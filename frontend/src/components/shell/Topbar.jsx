import Logo from "../brand/Logo.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import UserMenu from "./UserMenu.jsx";
import "./Topbar.css";

/**
 * Brand mark, the signed-in user's default currency (the one real
 * end-to-end proof from Phase 0's identity wiring — see useCurrentUser),
 * theme toggle, and the account menu (avatar + sign-out).
 */
function Topbar() {
  const { profile } = useCurrentUser();

  return (
    <header className="ec-topbar">
      <Logo />
      <div className="ec-topbar-actions">
        {profile && <span className="ec-topbar-currency">{profile.default_currency}</span>}
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}

export default Topbar;
