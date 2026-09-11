import AppShell from "../../components/shell/AppShell.jsx";
import ServiceUnavailableIcon from "../../components/errors/ServiceUnavailableIcon.jsx";
import Button from "../../components/core/Button.jsx";
import "../../components/errors/ErrorPage.css";

/**
 * Shown in place of a page's own content when its initial load fails with
 * a real service-level failure (a network failure, or a genuine 5xx from
 * the API/API Gateway) rather than a normal empty/validation state — see
 * isServiceUnavailableError.js, and DashboardPage for the reference
 * wiring. `onRetry` re-runs whatever fetch failed when the caller has a
 * cheap way to (e.g. re-invoking its own load effect); defaults to a full
 * reload when it doesn't.
 *
 * Only reached inside RequireAuth (DashboardPage), so — like NotFoundPage —
 * it renders inside AppShell rather than the bare standalone ErrorPage
 * layout: Topbar's own profile fetch failing the same way doesn't crash
 * it, it just renders without the currency badge (see Topbar.jsx/
 * UserMenu.jsx, which reads the signed-in user's name/avatar straight off
 * the Auth0 token, not an API call) — so search/theme/sign-out stay
 * reachable even while the backend itself is down.
 */
function ServiceUnavailablePage({ onRetry }) {
  return (
    <AppShell narrow centerTitle title="equiCast is temporarily unavailable">
      <div className="ec-errorpage-body">
        <div className="ec-errorpage-icon" aria-hidden="true">
          <ServiceUnavailableIcon />
        </div>
        <p className="ec-errorpage-message">
          We're having trouble reaching the server. This is usually short-lived — try again in a
          moment.
        </p>
        <div className="ec-errorpage-action">
          <Button variant="primary" onClick={onRetry ?? (() => window.location.reload())}>
            Try again
          </Button>
        </div>
      </div>
    </AppShell>
  );
}

export default ServiceUnavailablePage;
