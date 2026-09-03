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
  return (
    node.kind === ts.SyntaxKind.SourceFile ||
    node.kind === ts.SyntaxKind.Block ||
    node.kind === ts.SyntaxKind.ModuleBlock || // a TS `namespace X { ... }` body (round 62)
    isForHeaderNode(node)
  );
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

// ─── Member paths ────────────────────────────────────────────────────────────────────────────
//
// Every read this resolver performs is one shape: `(root binding, key path, position)`. A bare
// identifier is the empty path; `config.llm.provider` is `config` + `["llm", "provider"]`; a
// destructured `const { llm: { provider } } = config` is the same path taken at the destructuring
// statement's own position. Every *member* assignment — `config.llm = ...`, `config.llm.provider
// += ...`, `config[KEY] = ...` — is a write recorded on the *root* binding with its key chain
// (`decl.memberWrites`), not on some per-property side structure. One replay (`replayPath`)
// merges the binding's own writes and every member write that touches a prefix of the path, in
// source order: a write to `config.llm` at level 1 supplies the value for `config.llm.provider`
// by walking its new value structurally one more level; a write to `config.llm.provider` at
// level 2 supplies it directly; a rebinding of `config` at level 0 resets everything.
//
// Round 63: the previous model (rounds 58–62) hung a per-property write timeline off a
// *single-shape* container — so any read that had to cross a container that had since been
// *replaced* (a nested destructuring's intermediate segment, a chained `a.b.c` read, a spread
// from a mutated base, a class static replaced then read through) silently fell back to the
// original literal or resolved to nothing at all. There is no per-property structure any more:
// mutation, replacement, and rebinding are all just writes at some depth on one timeline.

/** `+=` combines the target's own pre-write value with the folded RHS via string concatenation —
 * the only compound arithmetic operator this resolver models (round 56). `||=`/`&&=`/`??=` are
 * inherently conditional *by the operator itself*, independent of AST position — whether the new
 * value actually takes effect depends on the runtime truthiness/nullishness of the *current*
 * value — so these are never treated as deterministic (`forceConditional`), and their own
 * contribution is just the folded RHS: the old value's survival, when the assignment doesn't
 * trigger, is already implied by not replacing the reachable set. */
const COMPOUND_STRING_OPERATORS = new Set([ts.SyntaxKind.PlusEqualsToken]);
const COMPOUND_CONDITIONAL_OPERATORS = new Set([
  ts.SyntaxKind.BarBarEqualsToken,
  ts.SyntaxKind.AmpersandAmpersandEqualsToken,
  ts.SyntaxKind.QuestionQuestionEqualsToken,
]);

const STATIC_KEY = /^\d+$/;
const EOF = (analysis) => analysis.sourceFile.text.length;

function union(a, b) {
  if (!a) return b;
  if (!b) return a;
  return Array.from(new Set([...a, ...b]));
}

/** A read context. `atPos` is where the value is read. `bindPos`/`refDepth` describe a *captured
 * reference* (round 63): when a read walks through a value that was bound earlier — a literal's
 * member that is another binding (`config = { llm: inner }`), a destructured object (`const
 * { llm } = config`), a spread's copied members — the binding it lands on was fixed at `bindPos`,
 * and only the first `refDepth` path segments were *copied* then. Writes at or above that depth
 * after `bindPos` (a rebinding, a replacement of the captured slot) no longer concern the object
 * this read holds a reference to; writes *below* that depth (a mutation of the shared object
 * itself) still do, because JS objects are references, not copies. A plain read has
 * `bindPos === atPos`, where none of this matters. */
function ctxAt(atPos) {
  return { atPos, bindPos: atPos, refDepth: 0 };
}

/** Every statically-known value of `path` read off `decl` in context `ctx` (or, with
 * `containers`, every container literal node it could be): the binding's own writes and every
 * member write on a prefix of `path`, replayed in source order up to `ctx.atPos`. A write that's
 * a direct sibling statement in the binding's own scope is deterministic (replaces the reachable
 * set); one nested inside anything conditional — an `if`/loop/`try` body, a short-circuit RHS, a
 * ternary branch — or one whose member key is only ambiguously known, is only conditionally
 * reached (adds to the set without discarding what came before). `excludeWrite` is the one write
 * a self-referential RHS must not see (see `selfReferenceContext`). */
function replayPath(analysis, decl, path, ctx, excludeWrite = null, containers = false) {
  const events = decl.writes.map((write) => ({ write, depth: 0 }));
  for (const write of decl.memberWrites || []) {
    if (write.chain.length <= path.length) events.push({ write, depth: write.chain.length });
  }
  events.sort((a, b) => a.write.pos - b.write.pos);
  let reachable = new Set();
  let detached = false; // a captured slot was *conditionally* overwritten after `bindPos`
  for (const { write, depth } of events) {
    if (write === excludeWrite) continue;
    if (write.pos > ctx.atPos) break;
    let deterministic = write.own || (!write.forceConditional && isDeterministicWrite(write.node, decl.scope));
    if (depth > 0) {
      // `config[KEY] = ...`: a key that folds to exactly `path[i]` matches; one that folds to a
      // set containing it *might*; one that doesn't fold at all could be anything — the last two
      // are conditional matches. A key that folds to something else entirely can't be this slot.
      let matches = true;
      for (let i = 0; i < depth; i++) {
        const keys = memberKeys(analysis, write.chain[i]);
        if (keys && !keys.includes(path[i])) {
          matches = false;
          break;
        }
        if (!keys || keys.length > 1) deterministic = false;
      }
      if (!matches) continue;
    }
    if (write.pos > ctx.bindPos) {
      if (depth <= ctx.refDepth) {
        // The captured reference was rebound/replaced after it was taken: nothing later on this
        // binding's timeline can reach the object this read holds — unless the overwrite itself
        // might not have happened, in which case everything after is merely uncertain.
        if (deterministic) break;
        detached = true;
        continue;
      }
      if (detached) deterministic = false;
    }
    const values = writeValues(analysis, decl, write, path.slice(0, depth), path.slice(depth), ctx, containers);
    if (deterministic) {
      reachable = new Set(values || []);
    } else if (values) {
      for (const v of values) reachable.add(v);
    }
  }
  return reachable.size ? Array.from(reachable) : null;
}

