import { Link } from "react-router-dom";
import Logo from "../brand/Logo.jsx";
import "./ErrorPage.css";

/**
 * Shared full-page layout for every error state (NotFoundPage,
 * ServiceUnavailablePage, AppErrorPage, OfflinePage) — deliberately
 * standalone, not wrapped in AppShell: AppShell's own Topbar fetches the
 * signed-in user's profile, which is exactly the kind of call that can be
 * what's failing (ServiceUnavailablePage) or unreachable (OfflinePage) in
 * the first place, and a 404/render-crash shouldn't depend on it
 * succeeding either. Only the brand mark, linked back to /dashboard, so
 * there's always one clear way out regardless of which of these fired.
 *
 * `icon` carries each page's own animated SVG (see NotFoundIcon.jsx and
 * siblings) — the one deliberately bold, page-specific element; title/
 * message stay in the app's plain interface voice (what happened, not an
 * apology), and `action` is optional since OfflinePage has nothing useful
 * for a person to click (it recovers on its own once the browser reports
 * being back online — see useOnlineStatus.js).
 */
function ErrorPage({ icon, title, message, action }) {
  return (
    <div className="ec-errorpage">
      <Link to="/dashboard" className="ec-errorpage-logo-link" aria-label="Go to dashboard">
        <Logo />
      </Link>
      <div className="ec-errorpage-body">
        <div className="ec-errorpage-icon" aria-hidden="true">
          {icon}
        </div>
        <h1 className="ec-errorpage-title">{title}</h1>
        <p className="ec-errorpage-message">{message}</p>
        {action && <div className="ec-errorpage-action">{action}</div>}
      </div>
    </div>
  );
}

export default ErrorPage;
