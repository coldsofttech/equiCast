import ICON_OVERRIDES from "../config/websiteIcons.json";

/**
 * Per-ticker overrides (config/websiteIcons.json) for cases the automated
 * providers get wrong: `website` corrects a profile's `website` field
 * pointing at the wrong domain for the Google-favicon fallback (e.g.
 * GOOGL's yfinance website is a shared Alphabet domain, not google.com —
 * Google's favicon service would otherwise return Alphabet's icon), and a
 * `source` starting with "/" points at a locally hosted SVG
 * (frontend/public) for a ticker neither Brandfetch nor Google serves
 * well. See resolveIconCandidates for where each fits in the fallback
 * order.
 */

function domainOf(website) {
  if (!website) return null;
  try {
    return new URL(website).hostname;
  } catch {
    return null;
  }
}

// A public client ID, not a secret — Brandfetch's own Logo Link CDN is
// designed to be called straight from the browser with this in the URL
// (see brandfetchIconUrl), same as Auth0's client ID or the GA
// measurement ID elsewhere in this app. One value baked into both the
// dev and prod frontend builds (see deploy.yml's VITE_BRANDFETCH_CLIENT_ID),
// sourced from the repo's BRANDFETCH_API_KEY secret.
const BRANDFETCH_CLIENT_ID = import.meta.env.VITE_BRANDFETCH_CLIENT_ID;

/**
 * Resolves a company logo URL via Brandfetch's free Logo API
 * (https://brandfetch.com/developers/logo-api), looked up directly by
 * ticker symbol — Brandfetch resolves stock tickers natively, so this
 * needs no `website` at all, and (unlike Google's favicon) serves an
 * actual logo rather than a small favicon. Returns null without a ticker
 * or without VITE_BRANDFETCH_CLIENT_ID configured (e.g. local dev with
 * no key set), so resolveIconCandidates falls straight through to
 * Google's favicon instead of requesting a guaranteed-401 URL.
 *
 * @param {string|null|undefined} ticker
 * @returns {string|null}
 */
export function brandfetchIconUrl(ticker) {
  if (!ticker || !BRANDFETCH_CLIENT_ID) return null;
  return `https://cdn.brandfetch.io/ticker/${encodeURIComponent(ticker.toUpperCase())}?c=${BRANDFETCH_CLIENT_ID}`;
}

/**
 * Resolves a favicon URL for a company website using Google's public
 * favicon-by-domain service — no API key, no backend involvement, and the
 * de facto standard trick for "give me this site's icon" (returns a
 * generic globe placeholder rather than an error for domains it can't
 * resolve, so callers don't need to special-case failures).
 *
 * @param {string|null|undefined} website
 * @param {{ size?: number }} [options]
 * @returns {string|null}
 */
export function websiteIconUrl(website, { size = 128 } = {}) {
  const domain = domainOf(website);
  if (!domain) return null;
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=${size}`;
}

/**
 * Resolves the ordered list of icon URLs AssetIcon should try in turn,
 * falling through to the next one on load failure: Brandfetch (by
 * ticker) first, then Google's favicon-by-domain (using ICON_OVERRIDES'
 * `website` override in place of `website` when set), then a locally
 * hosted SVG override (ICON_OVERRIDES' `source`) as the last resort for a
 * ticker neither automated provider serves well. Empty when there's
 * nothing to try at all (e.g. an FX pair with no ticker/website and no
 * override).
 *
 * @param {string|null|undefined} ticker
 * @param {string|null|undefined} website
 * @param {{ size?: number }} [options]
 * @returns {string[]}
 */
export function resolveIconCandidates(ticker, website, { size = 128 } = {}) {
  const override = ticker ? ICON_OVERRIDES[ticker.toUpperCase()] : null;
  const effectiveWebsite = override?.website ?? website;
  return [
    brandfetchIconUrl(ticker),
    websiteIconUrl(effectiveWebsite, { size }),
    override?.source?.startsWith("/") ? override.source : null,
  ].filter(Boolean);
}