/** What one write contributes to a read of `rest` below the slot it targets (`matched` is the
 * path prefix that slot sits at — needed by `+=`, which reads its own target's prior value). */
function writeValues(analysis, decl, write, matched, rest, ctx, containers) {
  if (write.redirect !== undefined) return redirectValues(write.redirect, rest, containers);
  if (write.copyOf !== undefined) {
    return replayPath(analysis, write.copyOf, rest, ctxAt(EOF(analysis)), null, containers);
  }
  if (write.compoundOp !== undefined) {
    if (rest.length || containers) return null; // a string has no members
    // Real JS reads the current value, then computes, then commits — replaying the target itself
    // up to (but excluding) this exact write gives that pre-write state directly.
    const prior = replayPath(analysis, decl, matched, { ...ctx, atPos: write.pos }, write);
    return write.compoundOp === ts.SyntaxKind.PlusEqualsToken ? combine([prior, foldExpr(analysis, write.rhsExpr)]) : null;
  }
  if (write.destructureFrom !== undefined) return destructureValues(analysis, write.destructureFrom, rest, ctx, containers);
  const expr = write.forceConditional ? write.rhsExpr : write.expr;
  return exprValues(analysis, expr, rest, { atPos: ctx.atPos, bindPos: write.pos, refDepth: 0 }, containers);
}

// Guards `redirectValues`'s own recursion against a genuine circular *value* dependency (not just a
// re-export chain, already guarded by `resolveExport`'s own `seen` set) — e.g. two files whose
// exported constants each reference the other's. Keyed by declaration object identity.
const redirectInProgress = new Set();

/** An imported binding's "write" has no local expression to fold — its value comes from wherever
 * the import points, resolved lazily each time it's needed rather than once when the import is
 * first seen (round 46: eager resolution made cross-file chains depend on traversal order). */
function redirectValues(redirect, rest, containers) {
  if (!redirect) return null; // an import whose specifier resolves to no file in this batch
  const target = resolveExport(redirect.analysis, redirect.name);
  if (!target || redirectInProgress.has(target.decl)) return null;
  redirectInProgress.add(target.decl);
  try {
    return replayPath(target.analysis, target.decl, rest, ctxAt(EOF(target.analysis)), null, containers);
  } finally {
    redirectInProgress.delete(target.decl);
  }
}

const MAX_PATH_DEPTH = 32; // ponytail: backstop for spread cycles (`a = {...b}; b = {...a}`)
let pathDepth = 0;

/** The values (or container literals) of `path` read off the *expression* `expr` in context
 * `ctx` — the single entry point every member read goes through. A member access flattens into
 * its object's path (`a.b.c` + `[d]` → `a` + `["b","c","d"]`); an identifier replays its binding;
 * an inline literal is walked structurally; a ternary or short-circuit expression contributes
 * both branches. `null` means "nothing statically known here." */
function exprValues(analysis, expr, path, ctx, containers = false) {
  if (!expr || pathDepth >= MAX_PATH_DEPTH) return null;
  pathDepth++;
  try {
    return exprValuesInner(analysis, expr, path, ctx, containers);
  } finally {
    pathDepth--;
  }
}

function exprValuesInner(analysis, expr, path, ctx, containers) {
  while (expr && (ts.isParenthesizedExpression(expr) || TRANSPARENT_WRAPPER_KINDS.has(expr.kind))) expr = expr.expression;
  if (ts.isConditionalExpression(expr)) {
    return union(exprValues(analysis, expr.whenTrue, path, ctx, containers), exprValues(analysis, expr.whenFalse, path, ctx, containers));
  }
  if (ts.isBinaryExpression(expr) && SHORT_CIRCUIT_OPERATORS.has(expr.operatorToken.kind) && !isAssignmentOperator(expr.operatorToken.kind)) {
    return union(exprValues(analysis, expr.left, path, ctx, containers), exprValues(analysis, expr.right, path, ctx, containers));
  }
  if (isContainerLiteral(expr)) return path.length ? literalValues(analysis, expr, path, ctx, containers) : containers ? [expr] : null;
  if (ts.isPropertyAccessExpression(expr) || ts.isElementAccessExpression(expr)) {
    const keys = memberKeys(analysis, expr);
    if (!keys) return null;
    const inner = { ...ctx, refDepth: ctx.refDepth + 1 };
    let out = null;
    for (const key of keys) out = union(out, exprValues(analysis, expr.expression, [key, ...path], inner, containers));
    return out;
  }
  if (!ts.isIdentifier(expr)) return path.length || containers ? null : foldExpr(analysis, expr);
  const decl = analysis.resolveDecl(expr, expr.text);
  if (!decl) return null;
  if (decl.namespaceOf) {
    // `import * as providers from "./x"; providers.primary` — looked up in the source module's own
    // export graph, exactly like an ordinary named import (round 58).
    if (!path.length) return null;
    const targetAnalysis = analyses.get(decl.namespaceOf);
    const target = targetAnalysis ? resolveExport(targetAnalysis, path[0]) : null;
    return target ? replayPath(target.analysis, target.decl, path.slice(1), ctxAt(EOF(target.analysis)), null, containers) : null;
  }
  if (decl.tsNamespace) {
    // `namespace Providers { export const primary = "openai"; }` → `Providers.primary`: a member
    // is an ordinary binding scoped to the namespace's own `ModuleBlock`, replayed in full.
    if (!path.length) return null;
    const inner = analysis.declsByScope.get(decl.tsNamespace)?.get(path[0]);
    return inner?.length ? replayPath(analysis, inner[inner.length - 1], path.slice(1), ctxAt(EOF(analysis)), null, containers) : null;
  }
  if (decl.enumNode) {
    // `enum Provider { OpenAI = "openai" }` → `Provider.OpenAI`: a string enum member is its
    // initializer; a numeric/auto member has no string value and correctly resolves to nothing.
    if (path.length !== 1 || containers) return null;
    for (const member of decl.enumNode.members) {
      const name = ts.isIdentifier(member.name) || ts.isStringLiteral(member.name) ? member.name.text : null;
      if (name === path[0]) return member.initializer ? foldExpr(analysis, member.initializer) : null;
    }
    return null;
  }
  // A reference sitting inside the RHS of one of its own target's writes (`provider = provider +
  // "ai"`, `config.provider = config.provider + "ai"`) reads the state *immediately before* that
  // write — the write itself is excluded and its own position becomes the cutoff (round 56).
  const enclosingWrite = selfReferenceContext(expr, decl);
  const readCtx = enclosingWrite ? ctxAt(enclosingWrite.pos) : ctx;
  return replayPath(analysis, decl, path, readCtx, enclosingWrite, containers);
}

