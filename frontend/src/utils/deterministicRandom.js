/**
 * A tiny deterministic PRNG (mulberry32), seeded from a string hash —
 * shared by every illustrative/dummy chart on the accounts pages
 * (AccountPriceChart, HoldingsHeatmap) so a given input always renders the
 * same synthetic shape instead of reshuffling on every re-render, without
 * pulling in a real random-number or charting library for what's
 * explicitly placeholder data.
 */

/** Small deterministic string hash, seeding mulberry32 below. */
export function hashSeed(str) {
  let h = 0;
  for (let i = 0; i < str.length; i += 1) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  return h >>> 0;
}

export function mulberry32(seed) {
  let a = seed;
  return function rand() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Convenience: a seeded rand() function straight from a string seed. */
export function seededRandom(seedLabel) {
  return mulberry32(hashSeed(seedLabel));
}
