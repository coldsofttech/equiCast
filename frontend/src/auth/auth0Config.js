/**
 * Vite bakes `import.meta.env.VITE_*` in at build time, so these are only
 * ever undefined because they're genuinely unset (missing an `.env.local`
 * locally, or an unset build-time var in CI) — see `.env.example` and
 * docs/auth0-setup.md's "Register the frontend Application" section for
 * where they come from. No frontend Auth0 Application exists yet as of
 * this file being written; `isAuth0Configured` lets the app render a clear
 * "not configured" state instead of Auth0Provider misbehaving against
 * undefined config.
 *
 * Deliberately the *same* three values for dev and prod — Auth0 setup is
 * one shared tenant/API for both (see docs/auth0-setup.md), so unlike the
 * backend API's own URL, this part of the frontend build doesn't need to
 * differ per environment.
 */
export const auth0Domain = import.meta.env.VITE_AUTH0_DOMAIN;
export const auth0ClientId = import.meta.env.VITE_AUTH0_CLIENT_ID;
export const auth0Audience = import.meta.env.VITE_AUTH0_AUDIENCE;

export const isAuth0Configured = Boolean(auth0Domain && auth0ClientId && auth0Audience);
