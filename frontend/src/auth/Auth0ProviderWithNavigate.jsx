import { Auth0Provider } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";
import { auth0Audience, auth0ClientId, auth0Domain, isAuth0Configured } from "./auth0Config.js";

/**
 * Must render inside <BrowserRouter> (it calls useNavigate) and wrap
 * everything that calls useAuth0() — see main.jsx for the nesting order.
 * `onRedirectCallback` sends the user back to wherever they were headed
 * (appState.returnTo, set by RequireAuth's loginWithRedirect call) via
 * react-router instead of a full page reload, and strips Auth0's `code`/
 * `state` query params from the URL either way.
 *
 * If Auth0 isn't configured yet (see auth0Config.js), renders children
 * un-wrapped rather than handing Auth0Provider undefined domain/clientId —
 * RequireAuth's `!isAuth0Configured` branch handles telling the user why
 * nothing works instead.
 *
 * `cacheLocation="localstorage"` + `useRefreshTokens` keep the session alive
 * across a hard refresh — the SDK's default in-memory cache is wiped on
 * reload, so without this a refresh on any route (e.g. /accounts) bounced
 * straight back to the sign-in screen even though Auth0 still had a valid
 * session.
 */
function Auth0ProviderWithNavigate({ children }) {
  const navigate = useNavigate();

  if (!isAuth0Configured) {
    return children;
  }

  const onRedirectCallback = (appState) => {
    navigate(appState?.returnTo ?? window.location.pathname, { replace: true });
  };

  return (
    <Auth0Provider
      domain={auth0Domain}
      clientId={auth0ClientId}
      authorizationParams={{
        redirect_uri: window.location.origin,
        audience: auth0Audience,
      }}
      cacheLocation="localstorage"
      useRefreshTokens
      onRedirectCallback={onRedirectCallback}
    >
      {children}
    </Auth0Provider>
  );
}

export default Auth0ProviderWithNavigate;
