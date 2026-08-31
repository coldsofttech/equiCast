/**
 * Plain-JS fetch wrapper, JSDoc-typed for editor intellisense rather than
 * real TypeScript (see the design discussion this was built from — no
 * TypeScript tooling exists in this project yet). Framework-agnostic on
 * purpose: it takes a `getAccessToken` callback rather than importing
 * @auth0/auth0-react itself, so it's usable/testable without a React tree
 * or an Auth0Provider in scope — see useApi.js for the hook that binds
 * Auth0's token getter in for real use.
 */

/**
 * In dev, Vite's proxy (vite.config.js) forwards `/api` to the local
 * Django server, so the default is enough with nothing set. A deployed
 * build needs `VITE_API_BASE_URL` pointed at that environment's real API
 * Gateway URL instead — dev and prod are separate backend deployments
 * with different URLs, unlike the Auth0 config in auth0Config.js, which
 * is genuinely the same for both. NOT wired up yet: deploy.yml currently
 * builds the frontend once and promotes the identical artifact to dev and
 * prod, which can't be correct once this needs to differ per environment
 * — see CHANGELOG.md.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

/**
 * Thrown for any non-2xx response. `status` lets a caller branch on it
 * (e.g. redirect to sign-in on 401) without parsing `.message`.
 */
export class ApiError extends Error {
  /**
   * @param {string} message
   * @param {number} status
   */
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * @typedef {Object} ApiFetchOptions
 * @property {string} [method]
 * @property {unknown} [body] - JSON-serialized automatically unless it's
 *   already a string/FormData.
 * @property {Record<string, string>} [headers]
 * @property {() => Promise<string>} [getAccessToken] - Omit for an
 *   intentionally unauthenticated call; every real endpoint under
 *   `/api/` other than `/api/market/...`'s public reads requires one.
 */

/**
 * @param {string} path - e.g. "/identity/me/" (leading slash, trailing
 *   slash — every backend URL pattern ends in one, see backend/README.md).
 * @param {ApiFetchOptions} [options]
 * @returns {Promise<unknown>} Parsed JSON body, or `null` for a 204.
 * @throws {ApiError}
 */
export async function apiFetch(path, options = {}) {
  const { method = "GET", body, headers, getAccessToken } = options;

  const finalHeaders = new Headers(headers);
  finalHeaders.set("Accept", "application/json");

  let finalBody = body;
  if (body !== undefined && typeof body !== "string" && !(body instanceof FormData)) {
    finalHeaders.set("Content-Type", "application/json");
    finalBody = JSON.stringify(body);
  }

  if (getAccessToken) {
    const token = await getAccessToken();
    finalHeaders.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: finalHeaders,
    body: finalBody,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorBody = await response.json();
      if (errorBody && typeof errorBody.detail === "string") {
        detail = errorBody.detail;
      }
    } catch {
      // Non-JSON (or empty) error body — fall back to statusText.
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}
