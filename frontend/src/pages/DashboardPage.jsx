import { useAuth0 } from "@auth0/auth0-react";
import AppShell from "../components/shell/AppShell.jsx";
import { useCurrentUser } from "../api/useCurrentUser.js";
import "./DashboardPage.css";

const MENU_ITEMS = [
  { id: "portfolio", label: "Portfolio" },
  { id: "watchlists", label: "Watchlists" },
  { id: "search", label: "Search" },
];

/**
 * The one real page this phase has. Its profile card is the end-to-end
 * proof of the whole auth chain (Auth0 login -> access token -> Django
 * ->  DynamoDB -> back into React), not a real dashboard yet — accounts,
 * pies, holdings, and the rest are later phases.
 */
function DashboardPage() {
  const { logout } = useAuth0();
  const { profile, isLoading, error } = useCurrentUser();

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Phase 0"
      title="App shell"
      subtitle="Routing, Auth0, and the API client are wired up — accounts, pies, holdings, and everything else come in later phases."
      actions={
        <button
          type="button"
          className="ec-logout-btn"
          onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
        >
          Log out
        </button>
      }
    >
      <div className="ec-profile-card">
        <span className="ec-profile-label">Default currency</span>
        {isLoading && <span className="ec-profile-value">Loading…</span>}
        {error && (
          <span className="ec-profile-error" role="alert">
            {error}
          </span>
        )}
        {profile && <span className="ec-profile-value">{profile.default_currency}</span>}
      </div>
    </AppShell>
  );
}

export default DashboardPage;
