import AppShell from "../components/shell/AppShell.jsx";
import "./ComingSoonPage.css";

/**
 * Shared placeholder body for a feature whose nav entry point (menu item +
 * route) ships before its real page does — GitHub issue #170 added
 * "Watchlists"/"Goals" to UserMenu ahead of either page actually existing
 * (Watchlists has a working backend with no frontend yet; Goals has
 * neither on `main`), so each renders this instead of 404ing.
 */
function ComingSoonPage({ eyebrow, title, icon, message }) {
  return (
    <AppShell eyebrow={eyebrow} title={title} centerTitle>
      <div className="ec-comingsoon">
        <div className="ec-comingsoon-icon" aria-hidden="true">
          <i className={`bi ${icon}`} />
        </div>
        <p className="ec-comingsoon-message">{message}</p>
      </div>
    </AppShell>
  );
}

export default ComingSoonPage;
