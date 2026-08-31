# Brand design decisions

Working history for equiCast's visual identity, kept alongside the standalone HTML mockups
in this directory so nothing gets lost once the corresponding Claude Artifacts expire.

## Decided

- **Palette**: Option A — reuses [Resource Planner](https://github.com/coldsofttech/resource-planner)'s
  OKLCH design tokens as-is (blue-violet accent, purple secondary). See `palette-options.html`
  for the full comparison against the two alternatives that were considered and dropped
  (Teal & Amber, Indigo & Gold).
- **Tagline**: **"Cast your equity forward."**
- **Icon**: **Candlestick Spear** — three real OHLC candlesticks (body + wick) ascending,
  the tallest candle's upper wick sharpened into a spearpoint breaking past the frame.
  Chosen from `logo-concepts-round3-final.html`'s four trading-specific directions (Price
  Bolt, Candlestick Spear, Target Dart, Breakout Flag).
- **Wordmark**: full "equiCast" text (`equi` regular + `Cast` bold, in the accent color) —
  not an initials monogram.
- **Icon + wordmark pairing**: the badge (icon) always accompanies the wordmark for full-size
  lockups, and stands alone for the compact mobile/favicon/app-icon export — mirroring
  Resource Planner's own icon+wordmark topbar pattern.

## Not yet produced

The three real export files this points to (`equicast-logo-light.svg`,
`equicast-logo-dark.svg`, `equicast-mark.svg`, self-contained, no external font/CSS
dependency) plus the CSS/React web component, built around the finalized Candlestick Spear
icon. Colors for the exports are exact OKLCH→sRGB conversions of Palette A's token values
(not eyeballed) — see the hard-coded hex values already used throughout `logo-concepts-*.html`
(`#4B65D9`/`#8B4EC4` light, `#7896FF`/`#B682ED` dark) — since SVG files used in email can't
rely on `oklch()` or CSS custom properties the way the live web app can.

## Files in this directory

| File | What it shows |
|---|---|
| `palette-options.html` | Three color palette candidates (A/B/C), each rendered live with real UI pieces in light and dark. |
| `logo-concepts-round1.html` | First icon pass (Bars & Ping) plus the original six-candidate tagline shortlist. |
| `logo-concepts-round2.html` | Second icon pass — three directions (Bars & Ping, Trend & Signal, Orbit & Satellite), tagline locked. |
| `logo-concepts-round3-final.html` | Third icon pass — four trading-specific directions (Price Bolt, **Candlestick Spear**, Target Dart, Breakout Flag). Candlestick Spear is the chosen final. |

Open any file directly in a browser (or via GitHub's raw view) to see the live preview —
they're self-contained, no build step.
