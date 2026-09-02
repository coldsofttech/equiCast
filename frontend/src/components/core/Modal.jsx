import { useEffect } from "react";
import { createPortal } from "react-dom";
import "./Modal.css";

/**
 * Portalled into `document.body` so an account/pie modal opened from deep
 * in a card list isn't clipped by an ancestor's `overflow`. Closes on Esc
 * or a backdrop click; a click inside the panel is stopped from bubbling
 * to the backdrop listener. Renders nothing when `open` is false rather
 * than hiding via CSS, so its content (and any form state inside) only
 * exists while actually open.
 */
function Modal({ open, onClose, title, children, footer }) {
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
    <div className="ec-modal-backdrop" onClick={onClose}>
      <div
        className="ec-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ec-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="ec-modal-head">
          <h2 id="ec-modal-title" className="ec-modal-title">
            {title}
          </h2>
          <button type="button" className="ec-modal-close" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
              <path
                d="M6 6l12 12M18 6L6 18"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
            </svg>
          </button>
        </div>
        <div className="ec-modal-body">{children}</div>
        {footer && <div className="ec-modal-footer">{footer}</div>}
      </div>
    </div>,
    document.body
  );
}

export default Modal;
