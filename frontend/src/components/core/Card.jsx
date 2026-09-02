import "./Card.css";

/**
 * A plain surfaced container — `onClick` makes it a clickable card (used
 * for account/pie list rows) without pulling in a separate "ClickableCard"
 * variant; it stays a `<div>` either way since these are never form
 * submitters, and the caller adds `role="button"`/keyboard handling if it
 * needs to act as a real interactive control (see AccountsListPage).
 */
function Card({ className, children, ...rest }) {
  return (
    <div className={["ec-card", className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </div>
  );
}

export default Card;
