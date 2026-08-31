import "./Badge.css";

/**
 * Small labeled tag — account_type/currency/transaction_type on accounts,
 * asset_class on pie holdings. `tone` picks the soft-background/soft-text
 * token pair tokens.css already defines for exactly this purpose.
 *
 * @param {{ tone?: "neutral" | "accent" | "success" | "warning" | "danger" | "info" | "purple" }} props
 */
function Badge({ tone = "neutral", className, children }) {
  return (
    <span className={["ec-badge", `ec-badge-${tone}`, className].filter(Boolean).join(" ")}>
      {children}
    </span>
  );
}

export default Badge;
