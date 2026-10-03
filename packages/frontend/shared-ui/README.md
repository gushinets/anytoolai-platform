# Shared UI presentation contract

`src/tokens.json` is the canonical value source. `src/tokens.css` is hand-derived and checked by
`test/tokens.test.ts`; do not introduce a CSS token without its JSON value. This package depends
only on React and owns presentation. Product fields, validators, localization and scenario state
remain in the web host/product. These decisions revise Bundle 3 on 2026-10-02 for accessibility
and consistent typography; historical implementation plans remain historical.

## Color pairs and surfaces

- Primary Button: `onAccent` on `gradients.accent` (including normal, hover and focus). The
  decorative spinner's leading edge inherits this foreground only inside primary; secondary
  keeps its accent spinner. Disabled opacity is separate from available text contrast.
- `text` and `textSecondary` are supported on the dark page, one Card, and one nested
  `surfaceCard` field/placeholder or `surfaceHover` option. `textSecondary` alpha is 0.75.
  Selected options use `text`/`surfaceActive`, accent border and a checkmark. Never use
  `textDisabled` for an available option.
- Ordinary available text needs at least 4.5:1 after alpha composition. The token test samples
  all 1001 positions of the accent gradient and composes each supported base background with
  the card/nested/hover layers. Browser measurements must also cover the actual radial page
  glows, blur and hover at the relevant viewport; the bounded model is not permission to stack
  arbitrary glass layers or use these text tokens on arbitrary backgrounds.

## Typography

| Role | Family | Weight | Size / line-height |
|---|---|---|---|
| Display (`h1` default) | Cabinet Grotesk with body/Cyrillic fallback | 900 | 44px / 1.1; home 44–56px / 1.02 |
| Section (`h2`) | Body | 700 | 24px / 1.2 |
| Result subheading (`h3`) | Body | 700 | 18px / 1.3 |
| Body and native input | Body | normal | 16px / 1.5 |
| Long result text | Body | normal | 16px / 1.6 |
| Label | Body | 600 | 12px / inherited 1.5 |
| Helper/error explanation | Body | normal | 13px / 1.45 |

Keep semantic headings; these are presentation defaults, not new wrapper components. Web layout
loads DM Sans and DM Mono with next/font; Noto Sans (`--font-cyrillic`) covers Cyrillic. Display
falls back through the body/Cyrillic chain when Cabinet lacks a glyph. Do not replace font loading
or use Cabinet 900 for smaller section/result titles.

## Controls and textarea

Interactive controls have an **exterior minimum of 44px**, measured including padding/border.
Native field primitives and product tone/mode labels use border-box; radio options retain an 8px gap,
keyboard arrows and focus outlines. Multi-line labels grow instead of clipping. Do not apply a
global geometry reset to Cards. Native input/select/textarea and their error ARIA links remain.

Single-value Select uses `appearance: base-select` where supported: its dark picker is rendered
inside the browser page instead of a separate native popup window. Options have exterior 44px
targets; the selected option has a checkmark and the accent/onAccent pair. Native value/change,
labels and keyboard behavior remain. Older browsers and `multiple`/`size` listboxes keep the
existing native control. No JavaScript dropdown or UI dependency is needed.

Products choose textarea volume using native `rows` or their existing purpose-specific min-height:
use Input for short single values; 4–5 rows for a short message/notes; a larger field for a source
document. Client Update Writer uses 5 rows for progress, client message and billing notes, 4 for
reply goal. ProposalAI retains 144/120px and Brief Decoder 200px. Long input remains scrollable;
retain native resize where already available. Shared UI owns readable type and basic geometry,
not one fixed height for every product or an autosize dependency.

## Responsive workspace

The web host places input beside result on desktop, input first below 860px. Submit becomes full
width below 520px. Only the idle empty result placeholder has exterior min-height 120px below
860px; running/progress, errors and actual results retain their existing flow and grow with text.
An empty-to-result transition can increase page height: do not fix or clip real output to hide it.
Preserve visible keyboard focus, native Tab/Shift+Tab/arrows, label wrapping and reduced motion.

## Checks

Run `pnpm --filter @anytoolai/shared-ui test` for primitives, token parity and contrast. Run
`python scripts/agent/runner.py full-check` for integration. Review actual computed styles and PNGs
after changing a supported surface: automated axe incomplete contrast is not a passing result.
