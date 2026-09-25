import { useEffect, useMemo, useState } from "react";
import { resolveIconCandidates } from "../../utils/websiteIcon.js";
import { loadIcon } from "../../utils/iconCache.js";
import "./AssetIcon.css";

/**
 * A market instrument's icon, resolved from its `ticker` and `website` via
 * resolveIconCandidates (Brandfetch by ticker, then Google's
 * favicon-by-domain, then a locally hosted SVG override — see
 * websiteIcon.js) — shared by HoldingTickerPage's title icon (32px) and
 * TopbarSearch's result dropdown (16px) rather than each resolving/
 * rendering it separately. Each candidate is resolved through iconCache.js's
 * `loadIcon` rather than a plain `<img src>`, so a repeat view of the same
 * ticker (a page refresh, a different page, tomorrow) is served from this
 * browser's own IndexedDB-cached copy instead of re-hitting Brandfetch/
 * Google every time — see equicast-support#233, since neither service
 * reliably sends long-lived `Cache-Control` for the browser's native HTTP
 * cache to rely on. `loadIcon` resolving to `null` (a real "no icon here")
 * advances to the next candidate, same as this used to rely on `<img>`'s
 * own `onError`; that `onError` is kept too, as a fallback for a resolved
 * source that still fails to render (a corrupt cached blob, or a
 * CORS-blocked candidate's raw URL 404ing once handed to the browser
 * directly — see loadIcon's own docstring for when that happens). Renders a
 * same-sized blank placeholder (rather than nothing) while a candidate is
 * still resolving, once every candidate has failed, or when there was
 * nothing to try in the first place (e.g. an FX pair with no ticker/website
 * and no override) — see equicast-support#178 — so callers can render it
 * unconditionally without the row's other columns shifting to fill the gap
 * in a flex/grid layout. `size` (px) sets the rendered dimensions; the icon
 * is always requested at a fixed 128px regardless of `size` and left to the
 * browser to downscale, since most providers don't reliably have anything
 * sharper than that to serve anyway.
 *
 * @param {{ ticker?: string|null, website?: string|null, size?: number }} props
 */
function AssetIcon({ ticker, website, size = 24, className, ...rest }) {
  const candidates = useMemo(
    () => resolveIconCandidates(ticker, website, { size: 128 }),
    [ticker, website]
  );
  const [attempt, setAttempt] = useState(0);
  const [resolved, setResolved] = useState(null);

  // A different instrument (new ticker/website) means a fresh cascade —
  // otherwise a previous instrument's exhausted attempt count would carry
  // over and skip candidates that were never actually tried for this one.
  // Clearing `resolved` too avoids briefly showing the previous
  // instrument's icon under the new one's ticker/website while the new
  // cascade resolves.
  useEffect(() => {
    setAttempt(0);
    setResolved(null);
  }, [candidates]);

  useEffect(() => {
    const url = candidates[attempt];
    if (!url) return;

    let cancelled = false;
    loadIcon(url).then((result) => {
      if (cancelled) return;
      if (result) {
        setResolved(result);
      } else {
        setAttempt((current) => current + 1);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [candidates, attempt]);

  // Revokes the previous object URL exactly when it's superseded by a new
  // one, or on unmount — a `loadIcon` cache hit/fresh fetch both hand back
  // an object URL that would otherwise leak for the life of the tab.
  useEffect(() => {
    return () => {
      if (resolved?.isObjectUrl) {
        URL.revokeObjectURL(resolved.src);
      }
    };
  }, [resolved]);

  const iconClassName = ["ec-asset-icon", className].filter(Boolean).join(" ");

  if (!resolved) {
    return (
      <span
        aria-hidden="true"
        className={iconClassName}
        style={{ width: size, height: size }}
        {...rest}
      />
    );
  }

  return (
    <img
      src={resolved.src}
      alt=""
      width={size}
      height={size}
      className={iconClassName}
      onError={() => {
        setResolved(null);
        setAttempt((current) => current + 1);
      }}
      {...rest}
    />
  );
}

export default AssetIcon;
