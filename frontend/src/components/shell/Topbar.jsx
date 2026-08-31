import Logo from "../brand/Logo.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import "./Topbar.css";

/**
 * Just the brand mark and the theme toggle for now — search, notifications,
 * and the user menu are real features (auth, search backend) that later
 * phases wire up, not chrome worth faking here.
 */
function Topbar() {
  return (
    <header className="ec-topbar">
      <Logo />
      <div className="ec-topbar-actions">
        <ThemeToggle />
      </div>
    </header>
  );
}

export default Topbar;
