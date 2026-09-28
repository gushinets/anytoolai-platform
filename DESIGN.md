---
version: alpha
name: "AnytoolAI web products"
description: "A focused dark workbench for freelancers turning client material into usable deliverables."
colors:
  background: "#0F0C29"
  backgroundSecondary: "#1A1550"
  text: "#F0EFF8"
  accent: "#818CF8"
  teal: "#5EEAD4"
  success: "#34D399"
  error: "#F87171"
  warning: "#FBBF24"
typography:
  body:
    fontFamily: "DM Sans, Noto Sans, system-ui, sans-serif"
  heading:
    fontFamily: "Cabinet Grotesk, DM Sans, Noto Sans, system-ui, sans-serif"
rounded:
  input: "8px"
  button: "12px"
  card: "18px"
  panel: "20px"
  hero: "24px"
omitted:
  - section: spacing
    reason: "The existing application uses route-level layout values rather than a spacing token scale."
components:
  button: {}
  card: {}
  textarea: {}
---

# AnytoolAI web product design

## Overview

The product screen should feel like a compact writing desk: source material and the finished text stay in sight together. The audience is freelancers preparing client-facing work. Product clarity leads; the purple-to-teal background is the signature, while forms and results stay quiet and readable. Avoid a chat transcript layout or a marketing hero inside the work area.

The canonical values live in [tokens.json](packages/frontend/shared-ui/src/tokens.json) and are exposed through [tokens.css](packages/frontend/shared-ui/src/tokens.css); this file records their use. Product-specific layouts must consume the existing variables. Supported interface locales are English, French, Italian, German, Spanish, Russian, and Portuguese, with English fallback; product text comes from each product's message files.

## Colors

The dark purple background carries the atmosphere. Translucent cards and subtle white borders separate working surfaces; light text carries content. Accent purple marks primary actions and focus. Teal is an occasional expressive highlight. Success, warning, and error colors carry state, not decoration. The current application has one dark theme.

## Typography

Cabinet Grotesk at strong weight marks headings; DM Sans with Noto Sans fallback carries controls and prose, including Cyrillic. Keep generated text readable at a natural line length. Labels stay compact but legible; avoid all-caps body copy.

## Layout

The shared page width caps at 1160px. Long forms use natural document scrolling. Every web product uses source data on the left and the result on the right at desktop widths, then stacks them below 860px. Both columns have equal width and use the same outer Card surface, radius, padding, and heading placement. Keep both panels in the document flow so neither clips at short heights or zoom. Inputs and actions must remain reachable on small screens.

## Elevation & Depth

The background gradient and translucent card surface provide depth. Cards use a subtle border and blur; persistent large shadows would compete with the text. Pending and error states stay in the result area without moving the source form.

## Shapes

Use the shared input, button, card, panel, and hero radii above. Keep forms, output cards, and buttons in the same family rather than inventing a second geometry for one product.

## Components

Shared `Button`, `Card`, and `TextArea` own the baseline. A primary button starts or repeats generation; secondary buttons copy or clear. Focus is visible with the accent outline. Busy controls retain their dimensions; disabled inputs remain visible. Field errors appear beside their field, and run errors retain a clear retry path. Result changes should preserve the previous successful text until replacement succeeds and identify when it came from earlier input.

## Do's and Don'ts

- Do keep the task and its generated artifact together while editing.
- Do use existing shared tokens and product-localized messages for new UI.
- Don't turn operational screens into a multi-step wizard for a single output.
- Don't hide user input while a run is pending or after a result appears.
