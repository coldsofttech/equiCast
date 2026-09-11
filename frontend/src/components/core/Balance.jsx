/**
 * Wraps a currency-denominated value (a formatted amount, a price, a
 * chart's currency legend/axis label, ...) so the app-wide "hide balances"
 * toggle (see components/shell/HideBalancesToggle.jsx, in the Topbar) can
 * blur it. Needs no JS/state here or in any caller — the blur is CSS-only,
 * driven by the `data-hide-balances` attribute HideBalancesToggle sets on
 * `<html>` (see styles/base.css's `.ec-balance` rule), the same DOM-
 * attribute pattern ThemeToggle uses for light/dark. Percentages and other
 * non-currency values are left alone by simply not being wrapped in this.
 *
 * `as` picks the rendered element (default `span`) for callers that need a
 * block-level wrapper (e.g. a `<div>` around a chart legend row) instead of
 * an inline one.
 */
function Balance({ as, className, children, ...rest }) {
  const Component = as || "span";
  return (
    <Component className={["ec-balance", className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </Component>
  );
}

export default Balance;
