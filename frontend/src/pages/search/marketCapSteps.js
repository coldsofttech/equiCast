/**
 * Log-spaced breakpoints for SearchFilters' Market cap range slider —
 * market cap spans ~$1M to ~$3T across real tickers, so evenly-spaced
 * linear steps would make the small/mid-cap half of the range
 * unusable next to trillion-dollar mega-caps. `Infinity` as the last
 * step's value means "no upper bound" rather than a literal number to
 * send the backend.
 */
export const MARKET_CAP_STEPS = [
  { value: 0, label: "$0" },
  { value: 10_000_000, label: "$10M" },
  { value: 50_000_000, label: "$50M" },
  { value: 200_000_000, label: "$200M" },
  { value: 1_000_000_000, label: "$1B" },
  { value: 10_000_000_000, label: "$10B" },
  { value: 50_000_000_000, label: "$50B" },
  { value: 200_000_000_000, label: "$200B" },
  { value: 1_000_000_000_000, label: "$1T" },
  { value: Infinity, label: "$1T+" },
];

export const MARKET_CAP_MIN_INDEX = 0;
export const MARKET_CAP_MAX_INDEX = MARKET_CAP_STEPS.length - 1;

/**
 * `lowIndex`/`highIndex` (into MARKET_CAP_STEPS) -> the `minMarketCap`/
 * `maxMarketCap` searchTickers expects — `undefined` (omit the filter
 * entirely) at either end of the slider, since "$0" and "$1T+" both mean
 * "no bound here", not a literal 0 or a literal number to compare against.
 *
 * @param {number} lowIndex
 * @param {number} highIndex
 * @returns {{ minMarketCap: number|undefined, maxMarketCap: number|undefined }}
 */
export function marketCapRangeFromIndexes(lowIndex, highIndex) {
  const min = MARKET_CAP_STEPS[lowIndex].value;
  const max = MARKET_CAP_STEPS[highIndex].value;
  return {
    minMarketCap: min > 0 ? min : undefined,
    maxMarketCap: Number.isFinite(max) ? max : undefined,
  };
}

/**
 * The inverse of `marketCapRangeFromIndexes` — a `minMarketCap`/
 * `maxMarketCap` pair (e.g. parsed back out of the URL) -> the closest
 * enclosing slider index pair, so a shared/bookmarked/refreshed search
 * URL restores the same handle positions rather than resetting to the
 * full range. Snaps outward (floor for low, ceil for high) so the
 * restored range never excludes a ticker the URL's exact bounds would
 * have included.
 *
 * @param {number|undefined} minMarketCap
 * @param {number|undefined} maxMarketCap
 * @returns {{ lowIndex: number, highIndex: number }}
 */
export function indexesFromMarketCapRange(minMarketCap, maxMarketCap) {
  let lowIndex = MARKET_CAP_MIN_INDEX;
  if (minMarketCap != null) {
    for (let i = MARKET_CAP_MAX_INDEX; i >= 0; i -= 1) {
      if (MARKET_CAP_STEPS[i].value <= minMarketCap) {
        lowIndex = i;
        break;
      }
    }
  }

  let highIndex = MARKET_CAP_MAX_INDEX;
  if (maxMarketCap != null) {
    for (let i = MARKET_CAP_MIN_INDEX; i <= MARKET_CAP_MAX_INDEX; i += 1) {
      if (MARKET_CAP_STEPS[i].value >= maxMarketCap) {
        highIndex = i;
        break;
      }
    }
  }

  return { lowIndex, highIndex };
}