function isAssignmentOperator(kind) {
  return kind >= ts.SyntaxKind.FirstAssignment && kind <= ts.SyntaxKind.LastAssignment;
}

/** Whether `node` (an identifier resolving to `decl`) sits inside the RHS of one of `decl`'s own
 * writes — binding writes and member writes alike. A purely *structural* check — the same AST
 * node always gives the same answer regardless of which caller folds it first, so it stays
 * correct under `foldExpr`'s permanent per-node memoization no matter the traversal order. */
function selfReferenceContext(node, decl) {
  const writes = decl.memberWrites ? [...decl.writes, ...decl.memberWrites] : decl.writes;
  for (let n = node; n; n = n.parent) {
    for (const write of writes) {
      if (write.expr === n || write.rhsExpr === n) return write;
    }
  }
  return null;
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

function isContainerLiteral(node) {
  return (
    !!node &&
    (ts.isObjectLiteralExpression(node) ||
      ts.isArrayLiteralExpression(node) ||
      ts.isClassExpression(node) ||
      ts.isClassDeclaration(node))
  );
}

/** The one string key a static member target names, or `null`: `obj.prop`, `obj["prop"]`, or
 * `obj[0]` (a numeric index reads and writes as the key `"0"`, so arrays and objects share one
 * member model). Never folds anything — safe to call during declaration collection. */
function staticMemberKey(expr) {
  if (ts.isPropertyAccessExpression(expr)) return ts.isIdentifier(expr.name) ? expr.name.text : null;
  if (ts.isElementAccessExpression(expr) && expr.argumentExpression) {
    const arg = expr.argumentExpression;
    return ts.isStringLiteralLike(arg) || ts.isNumericLiteral(arg) ? arg.text : null;
  }
  return null;
}

/** Every key a member access could name: the static one, or — for a computed `obj[key]` — every
 * string `key` folds to (`const KEY = "provider"; config[KEY]`, round 63). `null` when unknown. */
function memberKeys(analysis, expr) {
  const key = staticMemberKey(expr);
  if (key !== null) return [key];
  if (ts.isElementAccessExpression(expr) && expr.argumentExpression) return foldExpr(analysis, expr.argumentExpression);
  return null;
}

/** Every key an object-literal member could declare — static, or every string a computed
 * `[KEY]: ...` name folds to. `null` when unknown. */
function propertyKeys(analysis, prop) {
  const name = prop.name;
  if (!name) return null;
  if (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)) return [name.text];
  if (ts.isComputedPropertyName(name)) return foldExpr(analysis, name.expression);
  return null;
}

/** `path` read structurally off a container literal: an array by index string (`"0"`, nothing at
 * or after a `...spread` element, whose index is unknowable), a class's own `static` property
 * initializer, or an object literal's property — walked in *reverse* so a later member wins over
 * an earlier one and over an earlier spread, exactly as at runtime. A spread (`{ ...base }`) is
 * read *through* (`base` + the same path) at the literal's own evaluation position with the
 * spread's first level marked as copied (see `ctx`); an unresolvable spread is skipped, not
 * fatal: a member declared before it stays reachable, the safe direction for the gates this
 * feeds. A computed key that folds to several strings, or to nothing, *might* be this key, so its
 * value joins the result without ending the walk. */
function literalValues(analysis, literal, path, ctx, containers) {
  const [key, ...rest] = path;
  if (ts.isArrayLiteralExpression(literal)) {
    if (!STATIC_KEY.test(key)) return null;
    const index = Number(key);
    for (let i = 0; i < literal.elements.length; i++) {
      const el = literal.elements[i];
      if (ts.isSpreadElement(el)) return null;
      if (i === index) return ts.isOmittedExpression(el) ? null : exprValues(analysis, el, rest, ctx, containers);
    }
    return null;
  }
  if (ts.isClassExpression(literal) || ts.isClassDeclaration(literal)) {
    for (const member of literal.members) {
      if (
        ts.isPropertyDeclaration(member) &&
        member.initializer &&
        (ts.getCombinedModifierFlags(member) & ts.ModifierFlags.Static) !== 0 &&
        (ts.isIdentifier(member.name) || ts.isStringLiteral(member.name) || ts.isNumericLiteral(member.name)) &&
        member.name.text === key
      ) {
        return exprValues(analysis, member.initializer, rest, ctx, containers);
      }
    }
    return null;
  }
  if (!ts.isObjectLiteralExpression(literal)) return null;
  let maybe = null;
  for (let i = literal.properties.length - 1; i >= 0; i--) {
    const prop = literal.properties[i];
    if (ts.isSpreadAssignment(prop)) {
      const spreadCtx = { atPos: ctx.atPos, bindPos: ctx.bindPos, refDepth: 1 };
      const found = exprValues(analysis, prop.expression, path, spreadCtx, containers);
      if (found) return union(maybe, found);
      continue;
    }
    const keys = propertyKeys(analysis, prop);
    if (keys && !keys.includes(key)) continue;
    let value = null;
    if (ts.isPropertyAssignment(prop)) value = exprValues(analysis, prop.initializer, rest, ctx, containers);
    else if (ts.isShorthandPropertyAssignment(prop)) value = exprValues(analysis, prop.name, rest, ctx, containers);
    if (keys && keys.length === 1) return union(maybe, value);
    maybe = union(maybe, value);
  }
  return maybe;
}

