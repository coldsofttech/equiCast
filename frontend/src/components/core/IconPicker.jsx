import "./IconPicker.css";

/**
 * Generic bootstrap-icons picker: a labeled grid of `icons` (bare names,
 * e.g. "pie-chart-fill" — see components/core/Field.jsx's FieldShell for
 * the label/error/hint layout this mirrors) rendered as a single-select
 * `radiogroup`. Callers own what `icons` list to offer (e.g.
 * config/portfolioIcons.js's PORTFOLIO_ICON_OPTIONS) — this component
 * knows nothing about any particular feature's icon set.
 *
 * @param {{
 *   id: string,
 *   label: string,
 *   icons: string[],
 *   value?: string,
 *   onChange: (icon: string) => void,
 *   required?: boolean,
 *   error?: string,
 *   hint?: string,
 * }} props
 */
function IconPicker({ id, label, icons, value, onChange, required, error, hint }) {
  const labelId = `${id}-label`;
  return (
    <div className="ec-field">
      <span id={labelId} className="ec-field-label">
        {label}
        {required && (
          <span className="ec-field-required" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </span>
      <div id={id} className="ec-icon-picker" role="radiogroup" aria-labelledby={labelId}>
        {icons.map((icon) => (
          <button
            key={icon}
            type="button"
            role="radio"
            aria-checked={value === icon}
            aria-label={icon}
            title={icon}
            className={`ec-icon-picker-option${value === icon ? " is-selected" : ""}`}
            onClick={() => onChange(icon)}
          >
            <i className={`bi bi-${icon}`} aria-hidden="true" />
          </button>
        ))}
      </div>
      {error ? (
        <span className="ec-field-error" role="alert">
          {error}
        </span>
      ) : (
        hint && <span className="ec-field-hint">{hint}</span>
      )}
    </div>
  );
}

export default IconPicker;
