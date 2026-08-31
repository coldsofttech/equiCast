import { useState } from "react";
import "./MenuBar.css";

/**
 * `items`: [{ id, label }, ...]. No routing wired up yet (that's a later
 * phase) — selecting an item just tracks which one is "active" locally, so
 * the visual state and the mobile collapse are both real and testable
 * without depending on react-router existing yet.
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
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`ec-menubar-item${item.id === activeId ? " is-active" : ""}`}
            onClick={() => handleSelect(item.id)}
            aria-current={item.id === activeId ? "page" : undefined}
          >
            {item.label}
          </button>
        ))}
      </div>
    </nav>
  );
}

export default MenuBar;
