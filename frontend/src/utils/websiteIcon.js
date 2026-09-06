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
export function websiteIconUrl(website, { size = 64 } = {}) {
  if (!website) return null;
  let domain;
  try {
    domain = new URL(website).hostname;
  } catch {
    return null;
  }
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=${size}`;
}
