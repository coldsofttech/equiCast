import { Link } from "react-router-dom";
import Logo from "../brand/Logo.jsx";
import Badge from "../core/Badge.jsx";
import HideBalancesToggle from "./HideBalancesToggle.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import TopbarSearch from "./TopbarSearch.jsx";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import useOnlineStatus from "../errors/useOnlineStatus.js";
import UserMenu from "./UserMenu.jsx";
import "./Topbar.css";

/**
 * Brand mark; the ticker search box; the signed-in user's default currency
 * (the one real end-to-end proof from Phase 0's identity wiring — see
 * useCurrentUser) as a clearly-labeled pill with a currency icon; the
 * hide-balances toggle (blurs every currency value app-wide — see
 * HideBalancesToggle); theme toggle; and the account menu (avatar,
 * Accounts, Settings, sign-out). `profile`/`setProfile` are passed into
 * UserMenu so its Settings drawer can update the same state this badge
 * reads, instead of each fetching its own copy and drifting out of sync
 * after a save.
 *
 * When the browser reports offline (`useOnlineStatus`), a slim banner
 * appears right below the bar instead of replacing the page — every price/
 * profile/dividend/etc. fetch already caches its last response in
 * IndexedDB (see utils/priceCache.js, eventsCache.js, sessionCache.js), so
 * a signed-in visitor can keep reading that cached data offline instead of
 * being locked out of the whole app. It recovers on its own once the
 * browser fires its own `online` event.
 */
function Topbar() {
  const { profile, setProfile } = useCurrentUser();
  const isOnline = useOnlineStatus();

  return (
    <>
      <header className="ec-topbar">
        <Link to="/dashboard" className="ec-topbar-logo-link" aria-label="Go to dashboard">
          <Logo />
        </Link>
        <div className="ec-topbar-actions">
          <TopbarSearch />
          {profile && (
            <Badge tone="accent" className="ec-topbar-currency" title="Default currency">
              <i className="bi bi-cash-coin" aria-hidden="true" />
              {profile.default_currency}
            </Badge>
          )}
          <HideBalancesToggle />
          <ThemeToggle />
          <UserMenu profile={profile} onProfileUpdate={setProfile} />
        </div>
      </header>
      {!isOnline && (
        <div className="ec-offline-banner" role="status">
          <i className="bi bi-wifi-off" aria-hidden="true" />
          You&rsquo;re offline — showing cached data. We&rsquo;ll reconnect automatically.
        </div>
      )}
    </>
  );
}

export default Topbar;
