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
 * `isForHeaderNode`), the `ArrowFunction` node itself (a parameter default's own concise-arrow-
 * body scope, which has no `Block` at all), or the enclosing function-like node itself (every
 * parameter's own scope — see below). Walks the node's own ancestors, not itself. */
function nearestScope(node) {
  let n = node;
  let parent = n.parent;
  while (parent) {
    if (isScopeNode(parent)) return parent;
    if (parent.kind === ts.SyntaxKind.ArrowFunction && parent.body && parent.body.kind !== ts.SyntaxKind.Block) {
      return parent; // concise (expression) body — the arrow node itself stands in for its own scope
    }
    if (isFunctionLike(parent) && ((parent.parameters && parent.parameters.includes(n)) || parent.body === n)) {
      // The function-like node itself is every parameter's own scope — real JS evaluates
      // parameter defaults in a distinct "parameter environment" that sits *outside* the
      // function body's own lexical environment: a later parameter default can see an earlier
      // parameter, and the body can see every parameter, but a body-local declaration does NOT
      // shadow a parameter default's own outer reference of the same name (round 51 — round 50's
      // fix routed parameter defaults into the *body's* own `Block` scope instead of a separate
      // one, so a same-named body-local `const`/`let` incorrectly won lexical lookup over the
      // real outer binding a parameter default actually sees at runtime).
      //
      // This one function node serves as that separate scope for both directions: reached
      // directly from inside the parameter list (`parent.parameters.includes(n)` — a later
      // parameter's default referencing an earlier one), where the walk never touches the body's
      // own `Block` at all (it isn't an ancestor of anything inside the parameter list), so a
      // body-local declaration is structurally unreachable from here; and reached one step out
      // from the body's own `Block` once nothing was found there (`parent.body === n`), which
      // still finds every parameter, exactly as real JS scoping does.
      return parent;
    }
    n = parent;
    parent = n.parent;
  }
  return null;
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
    // name -> `{kind: "local", decl}` (a module-level `export const/let/var NAME = ...`, or a bare
    // `export { NAME };` resolved directly to its own local declaration) or `{kind: "reexport",
    // path, name}` (an `export { a as NAME } from "./x"`) — see `resolveExport`.
    this.exportedNames = new Map();
    // Every `export * from "./x"` target this file has, as resolved absolute paths — a fallback
    // `resolveExport` only tries after a direct name lookup misses, since a star export re-exports
    // whatever its target itself exports, not a specific known set of names (round 47).
    this.starExports = [];
  }

  scopeDecls(scope) {
    let m = this.declsByScope.get(scope);
    if (!m) {
      m = new Map();
      this.declsByScope.set(scope, m);
    }
    return m;
  }

  /** Get-or-create the (name, scope) binding. A redeclaration at the same (name, scope) — legal
   * JS only for `var` (`var provider = "openai"; if (x) { var provider = "internal"; }` is one
   * runtime binding, not two) — reuses the same binding object rather than creating a second one,
   * so every write across every redeclaration lands on a single continuous timeline that
   * `resolveDecl` sees in full. Also used to register a binding with no writes at all yet
   * (`let provider;`), so a later plain assignment has a declaration to attach its write to
   * (round 47: previously an uninitialized declaration was never registered, so the first real
   * assignment had nothing to find and was silently dropped, and each `var` redeclaration got its
   * own separate `writes` array, so `resolveDecl`'s "last recorded wins" picked only the LAST
   * declaration and discarded every earlier one's write history). */
  binding(name, scope, mutable, exported) {
    let byName = this.scopeDecls(scope).get(name);
    if (!byName) {
      byName = [];
      this.scopeDecls(scope).set(name, byName);
    }
    let decl = byName[byName.length - 1];
    if (!decl) {
      decl = { name, scope, mutable, writes: [] };
      byName.push(decl);
    }
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
    const values =
      write.redirect !== undefined
        ? resolveRedirectValue(write.redirect)
        : write.copyOf !== undefined
          ? copyDeclValue(analysis, write.copyOf)
          : foldExpr(analysis, write.expr);
    const deterministic = write.own || isDeterministicWrite(write.node, decl.scope);
    if (deterministic) {
      reachable = new Set(values || []);
    } else if (values) {
      for (const v of values) reachable.add(v);
    }
  }
  return reachable;
}