/** Whether `path` is *guaranteed* present **and non-`undefined`** on the value `expr` evaluates
 * to in context `ctx` — a real destructuring default fires exactly when the extracted value is
 * `undefined`, not merely when the property was never declared (round 65: round 64's own version
 * of this check treated *any* exact-leaf write as proof, even an explicit `config.provider =
 * undefined;`, since reaching the leaf at all short-circuited straight to `true` without asking
 * what the leaf's own value actually is). Same traversal `exprValues` does (identical flattening,
 * replay, and capture/detach rules), combined with AND at every branch point (a ternary/
 * short-circuit only guarantees non-`undefined` when *every* branch does — the opposite of the
 * OR-shaped union a *value* read needs there). At the exact leaf (`path.length === 0`): `void x`
 * is always `undefined`; a container literal (constructing one is never `undefined`) or any other
 * self-contained expression (a string, a template, a `+`, a call result, ...) counts as defined;
 * an identifier defers to its own binding's timeline — including the global `undefined`, which
 * resolves no local declaration and so correctly falls through to `false` on its own, no special
 * case needed. This alone isn't the whole absence check `defaultedValues` needs (a `false` here
 * means "not guaranteed defined," which covers both "known absent/undefined" and "no idea" — an
 * opaque source, e.g. a function call's own result at a deeper, undescendable path, is `false`
 * here too) — see `defaultedValues` for how this pairs with `exprValues(..., true)` (a known-shape
 * check) to keep the never-guess-from-an-unknown-source rule this file has always followed. Never
 * guesses toward `true` from ambiguity: an unresolved spread, an ambiguous/unknown computed key,
 * or a class (whose instance/prototype members are unknowable) all leave `false`. */
function definitelyHasPath(analysis, expr, path, ctx) {
  if (!expr || pathDepth >= MAX_PATH_DEPTH) return false;
  pathDepth++;
  try {
    return definitelyHasPathInner(analysis, expr, path, ctx);
  } finally {
    pathDepth--;
  }
}

// Leaf expression *kinds* whose result is structurally guaranteed to never literally be
// `undefined`, regardless of what any sub-expression evaluates to (round 66) — the actual
// predicate is "can this evaluate to `undefined`," not "is it a string": `null` and `false` are
// both definitely non-`undefined` too (round 67 — a destructuring default fires *only* on
// `undefined`, never on `null` or any other falsy-but-defined value, so treating every primitive
// literal *except* strings/numbers as unproven was its own false-positive, injecting a default
// that can never actually run), alongside every other atomic JS/TS primitive-literal token
// (BigInt, regex) that carries the same guarantee for the same reason a string literal does — it
// *is* its own value, with no sub-expression to evaluate at all. `+` coerces both operands to a
// string (or `NaN`) no matter what they are, `undefined + "x"` included. Deliberately narrow
// beyond this — a `CallExpression`, `NewExpression`, or any other dynamic/unresolved shape stays
// unproven (see the review round 66 fixed: treating *any* non-identifier leaf as proof was the
// exact bug, since an ordinary function call can return `undefined`).
const NEVER_UNDEFINED_LEAF_KINDS = new Set([
  ts.SyntaxKind.StringLiteral,
  ts.SyntaxKind.NoSubstitutionTemplateLiteral,
  ts.SyntaxKind.TemplateExpression,
  ts.SyntaxKind.NumericLiteral,
  ts.SyntaxKind.BigIntLiteral,
  ts.SyntaxKind.RegularExpressionLiteral,
  ts.SyntaxKind.NullKeyword,
  ts.SyntaxKind.TrueKeyword,
  ts.SyntaxKind.FalseKeyword,
]);

function definitelyHasPathInner(analysis, expr, path, ctx) {
  while (expr && (ts.isParenthesizedExpression(expr) || TRANSPARENT_WRAPPER_KINDS.has(expr.kind))) expr = expr.expression;
  if (ts.isConditionalExpression(expr)) {
    return definitelyHasPath(analysis, expr.whenTrue, path, ctx) && definitelyHasPath(analysis, expr.whenFalse, path, ctx);
  }
  if (ts.isBinaryExpression(expr) && SHORT_CIRCUIT_OPERATORS.has(expr.operatorToken.kind) && !isAssignmentOperator(expr.operatorToken.kind)) {
    const op = expr.operatorToken.kind;
    if (!path.length && (op === ts.SyntaxKind.QuestionQuestionToken || op === ts.SyntaxKind.BarBarToken)) {
      // `a ?? b` / `a || b`, asked about the value itself (not a deeper member of it): whichever
      // side actually runs, the result is guaranteed non-`undefined` as soon as `b` alone is —
      // the *left* side, when it's the one that wins, is by definition non-nullish (`??`) or
      // truthy (`||`), hence already non-`undefined` on its own, with nothing to prove about it.
      // `&&`'s "left wins" branch is exactly *`a`'s own* falsy value instead, which could
      // genuinely be `undefined` — no such shortcut for it, so it keeps the blanket AND below (as
      // does either operator once there's a deeper path left to check: which side wins no longer
      // settles *that*, since a non-nullish/truthy `a` says nothing about whether `a.foo` exists).
      return definitelyHasPath(analysis, expr.right, path, ctx);
    }
    return definitelyHasPath(analysis, expr.left, path, ctx) && definitelyHasPath(analysis, expr.right, path, ctx);
  }
  if (ts.isBinaryExpression(expr) && expr.operatorToken.kind === ts.SyntaxKind.PlusToken) return !path.length;
  if (ts.isVoidExpression(expr)) return false; // `void x` always evaluates to `undefined`
  if (isContainerLiteral(expr)) return path.length ? literalDefinitelyHas(analysis, expr, path, ctx) : true;
  if (ts.isPropertyAccessExpression(expr) || ts.isElementAccessExpression(expr)) {
    const keys = memberKeys(analysis, expr);
    if (!keys || keys.length !== 1) return false; // an ambiguous/unknown key can't guarantee anything
    return definitelyHasPath(analysis, expr.expression, [keys[0], ...path], { ...ctx, refDepth: ctx.refDepth + 1 });
  }
  if (!path.length && NEVER_UNDEFINED_LEAF_KINDS.has(expr.kind)) return true;
  if (!ts.isIdentifier(expr)) return false; // an unresolved/dynamic expression (a call, ...) — never guess
  const decl = analysis.resolveDecl(expr, expr.text);
  if (!decl || decl.namespaceOf || decl.enumNode || decl.tsNamespace) return false; // includes the global `undefined`, which resolves no local decl
  const enclosingWrite = selfReferenceContext(expr, decl);
  const readCtx = enclosingWrite ? ctxAt(enclosingWrite.pos) : ctx;
  return replayPathDefinitelyHas(analysis, decl, path, readCtx, enclosingWrite);
}

