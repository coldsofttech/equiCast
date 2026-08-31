import Logo from "../components/brand/Logo.jsx";
import "./SignInScreen.css";

/**
 * `onSignIn` is `loginWithRedirect` from useAuth0(), passed in by
 * RequireAuth rather than called here directly — keeps this component
 * presentation-only (also makes it trivial to render/test without an
 * Auth0Provider in scope).
 */
function SignInScreen({ onSignIn, error }) {
  return (
    <div className="ec-signin">
      <Logo />
      <p className="ec-signin-tagline">Cast your equity forward.</p>
      {error ? (
        <p className="ec-signin-error" role="alert">
          {error}
        </p>
      ) : null}
      <button type="button" className="ec-signin-btn" onClick={onSignIn}>
        Log in
      </button>
    </div>
  );
}

export default SignInScreen;
