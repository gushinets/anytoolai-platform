#!/usr/bin/env node
// Real-parser (TypeScript compiler API) replacement for the hand-rolled, heuristic JS/TS scope
// scanner that used to live in tests/architecture/static_string_resolution.py. That scanner
// (character-level brace/comma/ASI tracking approximating scope and control flow) went through
// seven consecutive fix rounds (ANY-25 rounds 36-42) chasing edge case after edge case — braceless
// control flow, concise arrow bodies, ASI, object-literal commas — each one a genuine gap the
// approximation couldn't see. A real parser doesn't have any of these ambiguities: it already
// knows exactly where every statement, block, and expression starts and ends.
//
// Usage: node js_scope_resolver.mjs < <JSON array of absolute file paths> > <JSON result>
//
// Output: { [path]: { text: string, values: { [offset]: string[] }, roots: [offset, string][] } }
// - `text` is the file's source with every comment blanked to same-length whitespace (newlines
//   kept), so every character offset below matches the *original* file exactly — callers can
//   still regex-scan `text` for candidate positions (a `role:` key, a `LiteLLM/model` shape, an
//   import specifier) without comment content producing a false match, then resolve the value at
//   that exact offset via `values`.
// - `values[offset]` is every statically-known string value the expression starting at `offset`
//   could take (folded strings/templates/`+`-chains, and identifier references resolved through
//   real lexical scope and write-order — see `resolveIdentifier` below). Absent or empty means
//   "genuinely dynamic here."
// - `roots` is every top-level (not nested inside another already-foldable string expression)
//   resolved expression's `(offset, value)` pairs, flattened one entry per value — an exhaustive
//   scan of every hardcoded/foldable string literally reachable in the file.

import ts from "typescript";
import { readFileSync } from "fs";
import path from "path";

const MAX_COMBINATIONS = 256; // ponytail: matches the prior resolver's own Cartesian-product cap

function scriptKindFor(filePath) {
  if (filePath.endsWith(".tsx")) return ts.ScriptKind.TSX;
  if (filePath.endsWith(".ts")) return ts.ScriptKind.TS;
  if (filePath.endsWith(".jsx")) return ts.ScriptKind.JSX;
  return ts.ScriptKind.JS; // .js, .mjs, .cjs
}

/** `text` with every comment (line or block) replaced by same-length whitespace (newlines kept
 * as newlines), so line numbers and every other character offset stay identical to the original
 * file — unlike blanking-by-removal, this keeps every later offset valid. */
function blankComments(text, scriptKind) {
  const scanner = ts.createScanner(ts.ScriptTarget.Latest, /* skipTrivia */ false, scriptKind, text);
  const chars = Array.from(text);
  let tok = scanner.scan();
  while (tok !== ts.SyntaxKind.EndOfFileToken) {
    if (tok === ts.SyntaxKind.SingleLineCommentTrivia || tok === ts.SyntaxKind.MultiLineCommentTrivia) {
      const start = scanner.getTokenPos();
      const end = scanner.getTextPos();
      for (let i = start; i < end; i++) {
        if (chars[i] !== "\n") chars[i] = " ";
      }
    }
    tok = scanner.scan();
  }
  return chars.join("");
}

// A `for`/`for-in`/`for-of` header's own `let`/`const` binding (`for (let i = 0; ...)`) is
// visible throughout the loop's condition/update/body but lives nowhere a `Block` can represent
// — its declaration is a sibling of the body, not an ancestor of it. Treating the loop statement
// itself as a scope node (round 46) lets `nearestScope` find it as the header's home while
// walking up from anywhere inside the loop, the same way a concise arrow's own node already
// stands in for a body-less scope.
function isForHeaderNode(node) {
  return (
    node.kind === ts.SyntaxKind.ForStatement ||
    node.kind === ts.SyntaxKind.ForInStatement ||
    node.kind === ts.SyntaxKind.ForOfStatement
  );
}

