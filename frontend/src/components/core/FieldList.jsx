import "./FieldList.css";

/**
 * A plain label/value list for a "See all" Drawer's body (HoldingStatsPanel's
 * full metrics list, HoldingAboutSection's full company profile) — the
 * first "truncated section + See all -> Drawer" pattern in the app, so
 * shared here rather than left one-off. Skips any item whose `value` is
 * null/undefined/empty rather than rendering a "—" placeholder for every
 * absent optional field.
 *
 * @param {{ items: { label: string, value: string|number|null|undefined }[] }} props
 */
function FieldList({ items }) {
  const visible = items.filter((item) => item.value != null && item.value !== "");

  return (
    <dl className="ec-field-list">
      {visible.map((item) => (
        <div className="ec-field-list-item" key={item.label}>
          <dt className="ec-field-list-label">{item.label}</dt>
          <dd className="ec-field-list-value">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default FieldList;
