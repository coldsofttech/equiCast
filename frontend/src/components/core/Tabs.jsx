import "./Tabs.css";

/**
 * Generic tab strip — `tabs` is `[{ id, label, badge? }]`, `activeId` is
 * the currently selected tab's id, `onChange` fires with the clicked tab's
 * id. Renders only the tablist itself; callers render their own panel
 * content keyed off `activeId` (see WatchlistsPanel), since what a "tab
 * panel" holds differs per caller.
 *
 * @param {{
 *   tabs: { id: string, label: string, badge?: string|number }[],
 *   activeId: string,
 *   onChange: (id: string) => void,
 * }} props
 */
function Tabs({ tabs, activeId, onChange }) {
  return (
    <div className="ec-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === activeId}
          className={`ec-tabs-tab${tab.id === activeId ? " is-active" : ""}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {tab.badge != null && <span className="ec-tabs-badge">{tab.badge}</span>}
        </button>
      ))}
    </div>
  );
}

export default Tabs;
