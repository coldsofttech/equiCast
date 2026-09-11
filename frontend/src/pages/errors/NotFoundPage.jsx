import { useNavigate } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import NotFoundIcon from "../../components/errors/NotFoundIcon.jsx";
import Button from "../../components/core/Button.jsx";
import "../../components/errors/ErrorPage.css";

/** Shown for any route that doesn't match one of App.jsx's own — replaces
 * the previous silent redirect-to-dashboard, so a bad/stale link actually
 * says so instead of quietly landing somewhere else. Only reachable inside
 * RequireAuth (see App.jsx), so — unlike AppErrorPage/OfflinePage/
 * ServiceUnavailablePage, which can fire before or because of a failure in
 * the app's own chrome — the signed-in user's normal Topbar (search,
 * currency, account menu, ...) is always safe to render here, via AppShell,
 * instead of the bare standalone ErrorPage layout the others use. */
function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <AppShell narrow centerTitle title="Page not found">
      <div className="ec-errorpage-body">
        <div className="ec-errorpage-icon" aria-hidden="true">
          <NotFoundIcon />
        </div>
        <p className="ec-errorpage-message">
          There's nothing here. The page may have moved, or the link might be out of date.
        </p>
        <div className="ec-errorpage-action">
          <Button variant="primary" onClick={() => navigate("/dashboard")}>
            Back to dashboard
          </Button>
        </div>
      </div>
    </AppShell>
  );
}

export default NotFoundPage;
