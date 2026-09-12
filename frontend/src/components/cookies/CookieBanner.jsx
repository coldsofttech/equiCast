import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Button from "../core/Button.jsx";
import Drawer from "../core/Drawer.jsx";
import { getCookieConsent, setCookieConsent } from "../../utils/cookieConsent.js";
import "./CookieBanner.css";

const OPEN_PREFERENCES_EVENT = "ec:open-cookie-preferences";

/**
 * Reopens the preferences panel after the visitor has already made a
 * choice (so the bottom banner itself is gone) — CookieBanner is mounted
 * once at the app root (see App.jsx) and is the only listener, so this is
 * a lighter way for something far away in the tree (CookiePolicyPage's own
 * "Manage your cookie preferences" button) to reach it than threading
 * shared state/context through the whole app for one rarely-used trigger.
 */
export function openCookiePreferences() {
  window.dispatchEvent(new Event(OPEN_PREFERENCES_EVENT));
}

/** The three categories the preferences panel offers — see
 * cookieConsent.js's own docstring for why only "analytics" is a real,
 * savable choice; "necessary"/"functional" are `locked` (rendered as
 * "Always on", no switch) since there's nothing to meaningfully turn off. */
const CATEGORIES = [
  {
    key: "necessary",
    label: "Strictly necessary",
    locked: true,
    description:
      "Keeps you signed in (Auth0's own session) and remembers whatever choice you make here. equiCast can't function without these.",
  },
  {
    key: "functional",
    label: "Functional",
    locked: true,
    description:
      "Remembers your theme and hide-balances choice, and caches your accounts, holdings, prices and dividends on your own device so pages load instantly instead of re-fetching from the API every visit. None of it leaves your device or is used to track you elsewhere.",
  },
  {
    key: "analytics",
    label: "Analytics",
    locked: false,
    description:
      "equiCast doesn't use analytics or advertising cookies today. This is here for if that ever changes — off by default, and only ever on if you turn it on.",
  },
];

/**
 * Bottom consent banner, mounted once at the app root (App.jsx) so it
 * shows on both the logged-out sign-in screen and every signed-in page —
 * a cookie choice has to be offered before sign-in, not after. Shows
 * itself only while `getCookieConsent()` is `null` (no choice made yet);
 * once a choice is recorded it hides for good until localStorage is
 * cleared. The "Manage preferences" panel (a Drawer, per-category
 * switches) stays reachable afterward too, via `openCookiePreferences()`.
 */
function CookieBanner() {
  const [consent, setConsentState] = useState(() => getCookieConsent());
  const [isManaging, setIsManaging] = useState(false);
  const [draftAnalytics, setDraftAnalytics] = useState(false);

  useEffect(() => {
    const handleOpen = () => {
      setDraftAnalytics(getCookieConsent()?.analytics ?? false);
      setIsManaging(true);
    };
    window.addEventListener(OPEN_PREFERENCES_EVENT, handleOpen);
    return () => window.removeEventListener(OPEN_PREFERENCES_EVENT, handleOpen);
  }, []);

  const acceptAll = () => {
    setCookieConsent({ analytics: true });
    setConsentState({ analytics: true });
    setIsManaging(false);
  };

  const rejectNonEssential = () => {
    setCookieConsent({ analytics: false });
    setConsentState({ analytics: false });
    setIsManaging(false);
  };

  const openManage = () => {
    setDraftAnalytics(consent?.analytics ?? false);
    setIsManaging(true);
  };

  const savePreferences = () => {
    setCookieConsent({ analytics: draftAnalytics });
    setConsentState({ analytics: draftAnalytics });
    setIsManaging(false);
  };

  return (
    <>
      {consent === null && (
        <div className="ec-cookie-banner" role="dialog" aria-label="Cookie notice">
          <p className="ec-cookie-banner-text">
            equiCast uses essential cookies and local storage to keep you signed in and remember
            your preferences. See the <Link to="/cookie-policy">Cookie Policy</Link> for the full
            breakdown, or choose below.
          </p>
          <div className="ec-cookie-banner-actions">
            <Button variant="ghost" size="sm" onClick={rejectNonEssential}>
              Reject non-essential
            </Button>
            <Button variant="secondary" size="sm" onClick={openManage}>
              Manage preferences
            </Button>
            <Button variant="primary" size="sm" onClick={acceptAll}>
              Accept all
            </Button>
          </div>
        </div>
      )}

      <Drawer
        open={isManaging}
        onClose={() => setIsManaging(false)}
        title="Cookie preferences"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsManaging(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={savePreferences}>
              Save preferences
            </Button>
          </>
        }
      >
        <div className="ec-cookie-categories">
          {CATEGORIES.map((category) => (
            <div className="ec-cookie-category" key={category.key}>
              <div className="ec-cookie-category-head">
                <span className="ec-cookie-category-label">{category.label}</span>
                {category.locked ? (
                  <span className="ec-cookie-category-locked">Always on</span>
                ) : (
                  <label className="ec-cookie-switch">
                    <input
                      type="checkbox"
                      checked={draftAnalytics}
                      onChange={(event) => setDraftAnalytics(event.target.checked)}
                      aria-label={category.label}
                    />
                    <span className="ec-cookie-switch-track" aria-hidden="true" />
                  </label>
                )}
              </div>
              <p className="ec-cookie-category-desc">{category.description}</p>
            </div>
          ))}
        </div>
      </Drawer>
    </>
  );
}

export default CookieBanner;
