/**
 * Squarified treemap layout (Bruls/Huizing/van Wijk) — lays out a list of
 * weighted items as non-overlapping rectangles tiling a `width` x `height`
 * container, keeping each rectangle's aspect ratio as close to square as
 * the weights allow (rather than a naive single row/column of slivers).
 * Used by HoldingsHeatmap so tile *area* is proportional to holding weight,
 * matching a standard market-heatmap look.
 */

function worstRatio(row, side) {
  const sum = row.reduce((a, b) => a + b, 0);
  const rmax = Math.max(...row);
  const rmin = Math.min(...row);
  return Math.max((side * side * rmax) / (sum * sum), (sum * sum) / (side * side * rmin));
}

/**
 * @param {Array<{area: number}>} items - pre-scaled so sum(area) === width * height; any
 *   other fields on each item are preserved onto its output rectangle.
 * @returns {Array<{x: number, y: number, w: number, h: number}>} same items, each with its
 *   laid-out rectangle merged in.
 */
export function squarify(items, x, y, width, height) {
  const result = [];
  let remaining = items;
  let rx = x;
  let ry = y;
  let rw = width;
  let rh = height;

  while (remaining.length > 0) {
    const side = Math.min(rw, rh);
    let row = remaining.slice(0, 1);
    let i = 1;
    while (i < remaining.length) {
      const nextRow = remaining.slice(0, i + 1);
      if (worstRatio(nextRow.map((it) => it.area), side) > worstRatio(row.map((it) => it.area), side)) {
        break;
      }
      row = nextRow;
      i += 1;
    }

    const rowSum = row.reduce((sum, it) => sum + it.area, 0);
    if (rw >= rh) {
      const colWidth = rowSum / rh;
      let cy = ry;
      for (const item of row) {
        const cellHeight = item.area / colWidth;
        result.push({ ...item, x: rx, y: cy, w: colWidth, h: cellHeight });
        cy += cellHeight;
      }
      rx += colWidth;
      rw -= colWidth;
    } else {
      const rowHeight = rowSum / rw;
      let cx = rx;
      for (const item of row) {
        const cellWidth = item.area / rowHeight;
        result.push({ ...item, x: cx, y: ry, w: cellWidth, h: rowHeight });
        cx += cellWidth;
      }
      ry += rowHeight;
      rh -= rowHeight;
    }
    remaining = remaining.slice(row.length);
  }

  return result;
}