/** `definitelyHasPath`'s counterpart to `replayPath` — same event list, same position/match/
 * capture-detach filtering, and the same *replace*-vs-*combine* structure the value replay itself
 * uses, just over a boolean instead of a set: a deterministic exact-leaf contribution *replaces*
 * the running verdict with its own (round 65 — round 64 only ever OR'd a monotonic `false → true`,
 * so a later deterministic write that plainly removes the key, e.g. `config = {};` after an
 * earlier write established it, could never undo an already-`true` verdict); a conditional one
 * combines with AND (guaranteed only when the state was already guaranteed *and* this write, if it
 * fires, keeps it so — matching the reviewer's own "both the executed and non-executed outcomes"
 * framing); and a deterministic rebind/replace at or above the captured depth ends the timeline
 * exactly where `replayPath` would stop looking too, without asserting anything from the rebind's
 * own new value there, a fresh, separately-asked question. */
function replayPathDefinitelyHas(analysis, decl, path, ctx, excludeWrite = null) {
  const events = decl.writes.map((write) => ({ write, depth: 0 }));
  for (const write of decl.memberWrites || []) {
    if (write.chain.length <= path.length) events.push({ write, depth: write.chain.length });
  }
  events.sort((a, b) => a.write.pos - b.write.pos);
  let certain = false;
  let detached = false;
  for (const { write, depth } of events) {
    if (write === excludeWrite) continue;
    if (write.pos > ctx.atPos) break;
    let deterministic = write.own || (!write.forceConditional && isDeterministicWrite(write.node, decl.scope));
    if (depth > 0) {
      let matches = true;
      for (let i = 0; i < depth; i++) {
        const keys = memberKeys(analysis, write.chain[i]);
        if (keys && !keys.includes(path[i])) {
          matches = false;
          break;
        }
        if (!keys || keys.length > 1) deterministic = false;
      }
      if (!matches) continue;
    }
    if (write.pos > ctx.bindPos) {
      if (depth <= ctx.refDepth) {
        if (deterministic) break;
        detached = true;
        continue;
      }
      if (detached) deterministic = false;
    }
    const contributes = writeDefinitelyHas(analysis, write, path.slice(depth), ctx);
    certain = deterministic ? contributes : certain && contributes;
  }
  return certain;
}

function writeDefinitelyHas(analysis, write, rest, ctx) {
  if (write.redirect !== undefined) {
    if (!write.redirect) return false;
    const target = resolveExport(write.redirect.analysis, write.redirect.name);
    return target ? replayPathDefinitelyHas(target.analysis, target.decl, rest, ctxAt(EOF(target.analysis))) : false;
  }
  if (write.copyOf !== undefined) return replayPathDefinitelyHas(analysis, write.copyOf, rest, ctxAt(EOF(analysis)));
  if (write.compoundOp !== undefined) return rest.length === 0; // `+=` always leaves a string, never a container
  if (write.destructureFrom !== undefined) {
    const d = write.destructureFrom;
    if (d.restOmit || d.restSkip !== undefined) return false; // presence through a rest element isn't modeled
    return definitelyHasPath(analysis, d.sourceExpr, [...d.path, ...rest], { atPos: d.atPos, bindPos: d.atPos, refDepth: d.path.length });
  }
  const expr = write.forceConditional ? write.rhsExpr : write.expr;
  return definitelyHasPath(analysis, expr, rest, { atPos: ctx.atPos, bindPos: write.pos, refDepth: 0 });
}

/** `literalValues`'s counterpart: whether a container literal *structurally guarantees* `path` —
 * an object literal's own exact (unambiguous), non-spread-shadowed property, or an array's
 * element by index with nothing at or after a `...spread`. A class is never certain (instance/
 * prototype members are unknowable); an unresolved spread, once reached without an exact winning
 * match found after it (reverse walk, latest-wins, same order as `literalValues`), also ends the
 * search unresolved rather than guessing through it. */
function literalDefinitelyHas(analysis, literal, path, ctx) {
  const [key, ...rest] = path;
  if (ts.isArrayLiteralExpression(literal)) {
    if (!STATIC_KEY.test(key)) return false;
    const index = Number(key);
    for (let i = 0; i < literal.elements.length; i++) {
      const el = literal.elements[i];
      if (ts.isSpreadElement(el)) return false;
      if (i === index) return !ts.isOmittedExpression(el) && definitelyHasPath(analysis, el, rest, ctx);
    }
    return false;
  }
  if (!ts.isObjectLiteralExpression(literal)) return false; // a class: instance/prototype members unknowable
  for (let i = literal.properties.length - 1; i >= 0; i--) {
    const prop = literal.properties[i];
    if (ts.isSpreadAssignment(prop)) return false;
    const keys = propertyKeys(analysis, prop);
    if (keys && !keys.includes(key)) continue; // definitely not this property, keep looking
    if (!keys || keys.length > 1) return false; // might be this property, might not — never certain either way
    if (ts.isPropertyAssignment(prop)) return definitelyHasPath(analysis, prop.initializer, rest, ctx);
    if (ts.isShorthandPropertyAssignment(prop)) return definitelyHasPath(analysis, prop.name, rest, ctx);
    return false;
  }
  return false;
}

/** A destructured binding's value: the source's `path` (+ whatever `rest` is read below the
 * binding), taken at the destructuring statement's own position — `path` itself was *copied*
 * then, so a later replacement of any segment of it doesn't reach this binding, while a later
 * mutation *inside* the object it holds does (see `ctx`). A rest element reads the same source
 * minus its siblings' keys (object) or shifted past its position (array); its own value is a fresh
 * container nothing can name. Per-element defaults apply at every level — see `defaultedValues`. */
function destructureValues(analysis, d, rest, ctx, containers) {
  let copyDepth = 0;
  if (d.restOmit) {
    if (!rest.length || d.restOmit.has(rest[0])) return null;
    copyDepth = 1;
  } else if (d.restSkip !== undefined) {
    if (!rest.length || !STATIC_KEY.test(rest[0])) return null;
    rest = [String(Number(rest[0]) + d.restSkip), ...rest.slice(1)];
    copyDepth = 1;
  }
  return defaultedValues(analysis, d.sourceExpr, d.path, d.defaults, rest, copyDepth, ctx.atPos, d.atPos, containers);
}

