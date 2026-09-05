import "./RangeSlider.css";

/**
 * A two-handle range slider over a fixed, ordered list of `steps`
 * (`{ value, label }`) rather than a continuous numeric range — lets a
 * caller lay out non-linear (e.g. log-spaced) breakpoints, like market
 * cap's $10M/$50M/.../$1T+, on an ordinary `<input type="range">` pair
 * without any log-scale math of its own. Two overlapping native range
 * inputs sharing one visual track (a standard technique for a dual-thumb
 * slider without a component-library dependency) — `lowIndex`/`highIndex`
 * index into `steps`, clamped against each other so the handles can't
 * cross.
 *
 * @param {{
 *   steps: { value: number, label: string }[],
 *   lowIndex: number,
 *   highIndex: number,
 *   onChange: (lowIndex: number, highIndex: number) => void,
 * }} props
 */
function RangeSlider({ steps, lowIndex, highIndex, onChange }) {
  const maxIndex = steps.length - 1;
  const pctLow = (lowIndex / maxIndex) * 100;
  const pctHigh = (highIndex / maxIndex) * 100;

  return (
    <div className="ec-range-slider">
      <div className="ec-range-slider-track">
        <div
          className="ec-range-slider-fill"
          style={{ left: `${pctLow}%`, right: `${100 - pctHigh}%` }}
        />
      </div>
      <input
        type="range"
        className="ec-range-slider-input"
        min={0}
        max={maxIndex}
        step={1}
        value={lowIndex}
        onChange={(event) => onChange(Math.min(Number(event.target.value), highIndex), highIndex)}
        aria-label="Minimum"
      />
      <input
        type="range"
        className="ec-range-slider-input"
        min={0}
        max={maxIndex}
        step={1}
        value={highIndex}
        onChange={(event) => onChange(lowIndex, Math.max(Number(event.target.value), lowIndex))}
        aria-label="Maximum"
      />
      <div className="ec-range-slider-labels">
        <span>{steps[lowIndex].label}</span>
        <span>{steps[highIndex].label}</span>
      </div>
    </div>
  );
}

export default RangeSlider;
