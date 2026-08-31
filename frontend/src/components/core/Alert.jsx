import "./Alert.css";

/**
 * Inline banner for API errors/confirmations — generalizes the
 * `.ec-profile-error`/`.ec-signin-error` one-offs that predate this
 * library. `tone="danger"` is announced as `role="alert"`; the others are
 * `role="status"` since they aren't errors needing interruptive announcement.
 *
 * @param {{ tone?: "danger" | "success" | "info" }} props
 */
function Alert({ tone = "info", children }) {
  return (
    <div
      className={["ec-alert", `ec-alert-${tone}`].join(" ")}
      role={tone === "danger" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}

export default Alert;
