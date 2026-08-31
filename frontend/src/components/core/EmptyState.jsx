import "./EmptyState.css";

/** "No accounts yet" / "No pies yet" / "No holdings yet" placeholder. */
function EmptyState({ title, description, action }) {
  return (
    <div className="ec-empty">
      <p className="ec-empty-title">{title}</p>
      {description && <p className="ec-empty-desc">{description}</p>}
      {action && <div className="ec-empty-action">{action}</div>}
    </div>
  );
}

export default EmptyState;
