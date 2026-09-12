import { Link } from "react-router-dom";
import Logo from "../brand/Logo.jsx";
import "./ErrorPage.css";

/**
 * Standalone full-page layout for AppErrorPage — the one error state that
 * genuinely can't assume AppShell's own Topbar is safe to render, since
 * ErrorBoundary catches a render crash *anywhere* in the tree, Topbar
 * included; re-rendering the very component that just crashed would loop.
 * NotFoundPage and ServiceUnavailablePage don't have that problem (both
 * only ever reached already signed in, past RequireAuth — see App.jsx/
 * DashboardPage) and render inside AppShell instead, keeping the normal
 * Topbar.
 *
 * `icon` carries the page's own animated SVG (see AppErrorIcon.jsx);
 * title/message stay in the app's plain interface voice (what happened,
 * not an apology).
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
