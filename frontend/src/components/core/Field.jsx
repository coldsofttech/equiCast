import "./Field.css";

/**
 * `TextField`/`SelectField`/`TextAreaField`: three thin label+input+error
 * wrappers sharing one layout (Field.css) instead of three near-identical
 * components — every account/pie form field is one of these three DOM
 * elements, nothing else. Each forwards unknown props straight to the
 * underlying native element, so callers use them exactly like the native
 * input/select/textarea plus `label`/`error`/`hint`.
 */

function FieldShell({ id, label, error, hint, required, children }) {
  return (
    <div className="ec-field">
      <label htmlFor={id} className="ec-field-label">
        {label}
        {required && (
          <span className="ec-field-required" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </label>
      {children}
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

export function TextField({ id, label, error, hint, required, className, ...rest }) {
  return (
    <FieldShell id={id} label={label} error={error} hint={hint} required={required}>
      <input
        id={id}
        className={["ec-input", error && "has-error", className].filter(Boolean).join(" ")}
        required={required}
        aria-invalid={error ? "true" : undefined}
        {...rest}
      />
    </FieldShell>
  );
}

export function SelectField({ id, label, error, hint, required, className, children, ...rest }) {
  return (
    <FieldShell id={id} label={label} error={error} hint={hint} required={required}>
      <select
        id={id}
        className={["ec-select", error && "has-error", className].filter(Boolean).join(" ")}
        required={required}
        aria-invalid={error ? "true" : undefined}
        {...rest}
      >
        {children}
      </select>
    </FieldShell>
  );
}

export function TextAreaField({ id, label, error, hint, required, className, ...rest }) {
  return (
    <FieldShell id={id} label={label} error={error} hint={hint} required={required}>
      <textarea
        id={id}
        className={["ec-textarea", error && "has-error", className].filter(Boolean).join(" ")}
        required={required}
        aria-invalid={error ? "true" : undefined}
        {...rest}
      />
    </FieldShell>
  );
}
