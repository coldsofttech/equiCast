import ErrorPage from "../../components/errors/ErrorPage.jsx";
import ServiceUnavailableIcon from "../../components/errors/ServiceUnavailableIcon.jsx";
import Button from "../../components/core/Button.jsx";

/**
 * Shown in place of a page's own content when its initial load fails with
 * a real service-level failure (a network failure, or a genuine 5xx from
 * the API/API Gateway) rather than a normal empty/validation state — see
 * isServiceUnavailableError.js, and DashboardPage for the reference
 * wiring. `onRetry` re-runs whatever fetch failed when the caller has a
 * cheap way to (e.g. re-invoking its own load effect); defaults to a full
 * reload when it doesn't.
 */
function ServiceUnavailablePage({ onRetry }) {
  return (
    <ErrorPage
      icon={<ServiceUnavailableIcon />}
      title="equiCast is temporarily unavailable"
      message="We're having trouble reaching the server. This is usually short-lived — try again in a moment."
      action={
        <Button variant="primary" onClick={onRetry ?? (() => window.location.reload())}>
          Try again
        </Button>
      }
    />
  );
}

export default ServiceUnavailablePage;
