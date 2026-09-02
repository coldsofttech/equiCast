import { useState } from "react";
import { NavLink } from "react-router-dom";
import "./MenuBar.css";

/**
 * `items`: [{ id, label, to? }, ...]. An item with `to` renders as a
 * react-router `NavLink` — active state comes from the URL, matching
 * `to` as a prefix so a sub-route (e.g. `/accounts/:id`) still shows
 * "Portfolio" active. An item without `to` falls back to the original
 * Phase 0 behavior: local "active" state with no real destination, for
 * placeholders (Watchlists/Search) that don't have a page yet.
 */
function MenuBar({ items, defaultActiveId }) {
  const [activeId, setActiveId] = useState(defaultActiveId ?? items[0]?.id);
  const [isOpen, setIsOpen] = useState(false);

  const handleSelect = (id) => {
    setActiveId(id);
    setIsOpen(false);
  };

  return (
    <nav className="ec-menubar" aria-label="Main">
      <button
        type="button"
        className="ec-menubar-toggle"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
      >
        <span>Menu</span>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
          <path
            d="M6 9l6 6 6-6"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <div className={`ec-menubar-nav${isOpen ? " is-open" : ""}`}>
        {items.map((item) =>
          item.to ? (
            <NavLink
              key={item.id}
              to={item.to}
              className={({ isActive }) =>
                `ec-menubar-item${isActive ? " is-active" : ""}`
              }
              onClick={() => setIsOpen(false)}
            >
              {item.label}
            </NavLink>
          ) : (
            <button
              key={item.id}
              type="button"
              className={`ec-menubar-item${item.id === activeId ? " is-active" : ""}`}
              onClick={() => handleSelect(item.id)}
              aria-current={item.id === activeId ? "page" : undefined}
            >
              {item.label}
            </button>
          )
        )}
      </div>
    </nav>
  );
}

export default MenuBar;