function isScopeNode(node) {
  return node.kind === ts.SyntaxKind.SourceFile || node.kind === ts.SyntaxKind.Block || isForHeaderNode(node);
}

/** The nearest enclosing scope node for `node` — a `Block`/`SourceFile`/for-loop header (see
 * `isForHeaderNode`), or (for a parameter default's own concise-arrow-body scope, which has no
 * `Block` at all) the `ArrowFunction` node itself. Walks the node's own ancestors, not itself. */
function nearestScope(node) {
  let n = node.parent;
  while (n) {
    if (isScopeNode(n)) return n;
    if (n.kind === ts.SyntaxKind.ArrowFunction && n.body && n.body.kind !== ts.SyntaxKind.Block) {
      return n; // concise (expression) body — the arrow node itself stands in for its own scope
    }
    n = n.parent;
  }
  return null;
}

/** The `Block`/`SourceFile`/etc. a parameter's default value is usable within: the function's own
 * body if braced, else the arrow node itself (a synthetic scope for a concise body). */
function paramOwnScope(fn) {
  if (fn.body && fn.body.kind === ts.SyntaxKind.Block) return fn.body;
  return fn; // concise arrow body
}

/** The nearest enclosing *function* scope for `node` — a braced function/arrow's own body, or
 * `SourceFile` at module level — skipping every intervening `Block`/for-header/if/etc. along the
 * way. This is `var`'s real scope (function- or module-scoped, unlike `let`/`const`'s block
 * scope): `if (enabled) { var provider = "..."; }` still puts `provider` in the *function's* own
 * scope, not the `if` block's, exactly like real JS hoisting (round 46). */
function nearestFunctionScope(node) {
  let n = node.parent;
  while (n) {
    if (n.kind === ts.SyntaxKind.SourceFile) return n;
    if (isFunctionLike(n)) return n.body && n.body.kind === ts.SyntaxKind.Block ? n.body : n;
    n = n.parent;
  }
  return null;
}

class FileAnalysis {
  constructor(sourceFile, text) {
    this.sourceFile = sourceFile;
    this.text = text;
    // scope node -> Map<name, decl info>
    this.declsByScope = new Map();
    // decl info -> resolved value cache (populated lazily, cycle-guarded)
    this.valueCache = new Map();
    this.inProgress = new Set();
    this.values = new Map(); // offset -> string[]
    this.roots = []; // [offset, value][]
    // name -> `{kind: "local", decl}` (a module-level `export const/let/var NAME = ...`) or
    // `{kind: "reexport", path, name}` (an `export { a as NAME } from "./x"`, or a bare
    // `export { NAME };` re-exporting this same file's own `NAME`) — see `resolveExport`.
    this.exportedNames = new Map();
  }

  scopeDecls(scope) {
    let m = this.declsByScope.get(scope);
    if (!m) {
      m = new Map();
      this.declsByScope.set(scope, m);
    }
    return m;
  }

  addDecl(name, scope, mutable, initExpr, pos, exported) {
    const decl = { name, scope, mutable, writes: [{ pos, expr: initExpr, own: true }] };
    let byName = this.scopeDecls(scope).get(name);
    if (!byName) {
      byName = [];
      this.scopeDecls(scope).set(name, byName);
    }
    byName.push(decl);
    if (exported && scope.kind === ts.SyntaxKind.SourceFile) {
      this.exportedNames.set(name, { kind: "local", decl });
    }
    return decl;
  }

  /** The declaration `name` resolves to when referenced from `refNode`, honoring lexical
   * shadowing (innermost enclosing scope with a matching declaration wins). Prefers the last
   * declaration recorded for that exact scope (mirrors `var` redeclaration / multiple `const`s
   * at the same depth folding into one continuous timeline, same as the prior resolver). */
  resolveDecl(refNode, name) {
    let scope = nearestScope(refNode);
    while (scope) {
      const byName = this.declsByScope.get(scope)?.get(name);
      if (byName && byName.length) return byName[byName.length - 1];
      scope = nearestScope(scope);
    }
    return null;
  }
}

