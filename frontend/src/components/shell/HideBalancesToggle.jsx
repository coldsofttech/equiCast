import { useEffect, useState } from "react";

const STORAGE_KEY = "ec-hide-balances";

function currentlyHidden() {
  return document.documentElement.getAttribute("data-hide-balances") === "true";
}

/**
 * Blurs every currency-denominated value across the app (dashboard,
 * account/pie/holding pages — anything wrapped in `components/core/
 * Balance.jsx`) without touching percentages or other stats, mirroring
 * Trading 212's balance-hiding eye icon. Same mechanism as ThemeToggle:
 * flips a `data-hide-balances` attribute on `<html>` (which `.ec-balance`'s
 * CSS rule reacts to — see styles/base.css) and persists the choice to
 * localStorage, matching the key index.html's inline bootstrap script
 * reads on the next load so there's no flash of visible balances before
 * React mounts. Initial state is read from the DOM (not defaulted to
 * shown), since that script already set the attribute before this
 * component ever mounts.
 */
function HideBalancesToggle() {
  const [hidden, setHidden] = useState(currentlyHidden);

  useEffect(() => {
    document.documentElement.setAttribute("data-hide-balances", String(hidden));
    try {
      localStorage.setItem(STORAGE_KEY, String(hidden));
    } catch {
      // Storage can be unavailable (private browsing, disabled cookies) —
      // the toggle still works for this page load, just doesn't persist.
    }
  }, [hidden]);

  return (
    <button
      type="button"
      className="ec-icon-btn"
      onClick={() => setHidden((current) => !current)}
      aria-label={hidden ? "Show balances" : "Hide balances"}
      title={hidden ? "Show balances" : "Hide balances"}
    >
      <i className={hidden ? "bi bi-eye-slash" : "bi bi-eye"} aria-hidden="true" />
    </button>
  );
}

export default HideBalancesToggle;
