import ErrorPage from "../../components/errors/ErrorPage.jsx";
import OfflineIcon from "../../components/errors/OfflineIcon.jsx";

/** Rendered by App.jsx in place of the whole routed app whenever
 * useOnlineStatus reports the browser offline — no action button, since
 * there's nothing to click; it recovers on its own once the browser
 * fires its own `online` event. */
function OfflinePage() {
  return (
    <ErrorPage
      icon={<OfflineIcon />}
      title="You're offline"
      message="equiCast needs an internet connection. We'll reconnect automatically once you're back online."
    />
  );
}

export default OfflinePage;