/** `keys` (+ `rest`) read off `source`, where `defaults[i]` — if any — replaces the container
 * reached after `keys[0..i-1]` whenever `keys[i]` isn't *guaranteed* to be there (round 64,
 * `definitelyHasPath` — round 62/63's own version of this check only asked "does the source's
 * *original literal* declare this key," blind to every member write recorded since, so a
 * deterministic `config.provider = "internal";` before `const { provider = "openai" } = config`
 * didn't stop `"openai"` from being wrongly treated as reachable). Two independent questions,
 * both required, keep the original "never guess from an unknown source" rule intact: `owners`
 * (unchanged from round 62 — a structural container-shape lookup) answers "is anything about this
 * position's shape known at all," so a destructuring off a function call's result still resolves
 * to nothing rather than guessing a default; `definitelyHasPath` answers "given everything this
 * resolver *does* know, including every write since, is the key guaranteed present" — only a
 * `false` there, on an otherwise-known shape, lets the default through, so a merely *conditional*
 * write still leaves both the found value and the default reachable, exactly as real JS would. */
function defaultedValues(analysis, source, keys, defaults, rest, copyDepth, atPos, bindPos, containers) {
  const ctx = { atPos, bindPos, refDepth: keys.length + copyDepth };
  let out = exprValues(analysis, source, [...keys, ...rest], ctx, containers);
  for (let i = 0; i < keys.length; i++) {
    if (!defaults[i]) continue;
    if (definitelyHasPath(analysis, source, keys.slice(0, i + 1), ctx)) continue; // guaranteed present
    const owners = exprValues(analysis, source, keys.slice(0, i), ctx, true);
    if (!owners) continue; // an opaque source (e.g. a function call) — never guess a default here
    out = union(out, defaultedValues(analysis, defaults[i], keys.slice(i + 1), defaults.slice(i + 1), rest, copyDepth, atPos, bindPos, containers));
  }
  return out;
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
// is falsy, exactly like an `if` body never running (round 54) — and their compound-assignment
// forms (`&&=`/`||=`/`??=`) are the exact same short-circuit on the exact same AST shape
// (`BinaryExpression.right`), just with a compound operator token instead of the plain one:
// `enabled &&= (provider = "internal")` never runs the nested assignment at all when `enabled` is
// falsy, for the identical reason (round 56, self-caught while extending round 54's own fix to
// compound assignment writes — not part of any review). Checked by operator kind, not just AST
// shape, since a `BinaryExpression`'s `.right` is otherwise perfectly ordinary — `+`'s right side,
// for one, always evaluates unconditionally.
const SHORT_CIRCUIT_OPERATORS = new Set([
  ts.SyntaxKind.AmpersandAmpersandToken,
  ts.SyntaxKind.BarBarToken,
  ts.SyntaxKind.QuestionQuestionToken,
  ts.SyntaxKind.AmpersandAmpersandEqualsToken,
  ts.SyntaxKind.BarBarEqualsToken,
  ts.SyntaxKind.QuestionQuestionEqualsToken,
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
 * an identifier resolved through real lexical scope and write-order (see `replayPath`). `null`
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
      // `a || "x"` / `a ?? "x"` / `a && "x"` evaluates to one operand or the other — both are
      // reachable (round 63), the same union a conditional write already produces.
      if (SHORT_CIRCUIT_OPERATORS.has(node.operatorToken.kind) && !isAssignmentOperator(node.operatorToken.kind)) {
        return union(foldExpr(analysis, node.left), foldExpr(analysis, node.right));
      }
      return null;
    }
    case ts.SyntaxKind.ConditionalExpression:
      return union(foldExpr(analysis, node.whenTrue), foldExpr(analysis, node.whenFalse));
    case ts.SyntaxKind.Identifier:
    case ts.SyntaxKind.PropertyAccessExpression:
    case ts.SyntaxKind.ElementAccessExpression:
      // A binding read, or `obj.prop` / `obj["prop"]` / `arr[0]` / `obj[KEY]` — one path model for
      // every container shape and every mutation kind, see `exprValues`.
      return exprValues(analysis, node, [], ctxAt(node.getStart(sf)));
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
  // A destructuring `BindingName` — `Identifier`, `ObjectBindingPattern`, or `ArrayBindingPattern`,
  // arbitrarily nested — registers every *leaf* identifier it names as a real binding, recursively
  // (round 61: `const { provider } = config;` previously created no binding for `provider` at all,
  // so a later deterministic reference either found nothing, or — worse, exactly the round-57
  // parameter shape again — fell through to shadow a same-named outer binding it should have hidden
  // instead). A rest element (`...rest`) and an omitted array slot (`[, b]`) are handled the same
  // way as everything else: `...rest` still recurses into its own (always a plain identifier)
  // `.name`, since it's a real binding too, just one this resolver never attempts to give a value
  // (see `declareBindingPattern`'s write-attaching counterpart, below); an omitted slot names
  // nothing, so there's nothing to register.
  function declareBindingName(bindingName, scope, mutable, isExported) {
    if (ts.isIdentifier(bindingName)) {
      analysis.binding(bindingName.text, scope, mutable, isExported);
      return;
    }
    if (ts.isObjectBindingPattern(bindingName) || ts.isArrayBindingPattern(bindingName)) {
      for (const el of bindingName.elements) {
        if (!ts.isOmittedExpression(el)) declareBindingName(el.name, scope, mutable, isExported);
      }
    }
  }

  function declareList(declList, containerNode, lexicalScope, isExported) {
    const isVar = (declList.flags & (ts.NodeFlags.Let | ts.NodeFlags.Const)) === 0;
    const mutable = (declList.flags & ts.NodeFlags.Const) === 0;
    const scope = isVar ? nearestFunctionScope(containerNode) || sf : lexicalScope;
    for (const decl of declList.declarations) {
      if (!ts.isIdentifier(decl.name)) {
        declareBindingName(decl.name, scope, mutable, isExported);
        continue;
      }
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
        // parameter's, so a `copyOf` replay never sees anything past the parameter's own
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
    } else if (isFunctionLike(node) && node.parameters) {
      // Every parameter — of *every* function-like kind, class methods/accessors/constructors
      // included (round 62: the old branch listed only declarations, expressions, and arrows, so a
      // method's parameters were never bindings at all), destructured or not (round 62: a
      // `{ provider }` parameter was skipped by an `isIdentifier` guard, exactly the gap round 61
      // had just closed for variable declarations), default value or not (round 57) — is a real
      // binding: it shadows any same-named outer binding for the whole function, and a later
      // deterministic assignment needs it to attach to. `declareBindingName` registers every leaf
      // of a pattern; a leaf with no static source (a non-default destructured parameter) simply
      // has no value, like any non-default parameter.
      for (const param of node.parameters) declareBindingName(param.name, node, true, false);
      if (ts.isFunctionDeclaration(node) && node.name) {
        // A function declaration's own name is a (hoisted, `var`-like) binding too — never a
        // string value, but it shadows a same-named outer binding across its whole enclosing
        // function, which an unregistered name would let a reference fall straight through.
        analysis.binding(node.name.text, nearestFunctionScope(node) || sf, true, false);
      }
    } else if (ts.isCatchClause(node) && node.variableDeclaration) {
      // `catch (e)` / `catch ({ message })` — a binding scoped to the catch block itself, never
      // given a value (a thrown value is dynamic), registered for correct shadowing (round 62).
      declareBindingName(node.variableDeclaration.name, node.block, true, false);
    } else if (ts.isClassDeclaration(node) && node.name) {
      // The class body is the binding's own container value, so `Config.provider` resolves a
      // `static` initializer through the same member model as an object literal, and a later
      // `Config.provider = ...` mutation lands on the same timeline (`literalValues`).
      const d = analysis.binding(node.name.text, nearestScope(node) || sf, true, false);
      d.writes.push({ pos: node.getStart(sf), expr: node, own: true });
    } else if (ts.isEnumDeclaration(node)) {
      const d = analysis.binding(node.name.text, nearestScope(node) || sf, false, false);
      d.enumNode = node;
    } else if (ts.isModuleDeclaration(node) && ts.isIdentifier(node.name) && node.body && ts.isModuleBlock(node.body)) {
      const d = analysis.binding(node.name.text, nearestScope(node) || sf, false, false);
      d.tsNamespace = node.body;
    }
    ts.forEachChild(node, declare);
  }
  declare(sf);

  // Second pass, in source order as before: attach every initializer/default/assignment write to
  // the binding it belongs to — every binding it could possibly name already exists from the pass
  // above, so `resolveDecl` here always finds the real one instead of depending on how far
  // traversal has gotten.
  // The write-attaching counterpart of `declareBindingName` — every leaf identifier in a
  // destructuring pattern gets a `destructureFrom` write (resolved lazily by `replayPath`, see
  // `destructureValues`), carrying the full `path` of member keys from `sourceExpr` down to that
  // leaf, so a nested pattern (`const { a: { b } } = x;` → `["a", "b"]`) resolves through every
  // level (round 62), plus one default per level (`{ a: { b = "x" } = {} }` → `[aDefault,
  // bDefault]`, round 63 — round 62 kept only the leaf's) for `defaultedValues` to apply when —
  // and only when — that level's key is provably absent from a fully known container. An object
  // pattern's key is the alias's property name if any, else the shorthand name itself; an array
  // pattern's key is the element's index as a string, the same key `arr[0]` reads by. A rest
  // element (`{ a, ...rest }` / `[a, ...rest]`) is a binding whose *members* read through to the
  // source minus its siblings' keys, or shifted past its own position (round 63).
  function bindingElementKey(el, position, isObject) {
    if (!isObject) return String(position);
    const propKey = el.propertyName || el.name;
    return ts.isIdentifier(propKey) || ts.isStringLiteral(propKey) || ts.isNumericLiteral(propKey) ? propKey.text : null;
  }

  function attachBindingPatternWrites(pattern, scope, mutable, sourceExpr, atPos, path = [], defaults = []) {
    const isObject = ts.isObjectBindingPattern(pattern);
    let index = 0;
    for (const el of pattern.elements) {
      const position = index++;
      if (ts.isOmittedExpression(el)) continue;
      if (el.dotDotDotToken) {
        if (!ts.isIdentifier(el.name)) continue; // `...[a, b]` — a pattern inside a rest: not modeled
        const b = analysis.binding(el.name.text, scope, mutable, false); // already registered
        const d = { sourceExpr, path, defaults, atPos };
        if (isObject) {
          d.restOmit = new Set();
          let sibling = 0;
          for (const other of pattern.elements) {
            const key = other === el || ts.isOmittedExpression(other) ? null : bindingElementKey(other, sibling, true);
            sibling++;
            if (key !== null) d.restOmit.add(key);
          }
        } else {
          d.restSkip = position;
        }
        b.writes.push({ pos: el.name.getStart(sf), own: true, destructureFrom: d });
        continue;
      }
      const key = bindingElementKey(el, position, isObject);
      if (key === null) continue; // a computed property name has no statically-known key
      const fullPath = [...path, key];
      const fullDefaults = [...defaults, el.initializer || null];
      if (ts.isIdentifier(el.name)) {
        const b = analysis.binding(el.name.text, scope, mutable, false); // already registered
        b.writes.push({
          pos: el.name.getStart(sf),
          own: true,
          destructureFrom: { sourceExpr, path: fullPath, defaults: fullDefaults, atPos },
        });
      } else {
        attachBindingPatternWrites(el.name, scope, mutable, sourceExpr, atPos, fullPath, fullDefaults);
      }
    }
  }

  function collectDeclarationList(declList, containerNode, lexicalScope, isExported) {
    const isVar = (declList.flags & (ts.NodeFlags.Let | ts.NodeFlags.Const)) === 0;
    const mutable = (declList.flags & ts.NodeFlags.Const) === 0;
    const scope = isVar ? nearestFunctionScope(containerNode) || sf : lexicalScope;
    for (const decl of declList.declarations) {
      if (!ts.isIdentifier(decl.name)) {
        if (decl.initializer) attachBindingPatternWrites(decl.name, scope, mutable, decl.initializer, decl.name.getStart(sf));
        continue;
      }
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
    } else if (isFunctionLike(node) && node.parameters) {
      // The function node itself is every parameter's own scope, for both braced and concise
      // bodies alike — see `nearestScope`'s matching case for why this must be a scope distinct
      // from the function body's own `Block` (round 51).
      const scope = node;
      for (const param of node.parameters) {
        if (!param.initializer) continue;
        if (ts.isIdentifier(param.name)) {
          // Unlike a declaration's own initializer above, a parameter default's write stays
          // unconditionally `own: true` — it isn't reached through ordinary statement control
          // flow at all (whether it applies depends on whether the caller omitted the argument,
          // not on any AST ancestry `isDeterministicWrite` could see), and there's exactly one
          // such write per parameter to reason about.
          const b = analysis.binding(param.name.text, scope, true, false); // already registered above
          b.writes.push({ pos: param.name.getStart(sf), expr: param.initializer, node: param, own: true });
        } else {
          // `function f({ provider } = { provider: "openai" })` — the pattern's default is the
          // destructuring source, exactly like a declaration's initializer (round 62).
          attachBindingPatternWrites(param.name, scope, true, param.initializer, param.name.getStart(sf));
        }
      }
    } else if (ts.isBinaryExpression(node) && ts.isIdentifier(node.left)) {
      const op = node.operatorToken.kind;
      const decl = analysis.resolveDecl(node, node.left.text);
      if (decl && decl.mutable) {
        if (op === ts.SyntaxKind.EqualsToken) {
          decl.writes.push({ pos: node.left.getStart(sf), expr: node.right, node, own: false });
        } else if (COMPOUND_STRING_OPERATORS.has(op)) {
          decl.writes.push({ pos: node.left.getStart(sf), rhsExpr: node.right, node, own: false, compoundOp: op });
        } else if (COMPOUND_CONDITIONAL_OPERATORS.has(op)) {
          decl.writes.push({ pos: node.left.getStart(sf), rhsExpr: node.right, node, own: false, forceConditional: true });
        }
      }
    } else if (
      ts.isBinaryExpression(node) &&
      (ts.isPropertyAccessExpression(node.left) || ts.isElementAccessExpression(node.left))
    ) {
      // `config.provider = ...` / `config.llm.provider += ...` / `config[KEY] = ...` / `arr[0] = ...`
      // — a member mutation at any depth, recorded on the *root* binding with its access chain
      // (keys resolved lazily by `memberKeys`, since a computed key can't be folded before every
      // write is collected), with the same operator set an ordinary binding gets: `+=` reads the
      // pre-write value, `||=`/`&&=`/`??=` stay always-conditional. A namespace import, TS
      // `enum`, or TS `namespace` can't be mutated this way (it's a compile error), and
      // `this.x = ...` has no binding at all, so nothing is recorded for those.
      const op = node.operatorToken.kind;
      const chain = [];
      let root = node.left;
      while (ts.isPropertyAccessExpression(root) || ts.isElementAccessExpression(root)) {
        chain.unshift(root);
        root = root.expression;
        while (ts.isParenthesizedExpression(root) || TRANSPARENT_WRAPPER_KINDS.has(root.kind)) root = root.expression;
      }
      const objDecl = ts.isIdentifier(root) ? analysis.resolveDecl(root, root.text) : null;
      if (objDecl && !objDecl.namespaceOf && !objDecl.enumNode && !objDecl.tsNamespace) {
        if (!objDecl.memberWrites) objDecl.memberWrites = [];
        const pos = node.left.getStart(sf);
        if (op === ts.SyntaxKind.EqualsToken) {
          objDecl.memberWrites.push({ pos, chain, expr: node.right, node, own: false });
        } else if (COMPOUND_STRING_OPERATORS.has(op)) {
          objDecl.memberWrites.push({ pos, chain, rhsExpr: node.right, node, own: false, compoundOp: op });
        } else if (COMPOUND_CONDITIONAL_OPERATORS.has(op)) {
          objDecl.memberWrites.push({ pos, chain, rhsExpr: node.right, node, own: false, forceConditional: true });
        }
      }
    }
    ts.forEachChild(node, visit);
  }

  visit(sf);
  for (const byName of analysis.declsByScope.values()) {
    for (const decls of byName.values()) {
      for (const d of decls) {
        d.writes.sort((a, b) => a.pos - b.pos);
        if (d.memberWrites) d.memberWrites.sort((a, b) => a.pos - b.pos);
      }
    }
  }
}

/** Registers every named import as a module-level binding whose sole "write" is a *lazy*
 * `redirect` (resolved on demand by `redirectValues`, not eagerly here — round 46: eager
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
      if (node.importClause.namedBindings && ts.isNamespaceImport(node.importClause.namedBindings)) {
        // `import * as providers from "./providers"` — `providers` itself never folds to a string
        // (it isn't a value at all, just a namespace object), so it's registered with no writes of
        // its own; `namespaceOf` is read directly by `exprValues` when a later
        // `providers.someExport` needs to resolve *through* it into the source module's own export
        // graph, reusing `resolveExport` exactly as an ordinary named import already does (round
        // 58).
        const localName = node.importClause.namedBindings.name.text;
        const d = { name: localName, scope: sf, mutable: false, writes: [], namespaceOf: sourcePath };
        analysis.scopeDecls(sf).set(localName, [d]);
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
        decl: { name: "default", scope: sf, mutable: false, writes: [{ pos: node.expression.getStart(sf), expr: node.expression, node, own: true }] },
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
    // Fold every expression node — except an identifier that isn't a *reference* (a declaration
    // name, a parameter name, a destructuring alias key, an enum/class member name, ...): those
    // name a binding rather than read one, and folding them anyway reported whatever a same-named
    // binding happened to hold at that position — a declaration name "resolving to its own
    // initializer", or worse, an alias key `{ primaryProvider: provider }` reporting an unrelated
    // outer `primaryProvider`'s value (round 62). A shorthand property (`{ role }`) and a bare
    // reference both still land in `values`, since both *are* references.
    ts.forEachChild(sf, function visit(node) {
      if (!ts.isIdentifier(node) || isIdentifierReference(node)) foldExpr(analysis, node);
      ts.forEachChild(node, visit);
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
  // Both halves of a binding element name nothing readable: the bound name, and an alias's
  // *property key* (`{ primaryProvider: provider }` — `primaryProvider` is a key into the source,
  // not a variable; folding it as one would report an unrelated same-named outer binding's value
  // at that position, round 62).
  if (ts.isBindingElement(p) && (p.name === node || p.propertyName === node)) return false;
  if (
    (ts.isFunctionDeclaration(p) ||
      ts.isFunctionExpression(p) ||
      ts.isClassDeclaration(p) ||
      ts.isClassExpression(p) ||
      ts.isEnumDeclaration(p) ||
      ts.isEnumMember(p) ||
      ts.isModuleDeclaration(p) ||
      ts.isPropertyDeclaration(p) ||
      ts.isMethodDeclaration(p) ||
      ts.isGetAccessor(p) ||
      ts.isSetAccessor(p)) &&
    p.name === node
  ) {
    return false;
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