/** Every statically-known value `decl` (some *other* binding in the same file — a same-named
 * enclosing parameter, for a body `var`'s function-entry seed value) could hold by the end of the
 * file, for a write that copies another declaration's value wholesale rather than folding its own
 * expression (round 52's `copyOf`). No cycle guard needed here the way `resolveRedirectValue`
 * needs one for import/export chains: only a `var` write ever carries `copyOf`, and it always
 * points at a *parameter* decl, which can never itself carry a `copyOf` back — so no cycle is
 * structurally possible. */
function copyDeclValue(analysis, decl) {
  const set = replayWrites(analysis, decl, analysis.sourceFile.text.length);
  return set.size ? Array.from(set) : null;
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
  if (localDecls?.length) return { analysis, decl: localDecls[localDecls.length - 1] };
  // `export * from "./x"` re-exports whatever `./x` itself exports, under the same name — tried
  // only after every direct name lookup above has missed, and only recursively through the same
  // `seen` guard already threading through this whole call, so a star-export cycle (`a.ts` and
  // `b.ts` each doing `export * from` the other) can't loop forever either (round 47).
  for (const starPath of analysis.starExports) {
    const starAnalysis = analyses.get(starPath);
    if (!starAnalysis) continue;
    const result = resolveExport(starAnalysis, name, seen);
    if (result) return result;
  }
  return null;
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

// `&&`/`||`/`??`'s right-hand operand only evaluates when the left side's truthiness (or, for
// `??`, nullishness) allows it — `cond && (x = "y")` never runs the assignment at all when `cond`
// is falsy, exactly like an `if` body never running (round 54). Checked by operator kind, not
// just AST shape, since a `BinaryExpression`'s `.right` is otherwise perfectly ordinary — `+`'s
// right side, for one, always evaluates unconditionally.
const SHORT_CIRCUIT_OPERATORS = new Set([
  ts.SyntaxKind.AmpersandAmpersandToken,
  ts.SyntaxKind.BarBarToken,
  ts.SyntaxKind.QuestionQuestionToken,
]);

/** Whether `node` sits in one of the AST slots that only conditionally executes — the `then`/
 * `else` arm of an `if`, a loop body, anywhere under a `try`/`catch`/`switch` case, a short-circuit
 * operator's right-hand side, or a ternary's `whenTrue`/`whenFalse` branch (treated as conditional
 * unconditionally, the same conservative call the prior resolver already made for these — never
 * wrong-direction, only ever "loses a little precision inside one block"). */
function isConditionalSlot(node, parent) {
  for (const [kind, prop] of CONDITIONAL_PARENT_SLOTS) {
    if (parent.kind === kind && parent[prop] === node) return true;
  }
  if (parent.kind === ts.SyntaxKind.BinaryExpression && parent.right === node) {
    return SHORT_CIRCUIT_OPERATORS.has(parent.operatorToken.kind);
  }
  if (parent.kind === ts.SyntaxKind.ConditionalExpression && (parent.whenTrue === node || parent.whenFalse === node)) {
    return true;
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
    // A parameter's own scope is its function node itself, not the function's body `Block`
    // (round 51, so a body-local declaration can't shadow a parameter default's own outer
    // reference — see `nearestScope`). That makes the function's own top-level body `Block` sit
    // *between* a body-level write and a parameter's `scope`, which would otherwise wrongly read
    // as a Block-boundary crossing — that check exists to catch a write nested inside some other,
    // possibly-conditional inner block, not the function's own unconditional top-level body. So
    // this one Block, specifically, doesn't count as a crossing.
    const isOwnFunctionBody = isFunctionLike(scope) && scope.body === node;
    if (node.kind === ts.SyntaxKind.Block && node !== scope && !isOwnFunctionBody) return false;
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
  //
  // Binding *existence* is collected in a first pass, over the whole file, before any write is
  // attached to anything — real JS hoists a `var`'s binding (and a function's parameters) to
  // function entry regardless of where its declaration textually sits, so an assignment appearing
  // *before* a `var` statement must still resolve to that same hoisted binding. A single
  // source-order traversal doing both at once got this wrong: an assignment visited before the
  // `var` statement it actually targets found no binding registered yet for that name at that
  // scope, and either fell through to some unrelated outer scope's same-named binding or was
  // dropped outright (round 53).
  function declareList(declList, containerNode, lexicalScope, isExported) {
    const isVar = (declList.flags & (ts.NodeFlags.Let | ts.NodeFlags.Const)) === 0;
    const mutable = (declList.flags & ts.NodeFlags.Const) === 0;
    const scope = isVar ? nearestFunctionScope(containerNode) || sf : lexicalScope;
    for (const decl of declList.declarations) {
      if (!ts.isIdentifier(decl.name)) continue;
      const name = decl.name.text;
      const isFreshBinding = !analysis.declsByScope.get(scope)?.get(name)?.length;
      const b = analysis.binding(name, scope, mutable, isExported);
      if (isVar && isFreshBinding) {
        // A body `var` that shares a name with an enclosing parameter reuses that parameter's own
        // *current* value as its initial value at function entry — real JS
        // (`FunctionDeclarationInstantiation`) copies the parameter binding's value into the newly
        // created `var` binding when the two share a name, even with parameter-default expressions
        // present, before any of the `var`'s own body-level writes run (round 52). Seeded HERE, in
        // this first (binding-existence) pass — not in the second, write-attaching pass below —
        // specifically because an assignment positioned *before* the `var` statement now correctly
        // resolves to (and pushes its own write onto) this same binding, thanks to the hoisting fix
        // above; if seeding waited for the write-attaching pass to actually reach this `var`
        // statement, that earlier assignment's write would already be sitting in `b.writes` by
        // then, making a `b.writes.length === 0` freshness check see "not empty" and skip seeding
        // entirely (round 53 self-caught: this exact bug, in this exact fix, on the first attempt).
        // Seeding here instead only requires the *parameter's own decl object* to already exist —
        // not yet its own write, only attached in the second pass below — since `copyOf` stores a
        // reference to resolve lazily, well after every pass has finished; the enclosing function's
        // parameters are always registered before its own nested `var`s reach this point, since a
        // pre-order walk visits the function node itself (and its parameters) before recursing into
        // its body.
        //
        // `paramDecls` reflects only the parameter's *own* writes once fully attached (its default
        // value, plus any reassignment that genuinely targets the parameter itself with no
        // same-named `var` around) — with hoisting fixed, every body-level write to a name that
        // also names a parameter resolves to *this* `var` binding, never falls through to the
        // parameter's, so `copyDeclValue` never sees anything past the parameter's own
        // function-entry value.
        const enclosingFn = scope.kind === ts.SyntaxKind.Block ? scope.parent : null;
        if (enclosingFn && isFunctionLike(enclosingFn)) {
          const paramDecls = analysis.declsByScope.get(enclosingFn)?.get(name);
          if (paramDecls?.length) {
            b.writes.push({ pos: 0, own: true, copyOf: paramDecls[paramDecls.length - 1] });
          }
        }
      }
    }
  }

  function declare(node) {
    if (ts.isVariableStatement(node)) {
      const isExported = (ts.getCombinedModifierFlags(node) & ts.ModifierFlags.Export) !== 0;
      declareList(node.declarationList, node, nearestScope(node) || sf, isExported);
    } else if (isForHeaderNode(node) && node.initializer && ts.isVariableDeclarationList(node.initializer)) {
      declareList(node.initializer, node, node, false);
    } else if (
      (ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node) || ts.isArrowFunction(node)) &&
      node.parameters
    ) {
      for (const param of node.parameters) {
        if (ts.isIdentifier(param.name) && param.initializer) analysis.binding(param.name.text, node, true, false);
      }
    }
    ts.forEachChild(node, declare);
  }
  declare(sf);

  // Second pass, in source order as before: attach every initializer/default/assignment write to
  // the binding it belongs to — every binding it could possibly name already exists from the pass
  // above, so `resolveDecl` here always finds the real one instead of depending on how far
  // traversal has gotten.
  function collectDeclarationList(declList, containerNode, lexicalScope, isExported) {
    const isVar = (declList.flags & (ts.NodeFlags.Let | ts.NodeFlags.Const)) === 0;
    const mutable = (declList.flags & ts.NodeFlags.Const) === 0;
    const scope = isVar ? nearestFunctionScope(containerNode) || sf : lexicalScope;
    for (const decl of declList.declarations) {
      if (!ts.isIdentifier(decl.name)) continue;
      const name = decl.name.text;
      const b = analysis.binding(name, scope, mutable, isExported); // already registered above,
      // including this var's own function-entry `copyOf` seed if it shares a name with an
      // enclosing parameter — see `declareList`'s first pass, above.
      if (decl.initializer) {
        // `own: false` (not unconditionally `true`) so this write's determinism is computed for
        // real by `isDeterministicWrite`, exactly like an ordinary reassignment below — the same
        // result as before for `let`/`const` (whose own lexical scope trivially *is* wherever
        // they're declared, so the walk up always reaches `scope` immediately with nothing
        // conditional crossed) but no longer wrong for `var`, whose `scope` can be an outer
        // function/module scope while this particular declaration sits inside a conditional block
        // (round 47).
        b.writes.push({ pos: decl.name.getStart(sf), expr: decl.initializer, node: decl, own: false });
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
      // The function node itself is every parameter's own scope, for both braced and concise
      // bodies alike — see `nearestScope`'s matching case for why this must be a scope distinct
      // from the function body's own `Block` (round 51).
      const scope = node;
      for (const param of node.parameters) {
        if (ts.isIdentifier(param.name) && param.initializer) {
          // Unlike a declaration's own initializer above, a parameter default's write stays
          // unconditionally `own: true` — it isn't reached through ordinary statement control
          // flow at all (whether it applies depends on whether the caller omitted the argument,
          // not on any AST ancestry `isDeterministicWrite` could see), and there's exactly one
          // such write per parameter to reason about.
          const b = analysis.binding(param.name.text, scope, true, false); // already registered above
          b.writes.push({ pos: param.name.getStart(sf), expr: param.initializer, node: param, own: true });
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
 * making the result depend on which order files happened to be traversed in); every
 * `export { a as b } from "./x"` as a `reexport` entry in `exportedNames`; a bare `export { name };`
 * (no `from`) as a direct `local` entry, resolved immediately against this same file's own already-
 * collected declarations rather than deferred (round 47: deferring it as a self-pointing `reexport`
 * made `resolveExport` walk straight into its own cycle guard); and every `export * from "./x"` as
 * an entry in `starExports`, a fallback `resolveExport` only consults after a direct name lookup
 * misses (round 47). All of this is pure bookkeeping — the imported/re-exported *value* isn't
 * computed until something actually asks for it (see `main`'s own resolution pass), so this
 * function's own run order across files, like `collectDeclarations`'s, doesn't matter. */
function resolveImports(analysis) {
  const sf = analysis.sourceFile;
  ts.forEachChild(sf, function visit(node) {
    if (ts.isImportDeclaration(node) && node.importClause) {
      const specifier = node.moduleSpecifier.text;
      const sourcePath = resolveModuleSpecifier(analysis.path, specifier);
      if (node.importClause.name) {
        // `import provider from "./provider"` — a default import redirects to the source
        // module's "default" export, the same synthetic name an `export default ...;` registers
        // under (round 49/50: previously only `importClause.namedBindings` was read at all, so a
        // default import had no binding whatsoever, regardless of what the source module did).
        const localName = node.importClause.name.text;
        const redirect = sourcePath ? { analysis: analyses.get(sourcePath), name: "default" } : null;
        const d = { name: localName, scope: sf, mutable: false, writes: [{ pos: 0, own: true, redirect }] };
        analysis.scopeDecls(sf).set(localName, [d]);
      }
      if (node.importClause.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) {
        for (const spec of node.importClause.namedBindings.elements) {
          const exportedName = (spec.propertyName || spec.name).text;
          const localName = spec.name.text;
          const redirect = sourcePath ? { analysis: analyses.get(sourcePath), name: exportedName } : null;
          const d = { name: localName, scope: sf, mutable: false, writes: [{ pos: 0, own: true, redirect }] };
          analysis.scopeDecls(sf).set(localName, [d]);
        }
      }
    } else if (ts.isExportAssignment(node) && !node.isExportEquals) {
      // `export default <expr>;` — not tied to any named declaration (the expression can be a
      // bare literal, `export default "system";`), so this registers a synthetic anonymous
      // binding under the reserved name `"default"` whose one write is the assignment's own
      // expression, deterministic by construction (an `ExportAssignment` can only ever be a
      // top-level statement). `export { default as name } from "./x"` / `import x from "./y"`
      // both resolve through this same `"default"` name — no separate handling needed for those,
      // since `resolveExport`'s existing name lookup is already generic over the name string.
      // (`node.isExportEquals` is true only for the legacy CommonJS-interop `export = x;` form,
      // which isn't a default export at all — deliberately left unhandled here.)
      analysis.exportedNames.set("default", {
        kind: "local",
        decl: { name: "default", scope: sf, mutable: false, writes: [{ pos: 0, expr: node.expression, node, own: true }] },
      });
    } else if (ts.isExportDeclaration(node) && node.exportClause && ts.isNamedExports(node.exportClause)) {
      const specifier = node.moduleSpecifier ? node.moduleSpecifier.text : null;
      for (const spec of node.exportClause.elements) {
        const sourceName = (spec.propertyName || spec.name).text;
        const localExportedName = spec.name.text;
        if (!specifier) {
          // A bare `export { name };` (no `from`) re-exports THIS file's own binding directly.
          // Recording it as a `reexport` pointing at this same file would make `resolveExport`
          // walk straight back into its own cycle guard (`<this file>::name` is already in `seen`
          // from the very call that's looking it up) and give up before ever reaching the local-
          // declaration fallback — resolving to unresolvable for an ordinary, fully static
          // same-file re-export (round 47). `collectDeclarations` has already run for every file
          // by the time any file's `resolveImports` runs, so the local declaration is already
          // there to resolve directly instead of deferring.
          const localDecls = analysis.declsByScope.get(sf)?.get(sourceName);
          if (localDecls?.length) {
            analysis.exportedNames.set(localExportedName, { kind: "local", decl: localDecls[localDecls.length - 1] });
            continue;
          }
        }
        const sourcePath = specifier ? resolveModuleSpecifier(analysis.path, specifier) : analysis.path;
        analysis.exportedNames.set(localExportedName, { kind: "reexport", path: sourcePath, name: sourceName });
      }
    } else if (ts.isExportDeclaration(node) && !node.exportClause && node.moduleSpecifier) {
      const sourcePath = resolveModuleSpecifier(analysis.path, node.moduleSpecifier.text);
      if (sourcePath) analysis.starExports.push(sourcePath);
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
