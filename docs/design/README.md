# Brand design decisions

Working history for equiCast's visual identity, kept alongside the standalone HTML mockups
in this directory so nothing gets lost once the corresponding Claude Artifacts expire.

## Decided

- **Palette**: Option A — **Violet & Plum** (blue-violet accent, plum secondary). See
  `palette-options.html` for the full comparison against the two alternatives that were
  considered and dropped (Teal & Amber, Indigo & Gold).
- **Tagline**: **"Cast your equity forward."**
- **Icon**: **Candlestick Spear** — three real OHLC candlesticks (body + wick) ascending,
  the tallest candle's upper wick sharpened into a spearpoint breaking past the frame. See
  `logo-options.html` for the finalised lockup plus a recap of the alternative icon
  directions and taglines considered.
- **Wordmark**: full "equiCast" text (`equi` regular + `Cast` bold, in the accent color) —
  not an initials monogram.
- **Icon + wordmark pairing**: the badge (icon) always accompanies the wordmark for full-size
  lockups, and stands alone for the compact mobile/favicon/app-icon export.

## Not yet produced

The three real export files this points to (`equicast-logo-light.svg`,
`equicast-logo-dark.svg`, `equicast-mark.svg`, self-contained, no external font/CSS
dependency) plus the CSS/React web component, built around the finalised Candlestick Spear
icon in `logo-options.html`. Colors for the exports are exact OKLCH→sRGB conversions of
Palette A's token values (not eyeballed) — see the hard-coded hex values already used
throughout `logo-options.html` (`#4B65D9`/`#8B4EC4` light, `#7896FF`/`#B682ED` dark) — since
SVG files used in email can't rely on `oklch()` or CSS custom properties the way the live
web app can.

## Files in this directory

| File | What it shows |
|---|---|
| `palette-options.html` | Three color palette candidates (A/B/C) — **Option A finalised** — each rendered live with real UI pieces in light and dark. |
| `logo-options.html` | The finalised brand mark — Candlestick Spear icon, full lockup with the locked tagline, plus a recap of the alternative icon directions and taglines considered. Source of truth for the icon/wordmark/tagline. |

Open any file directly in a browser (or via GitHub's raw view) to see the live preview —
they're self-contained, no build step.
