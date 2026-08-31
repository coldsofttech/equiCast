import { useAuth0 } from "@auth0/auth0-react";
import Logo from "../components/brand/Logo.jsx";
import SignInScreen from "./SignInScreen.jsx";
import { isAuth0Configured } from "./auth0Config.js";
import "./SignInScreen.css";

/**
 * Gates its children behind Auth0. Split into an outer component that
 * checks `isAuth0Configured` *before* ever calling useAuth0() — Auth0
 * isn't wired up in the tree at all when unconfigured (see
 * Auth0ProviderWithNavigate), and this way that state gets an honest
 * message instead of depending on whatever @auth0/auth0-react's context
 * default happens to do when called outside a real Provider.
 */
function RequireAuth({ children }) {
  if (!isAuth0Configured) {
    return <SignInScreen error="Auth0 isn't configured yet — see docs/auth0-setup.md." />;
  }
  return <RequireAuthConfigured>{children}</RequireAuthConfigured>;
}

function RequireAuthConfigured({ children }) {
  const { isLoading, isAuthenticated, loginWithRedirect, error } = useAuth0();

  if (isLoading) {
    return (
      <div className="ec-signin" role="status" aria-live="polite">
        <Logo />
        <p className="ec-signin-tagline">Loading…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <SignInScreen
        error={error ? "Something went wrong signing in — try again." : undefined}
        onSignIn={() => loginWithRedirect({ appState: { returnTo: window.location.pathname } })}
      />
    );
  }

  return children;
}

export default RequireAuth;
