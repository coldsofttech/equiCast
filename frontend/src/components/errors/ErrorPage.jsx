import { Link } from "react-router-dom";
import Logo from "../brand/Logo.jsx";
import "./ErrorPage.css";

/**
 * Standalone full-page layout, with no Topbar/footer — used directly by
 * AppErrorPage's own nested ErrorBoundary fallback, for the one case that
 * genuinely can't assume AppShell's Topbar is safe to render: Topbar
 * itself being what crashed. AppErrorPage normally renders AppShell (with
 * the usual Topbar/SiteFooter, same as NotFoundPage/ServiceUnavailablePage)
 * around its own icon/message/action, and only falls back to this bare
 * layout if that inner AppShell/Topbar render throws too — see
 * AppErrorPage.jsx.
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