const analyses = new Map(); // absolute path -> FileAnalysis

function resolveModuleSpecifier(fromPath, specifier) {
  if (!specifier.startsWith(".")) return null;
  const base = path.resolve(path.dirname(fromPath), specifier);
  const exts = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"];
  const candidates = [base, ...exts.map((e) => base + e), ...exts.map((e) => path.join(base, "index" + e))];
  for (const c of candidates) {
    if (analyses.has(c)) return c;
  }
  return null;
}

/** Every statically-known value a scoped binding could hold at `atPos`, replaying its write
 * history up to that point: a write that's a direct sibling statement in the binding's own scope
 * is deterministic (replaces the reachable set); a write nested inside anything else — a
 * braced or braceless `if`/`for`/`while`/`try`/nested block/etc. — is only conditionally reached
 * (adds to the set without discarding what came before). Mirrors the prior resolver's model
 * exactly, but decided from real parent pointers instead of approximated bracket-depth counting. */
function replayWrites(analysis, decl, atPos) {
  let reachable = new Set();
  for (const write of decl.writes) {
    if (write.pos > atPos) break;
    // An imported binding's "write" has no local expression to fold — its value comes from
    // wherever the import points, resolved lazily (see `resolveRedirectValue`) each time it's
    // actually needed rather than once, eagerly, when the import itself is first seen (round 46:
    // eager resolution made cross-file constant chains depend on file traversal order, since a
    // consumer processed before its dependency's own imports were installed would memoize an
    // "unresolvable" result that a later pass had no way to revisit).
    const values = write.redirect !== undefined ? resolveRedirectValue(write.redirect) : foldExpr(analysis, write.expr);
    const deterministic = write.own || isDeterministicWrite(write.node, decl.scope);
    if (deterministic) {
      reachable = new Set(values || []);
    } else if (values) {
      for (const v of values) reachable.add(v);
    }
  }
  return reachable;
}

/** Follows an `export { a as NAME } from "./x"` (or a bare `export { NAME };` re-exporting this
 * same file's own binding) to the real declaration it ultimately names — recursively, since a
 * re-export can itself point at another re-export, with `seen` guarding against a circular chain
 * (`a.ts` re-exports from `b.ts`, which re-exports back from `a.ts`). A name that was never
 * exported at all, directly or via a re-export, still resolves through this same path: a bare
 * `export { NAME }` re-exporting an ordinary (no `export` keyword of its own) local binding falls
 * back to that file's own top-level scope directly. */
function resolveExport(analysis, name, seen = new Set()) {
  const key = `${analysis.path}::${name}`;
  if (seen.has(key)) return null;
  seen.add(key);
  const entry = analysis.exportedNames.get(name);
  if (entry?.kind === "local") return { analysis, decl: entry.decl };
  if (entry?.kind === "reexport") {
    // `entry.path` is always a concrete path when the re-export is resolvable at all — a bare
    // `export { NAME };` (no `from`) is recorded with the *current* file's own path, not left
    // unset — so a genuinely unresolvable specifier (an external package, or a file outside this
    // batch) correctly falls through to `null` here instead of silently searching this file.
    const sourceAnalysis = entry.path ? analyses.get(entry.path) : null;
    return sourceAnalysis ? resolveExport(sourceAnalysis, entry.name, seen) : null;
  }
  const localDecls = analysis.declsByScope.get(analysis.sourceFile)?.get(name);
  return localDecls?.length ? { analysis, decl: localDecls[localDecls.length - 1] } : null;
}

// Guards `resolveRedirectValue`'s own recursion against a genuine circular *value* dependency
// (not just a re-export chain, already guarded by `resolveExport`'s own `seen` set) — e.g. two
// files whose exported constants each reference the other's, directly or transitively. Keyed by
// declaration object identity (stable across repeated lookups of the same binding), not by name,
// so two different bindings that happen to share a name never collide.
const redirectInProgress = new Set();

