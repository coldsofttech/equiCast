import Logo from "../brand/Logo.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import UserMenu from "./UserMenu.jsx";
import "./Topbar.css";

/**
 * Brand mark, theme toggle, and the account menu (avatar + sign-out).
 * Search and notifications are real features (a search backend) that
 * later phases wire up, not chrome worth faking here.
 */
function Topbar() {
  return (
    <header className="ec-topbar">
      <Logo />
      <div className="ec-topbar-actions">
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}

export default Topbar;
