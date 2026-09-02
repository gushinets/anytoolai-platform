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

function isScopeNode(node) {
  return node.kind === ts.SyntaxKind.SourceFile || node.kind === ts.SyntaxKind.Block;
}

/** The nearest enclosing scope node for `node` — a `Block`/`SourceFile`, or (for a parameter
 * default's own concise-arrow-body scope, which has no `Block` at all) the `ArrowFunction` node
 * itself. Walks the node's own ancestors, not itself. */
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
    this.exportedNames = new Map(); // name -> decl info (module-level `export const/let/var`)
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
      this.exportedNames.set(name, decl);
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
    // An imported binding's "write" is already resolved against the source file it came from
    // (see `resolveImports`) — there's no local expression node to fold here.
    const values = "resolved" in write ? write.resolved : foldExpr(analysis, write.expr);
    const deterministic = write.own || isDeterministicWrite(write.node, decl.scope);
    if (deterministic) {
      reachable = new Set(values || []);
    } else if (values) {
      for (const v of values) reachable.add(v);
    }
  }
  return reachable;
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
 * from the assignment, it never passes through a conditional slot (see `isConditionalSlot`) or
 * any nested `Block` other than `scope` itself, all the way up to `scope`. This is the one test
 * that correctly treats a *braceless* `if (cond) role = "x";` exactly like the braced form: the
 * braceless body's `ExpressionStatement` sits directly in `IfStatement.thenStatement` — no
 * `Block` node exists there at all for a text-position/brace-counting heuristic to see, but a
 * real parent pointer sees the slot immediately. */
function isDeterministicWrite(assignmentNode, scope) {
  let node = assignmentNode;
  while (node !== scope) {
    const parent = node.parent;
    if (!parent) return false;
    if (isConditionalSlot(node, parent)) return false;
    if (node.kind === ts.SyntaxKind.Block && node !== scope) return false;
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

function foldExprInner(analysis, node) {
  const sf = analysis.sourceFile;
  switch (node.kind) {
    case ts.SyntaxKind.StringLiteral:
    case ts.SyntaxKind.NoSubstitutionTemplateLiteral:
      return [node.text];
    case ts.SyntaxKind.ParenthesizedExpression:
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
  if (p.kind === ts.SyntaxKind.BinaryExpression && p.operatorToken.kind === ts.SyntaxKind.PlusToken) return false;
  if (p.kind === ts.SyntaxKind.TemplateSpan) return false;
  return true;
}

function collectDeclarations(analysis) {
  const sf = analysis.sourceFile;

  function visit(node) {
    if (ts.isVariableStatement(node)) {
      const isExported = (ts.getCombinedModifierFlags(node) & ts.ModifierFlags.Export) !== 0;
      const scope = nearestScope(node) || sf;
      const mutable = (node.declarationList.flags & ts.NodeFlags.Const) === 0;
      for (const decl of node.declarationList.declarations) {
        if (ts.isIdentifier(decl.name) && decl.initializer) {
          const d = analysis.addDecl(decl.name.text, scope, mutable, decl.initializer, decl.name.getStart(sf), isExported);
          d.writes[0].node = decl;
        }
      }
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

function resolveImports(analysis) {
  const sf = analysis.sourceFile;
  ts.forEachChild(sf, function visit(node) {
    if (ts.isImportDeclaration(node) && node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) {
      const specifier = node.moduleSpecifier.text;
      const sourcePath = resolveModuleSpecifier(analysis.path, specifier);
      const sourceAnalysis = sourcePath ? analyses.get(sourcePath) : null;
      for (const spec of node.importClause.namedBindings.elements) {
        const exportedName = (spec.propertyName || spec.name).text;
        const localName = spec.name.text;
        let values = null;
        if (sourceAnalysis) {
          const exportedDecl = sourceAnalysis.exportedNames.get(exportedName);
          if (exportedDecl) {
            const endPos = sourceAnalysis.sourceFile.text.length;
            const set = replayWrites(sourceAnalysis, exportedDecl, endPos);
            values = set.size ? Array.from(set) : null;
          }
        }
        // A module-level synthetic declaration whose sole "write" is the already-resolved
        // imported value — reuses the same write/replay machinery so shadowing a local
        // re-export or re-binding the import name (rare) still behaves consistently.
        const d = { name: localName, scope: sf, mutable: false, writes: [{ pos: 0, own: true, resolved: values }] };
        analysis.scopeDecls(sf).set(localName, [d]);
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
