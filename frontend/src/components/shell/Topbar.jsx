import { useAuth0 } from "@auth0/auth0-react";
import Logo from "../brand/Logo.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import "./Topbar.css";

/**
 * Brand mark, the signed-in user's default currency (the one real
 * end-to-end proof from Phase 0's identity wiring — see useCurrentUser),
 * theme toggle, and log out. Only rendered once RequireAuth has already
 * gated the tree, so useAuth0()/useCurrentUser() always have a real
 * session to work with.
 */
function Topbar() {
  const { logout } = useAuth0();
  const { profile } = useCurrentUser();

  return (
    <header className="ec-topbar">
      <Logo />
      <div className="ec-topbar-actions">
        {profile && <span className="ec-topbar-currency">{profile.default_currency}</span>}
        <ThemeToggle />
        <button
          type="button"
          className="ec-topbar-logout"
          onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
        >
          Log out
        </button>
      </div>
    </header>
  );
}

export default Topbar;