function resolveRedirectValue(redirect) {
  if (!redirect) return null;
  const target = resolveExport(redirect.analysis, redirect.name);
  if (!target || redirectInProgress.has(target.decl)) return null;
  redirectInProgress.add(target.decl);
  try {
    const set = replayWrites(target.analysis, target.decl, target.analysis.sourceFile.text.length);
    return set.size ? Array.from(set) : null;
  } finally {
    redirectInProgress.delete(target.decl);
  }
}

const CONDITIONAL_PARENT_SLOTS = [
  [ts.SyntaxKind.IfStatement, "thenStatement"],
  [ts.SyntaxKind.IfStatement, "elseStatement"],
  [ts.SyntaxKind.ForStatement, "statement"],
  [ts.SyntaxKind.ForInStatement, "statement"],
  [ts.SyntaxKind.ForOfStatement, "statement"],
  [ts.SyntaxKind.WhileStatement, "statement"],
  [ts.SyntaxKind.DoStatement, "statement"],
];

/** Whether `node` sits in one of the AST slots that only conditionally executes — the `then`/
 * `else` arm of an `if`, a loop body, or anywhere under a `try`/`catch`/`switch` case (treated as
 * conditional unconditionally, the same conservative call the prior resolver already made for
 * these — never wrong-direction, only ever "loses a little precision inside one block"). */
function isConditionalSlot(node, parent) {
  for (const [kind, prop] of CONDITIONAL_PARENT_SLOTS) {
    if (parent.kind === kind && parent[prop] === node) return true;
  }
  return (
    parent.kind === ts.SyntaxKind.TryStatement ||
    parent.kind === ts.SyntaxKind.CatchClause ||
    parent.kind === ts.SyntaxKind.CaseClause ||
    parent.kind === ts.SyntaxKind.DefaultClause
  );
}

/** Whether a write reaching `scope` from `assignmentNode` is a *deterministic* one — walking up
 * from the assignment, it never passes through a conditional slot (see `isConditionalSlot`), any
 * nested `Block` other than `scope` itself, or any function-like node other than `scope` itself
 * — all the way up to `scope`. This is the one test that correctly treats a *braceless*
 * `if (cond) role = "x";` exactly like the braced form: the braceless body's `ExpressionStatement`
 * sits directly in `IfStatement.thenStatement` — no `Block` node exists there at all for a
 * text-position/brace-counting heuristic to see, but a real parent pointer sees the slot
 * immediately.
 *
 * The function-like check matters just as much as the Block one, for the same underlying reason:
 * a write inside a nested function/arrow is only reached if and when that function is *called* —
 * never assumable from its mere textual position, since defining a function isn't running it. A
 * *braced* arrow/function body already gets this for free (its own `Block` isn't `scope`, so the
 * Block check alone already returns conditional) — but a *concise* arrow body has no `Block` at
 * all (`() => role = "x"` puts the assignment directly under the `ArrowFunction` node, no
 * wrapping statement or block in between), so without this explicit check a write nested inside
 * an uncalled concise arrow would walk straight up to `scope` and be wrongly read as
 * deterministic, exactly as if it always ran before the very next statement (round 44). */
function isFunctionLike(node) {
  switch (node.kind) {
    case ts.SyntaxKind.ArrowFunction:
    case ts.SyntaxKind.FunctionExpression:
    case ts.SyntaxKind.FunctionDeclaration:
    case ts.SyntaxKind.MethodDeclaration:
    case ts.SyntaxKind.GetAccessor:
    case ts.SyntaxKind.SetAccessor:
    case ts.SyntaxKind.Constructor:
      return true;
    default:
      return false;
  }
}

function isDeterministicWrite(assignmentNode, scope) {
  let node = assignmentNode;
  while (node !== scope) {
    const parent = node.parent;
    if (!parent) return false;
    if (isConditionalSlot(node, parent)) return false;
    if (node.kind === ts.SyntaxKind.Block && node !== scope) return false;
    if (isFunctionLike(node) && node !== scope) return false;
    node = parent;
  }
  return true;
}

