import Logo from "../brand/Logo.jsx";
import Badge from "../core/Badge.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import TopbarSearch from "./TopbarSearch.jsx";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import UserMenu from "./UserMenu.jsx";
import "./Topbar.css";

/**
 * Brand mark; the ticker search box; the signed-in user's default currency
 * (the one real end-to-end proof from Phase 0's identity wiring — see
 * useCurrentUser) as a clearly-labeled pill with a currency icon; theme
 * toggle; and the account menu (avatar, Accounts, Settings, sign-out).
 * `profile`/`setProfile` are passed into UserMenu so its Settings drawer
 * can update the same state this badge reads, instead of each fetching
 * its own copy and drifting out of sync after a save.
 */
function Topbar() {
  const { profile, setProfile } = useCurrentUser();

  return (
    <header className="ec-topbar">
      <Logo />
      <div className="ec-topbar-actions">
        <TopbarSearch />
        {profile && (
          <Badge tone="accent" className="ec-topbar-currency" title="Default currency">
            <i className="bi bi-cash-coin" aria-hidden="true" />
            {profile.default_currency}
          </Badge>
        )}
        <ThemeToggle />
        <UserMenu profile={profile} onProfileUpdate={setProfile} />
      </div>
    </header>
  );
}

export default Topbar;
