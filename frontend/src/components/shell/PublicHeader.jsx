import { Link } from "react-router-dom";
import Logo from "../brand/Logo.jsx";
import ThemeToggle from "./ThemeToggle.jsx";
import "./PublicHeader.css";

/**
 * The signed-out header row shared by SignInScreen, PrivacyPolicyPage, and
 * TermsAndConditionsPage — the equiCast logo (linked back to "/") plus the
 * theme toggle, sticky at the top of the viewport. One component instead
 * of three near-identical copies, so all three signed-out pages stay
 * pixel-identical (logo position, height, sticky behavior) instead of
 * silently drifting apart the way the old per-page copies did.
 */
function PublicHeader() {
  return (
    <header className="ec-public-header">
      <Link to="/" className="ec-public-header-logo-link" aria-label="Go to equiCast">
        <Logo />
      </Link>
      <ThemeToggle />
    </header>
  );
}

export default PublicHeader;