function combine(parts) {
  if (parts.some((p) => !p || p.length === 0)) return null;
  let size = 1;
  for (const p of parts) {
    size *= p.length;
    if (size > MAX_COMBINATIONS) return null;
  }
  let combos = [""];
  for (const part of parts) {
    const next = [];
    for (const prefix of combos) {
      for (const v of part) next.push(prefix + v);
    }
    combos = next;
  }
  return combos;
}

/** Fold `node` to every statically-known string value it could produce — a literal, a template
 * (each hole resolved at its own true position), a `+` chain, a parenthesized sub-expression, or
 * an identifier resolved through real lexical scope and write-order (see `replayWrites`). `null`
 * for anything genuinely dynamic (a call, a member access, an unknown name). Memoized per node
 * with cycle protection (a value that depends on itself, directly or through an import cycle,
 * resolves to unresolvable rather than looping). */
function foldExpr(analysis, node) {
  if (!node) return null;
  if (analysis.valueCache.has(node)) return analysis.valueCache.get(node);
  if (analysis.inProgress.has(node)) return null;
  analysis.inProgress.add(node);
  const result = foldExprInner(analysis, node);
  analysis.inProgress.delete(node);
  analysis.valueCache.set(node, result);
  if (result) {
    analysis.values.set(node.getStart(analysis.sourceFile), result);
  }
  return result;
}

// TypeScript-only wrapper expressions that carry no runtime effect at all — `as`/`satisfies`/the
// legacy `<Type>expr` cast, and `!` (non-null assertion) — each just wraps `.expression` with
// type information the compiler erases; the runtime value is exactly the inner expression's
// (round 46). Folding through them is a plain unwrap, not a fold of their own.
const TRANSPARENT_WRAPPER_KINDS = new Set([
  ts.SyntaxKind.AsExpression,
  ts.SyntaxKind.SatisfiesExpression,
  ts.SyntaxKind.TypeAssertionExpression,
  ts.SyntaxKind.NonNullExpression,
]);

function foldExprInner(analysis, node) {
  const sf = analysis.sourceFile;
  switch (node.kind) {
    case ts.SyntaxKind.StringLiteral:
    case ts.SyntaxKind.NoSubstitutionTemplateLiteral:
      return [node.text];
    case ts.SyntaxKind.ParenthesizedExpression:
    case ts.SyntaxKind.AsExpression:
    case ts.SyntaxKind.SatisfiesExpression:
    case ts.SyntaxKind.TypeAssertionExpression:
    case ts.SyntaxKind.NonNullExpression:
      return foldExpr(analysis, node.expression);
    case ts.SyntaxKind.TemplateExpression: {
      const parts = [[node.head.text]];
      for (const span of node.templateSpans) {
        const holeValues = foldExpr(analysis, span.expression);
        if (!holeValues) return null;
        parts.push(holeValues);
        parts.push([span.literal.text]);
      }
      return combine(parts);
    }
    case ts.SyntaxKind.BinaryExpression: {
      if (node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
        const left = foldExpr(analysis, node.left);
        const right = foldExpr(analysis, node.right);
        return combine([left, right]);
      }
      return null;
    }
    case ts.SyntaxKind.Identifier: {
      const decl = analysis.resolveDecl(node, node.text);
      if (!decl) return null;
      const set = replayWrites(analysis, decl, node.getStart(sf));
      return set.size ? Array.from(set) : null;
    }
    default:
      return null;
  }
}

function isRootExpr(node) {
  const p = node.parent;
  if (!p) return true;
  if (p.kind === ts.SyntaxKind.ParenthesizedExpression) return false;
  if (TRANSPARENT_WRAPPER_KINDS.has(p.kind)) return false;
  if (p.kind === ts.SyntaxKind.BinaryExpression && p.operatorToken.kind === ts.SyntaxKind.PlusToken) return false;
  if (p.kind === ts.SyntaxKind.TemplateSpan) return false;
  return true;
}

