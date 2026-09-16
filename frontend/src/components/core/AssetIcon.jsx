import { useEffect, useMemo, useState } from "react";
import { resolveIconCandidates } from "../../utils/websiteIcon.js";
import "./AssetIcon.css";

/**
 * A market instrument's icon, resolved from its `ticker` and `website`
 * via resolveIconCandidates (Brandfetch by ticker, then Google's
 * favicon-by-domain, then a locally hosted SVG override — see
 * websiteIcon.js) — shared by HoldingTickerPage's title icon (32px) and
 * TopbarSearch's result dropdown (16px) rather than each resolving/
 * rendering it separately. Since a browser `<img>` can only ever try one
 * URL at a time, this walks the candidate list itself: each failed load
 * (`onError`) advances to the next candidate, and the icon renders
 * nothing once every candidate has failed (or there was nothing to try
 * in the first place, e.g. an FX pair with no ticker/website and no
 * override) — so callers can render it unconditionally either way.
 * `size` (px) sets the rendered dimensions; the icon is always requested
 * at a fixed 128px regardless of `size` and left to the browser to
 * downscale, since most providers don't reliably have anything sharper
 * than that to serve anyway — the browser's own HTTP cache keeps repeat
 * requests for the same ticker free.
 *
 * @param {{ ticker?: string|null, website?: string|null, size?: number }} props
 */
function AssetIcon({ ticker, website, size = 24, className, ...rest }) {
  const candidates = useMemo(
    () => resolveIconCandidates(ticker, website, { size: 128 }),
    [ticker, website]
  );
  const [attempt, setAttempt] = useState(0);

  // A different instrument (new ticker/website) means a fresh cascade —
  // otherwise a previous instrument's exhausted attempt count would carry
  // over and skip candidates that were never actually tried for this one.
  useEffect(() => {
    setAttempt(0);
  }, [ticker, website]);

  const iconUrl = candidates[attempt];
  if (!iconUrl) return null;

  return (
    <img
      src={iconUrl}
      alt=""
      width={size}
      height={size}
      className={["ec-asset-icon", className].filter(Boolean).join(" ")}
      onError={() => setAttempt((current) => current + 1)}
      {...rest}
    />
  );
}

export default AssetIcon;
