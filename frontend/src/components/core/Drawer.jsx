import { useEffect } from "react";
import { createPortal } from "react-dom";
import "./Drawer.css";

/**
 * Same open/onClose/title/children/footer contract as Modal, but slides in
 * from the right edge instead of centering — used for the accounts CRUD
 * forms/confirmations (AccountsListPage, AccountDetailPage) instead of
 * Modal. Portalled into `document.body` for the same reason Modal is (not
 * clipped by an ancestor's `overflow`), and renders nothing when closed so
 * its content/form state doesn't persist between opens.
 */
function Drawer({ open, onClose, title, children, footer }) {
  useEffect(() => {
    if (!open) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="ec-drawer-backdrop" onClick={onClose}>
      <div
        className="ec-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ec-drawer-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="ec-drawer-head">
          <h2 id="ec-drawer-title" className="ec-drawer-title">
            {title}
          </h2>
          <button type="button" className="ec-drawer-close" onClick={onClose} aria-label="Close">
            <i className="bi bi-x-lg" aria-hidden="true" />
          </button>
        </div>
        <div className="ec-drawer-body">{children}</div>
        {footer && <div className="ec-drawer-footer">{footer}</div>}
      </div>
    </div>,
    document.body
  );
}

export default Drawer;