function collectDeclarations(analysis) {
  const sf = analysis.sourceFile;

  // `var` is function/module-scoped and hoists out of every enclosing block, unlike `let`/
  // `const` — `if (enabled) { var provider = "x"; }` still declares `provider` in the *function*
  // (or module) scope, not the `if` block's, so a reference outside that block can still find it
  // (round 46: `nearestFunctionScope` finds that real scope; `isDeterministicWrite`'s existing
  // Block-crossing check then correctly still treats the write itself as conditional, since the
  // `if` block isn't the binding's own scope — a `var` assigned inside a branch that might not
  // run is exactly as uncertain as a `let` would be there).
  function collectDeclarationList(declList, containerNode, lexicalScope, isExported) {
    const isVar = (declList.flags & (ts.NodeFlags.Let | ts.NodeFlags.Const)) === 0;
    const mutable = (declList.flags & ts.NodeFlags.Const) === 0;
    const scope = isVar ? nearestFunctionScope(containerNode) || sf : lexicalScope;
    for (const decl of declList.declarations) {
      if (ts.isIdentifier(decl.name) && decl.initializer) {
        const d = analysis.addDecl(decl.name.text, scope, mutable, decl.initializer, decl.name.getStart(sf), isExported);
        d.writes[0].node = decl;
      }
    }
  }

  function visit(node) {
    if (ts.isVariableStatement(node)) {
      const isExported = (ts.getCombinedModifierFlags(node) & ts.ModifierFlags.Export) !== 0;
      collectDeclarationList(node.declarationList, node, nearestScope(node) || sf, isExported);
    } else if (
      isForHeaderNode(node) &&
      node.initializer &&
      ts.isVariableDeclarationList(node.initializer)
    ) {
      // The header's own scope is the loop statement itself (see `isForHeaderNode`) — there's no
      // `Block` a bare `for (let i = 0; ...)` header could live in.
      collectDeclarationList(node.initializer, node, node, false);
    } else if (
      (ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node) || ts.isArrowFunction(node)) &&
      node.parameters
    ) {
      const scope = paramOwnScope(node);
      for (const param of node.parameters) {
        if (ts.isIdentifier(param.name) && param.initializer) {
          const d = analysis.addDecl(param.name.text, scope, true, param.initializer, param.name.getStart(sf), false);
          d.writes[0].node = param;
        }
      }
    } else if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
      ts.isIdentifier(node.left)
    ) {
      const decl = analysis.resolveDecl(node, node.left.text);
      if (decl && decl.mutable) {
        decl.writes.push({ pos: node.left.getStart(sf), expr: node.right, node, own: false });
      }
    }
    ts.forEachChild(node, visit);
  }

  visit(sf);
  for (const byName of analysis.declsByScope.values()) {
    for (const decls of byName.values()) {
      for (const d of decls) d.writes.sort((a, b) => a.pos - b.pos);
    }
  }
}

/** Registers every named import as a module-level binding whose sole "write" is a *lazy*
 * `redirect` (resolved on demand by `resolveRedirectValue`, not eagerly here — round 46: eager
 * resolution needed every file's own imports installed first to see through a multi-hop chain,
 * making the result depend on which order files happened to be traversed in), and every
 * `export { a as b } from "./x"` / bare `export { name };` as a `reexport` entry in
 * `exportedNames` (structural only — which declaration a re-export ultimately names doesn't
 * depend on any value being folded yet, so, unlike the import bindings above, there's nothing
 * here to defer). Both kinds of registration are pure bookkeeping — the imported/re-exported
 * *value* isn't computed until something actually asks for it (see `main`'s own resolution pass),
 * so this function's own run order across files, like `collectDeclarations`'s, doesn't matter. */
function resolveImports(analysis) {
  const sf = analysis.sourceFile;
  ts.forEachChild(sf, function visit(node) {
    if (ts.isImportDeclaration(node) && node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) {
      const specifier = node.moduleSpecifier.text;
      const sourcePath = resolveModuleSpecifier(analysis.path, specifier);
      for (const spec of node.importClause.namedBindings.elements) {
        const exportedName = (spec.propertyName || spec.name).text;
        const localName = spec.name.text;
        const redirect = sourcePath ? { analysis: analyses.get(sourcePath), name: exportedName } : null;
        const d = { name: localName, scope: sf, mutable: false, writes: [{ pos: 0, own: true, redirect }] };
        analysis.scopeDecls(sf).set(localName, [d]);
      }
    } else if (ts.isExportDeclaration(node) && node.exportClause && ts.isNamedExports(node.exportClause)) {
      const specifier = node.moduleSpecifier ? node.moduleSpecifier.text : null;
      const sourcePath = specifier ? resolveModuleSpecifier(analysis.path, specifier) : analysis.path;
      for (const spec of node.exportClause.elements) {
        const sourceName = (spec.propertyName || spec.name).text;
        const localExportedName = spec.name.text;
        analysis.exportedNames.set(localExportedName, { kind: "reexport", path: sourcePath, name: sourceName });
      }
    }
    ts.forEachChild(node, visit);
  });
}

function main() {
  const input = readFileSync(0, "utf-8");
  const filePaths = JSON.parse(input);
  const output = {};

  for (const filePath of filePaths) {
    let text;
    try {
      text = readFileSync(filePath, "utf-8");
    } catch {
      continue;
    }
    const scriptKind = scriptKindFor(filePath);
    const blanked = blankComments(text, scriptKind);
    const sourceFile = ts.createSourceFile(filePath, blanked, ts.ScriptTarget.Latest, true, scriptKind);
    const analysis = new FileAnalysis(sourceFile, blanked);
    analysis.path = filePath;
    analyses.set(filePath, analysis);
  }

  for (const analysis of analyses.values()) collectDeclarations(analysis);
  for (const analysis of analyses.values()) resolveImports(analysis);

  for (const analysis of analyses.values()) {
    const sf = analysis.sourceFile;
    ts.forEachChild(sf, function visit(node) {
      foldExpr(analysis, node);
      ts.forEachChild(node, visit);
    });
    // Also resolve every plain identifier *reference* (not a declaration name, not a property
    // key) so a shorthand property (`{ role }`) and a bare reference both land in `values`.
    ts.forEachChild(sf, function visitIdents(node) {
      if (ts.isIdentifier(node) && isIdentifierReference(node)) {
        foldExpr(analysis, node);
      }
      ts.forEachChild(node, visitIdents);
    });

    const valuesObj = {};
    const roots = [];
    for (const [node, offset] of nodeOffsets(analysis)) {
      const values = analysis.valueCache.get(node);
      if (!values || !values.length) continue;
      valuesObj[offset] = values;
      if (isRootExpr(node)) {
        for (const v of values) roots.push([offset, v]);
      }
    }
    output[analysis.path] = { text: analysis.text, values: valuesObj, roots };
  }

  process.stdout.write(JSON.stringify(output));
}

function isIdentifierReference(node) {
  const p = node.parent;
  if (!p) return false;
  if (ts.isVariableDeclaration(p) && p.name === node) return false;
  if (ts.isParameter(p) && p.name === node) return false;
  if (ts.isPropertyAssignment(p) && p.name === node) return false;
  if (ts.isPropertyAccessExpression(p) && p.name === node) return false;
  if (ts.isImportSpecifier(p)) return false;
  if (ts.isBindingElement(p) && p.name === node) return false;
  if (ts.isFunctionDeclaration(p) || ts.isFunctionExpression(p) || ts.isClassDeclaration(p)) {
    if (p.name === node) return false;
  }
  return true;
}

function* nodeOffsets(analysis) {
  for (const node of analysis.valueCache.keys()) {
    if (!node.getStart) continue;
    yield [node, node.getStart(analysis.sourceFile)];
  }
}

main();
