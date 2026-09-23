#!/usr/bin/env bash
# Keeps the Auth0 frontend SPA Application (AUTH0_CLIENT_ID, "equiCast Web"
# in docs/auth0-setup.md's Step 3) in sync with a dev/prod environment's
# frontend_url as infra-lifecycle.yml destroys/redeploys it. That Terraform
# output is a CloudFront domain assigned fresh every time the distribution
# is recreated (see infra/outputs.tf's frontend_url comment), so the
# Allowed Callback URLs / Allowed Logout URLs / Allowed Web Origins lists
# would otherwise need the same manual dashboard edit docs/auth0-setup.md
# Step 3 originally described.
#
# "Allowed Web Origins" is also what Auth0 checks for CORS on this
# Application — there's no separate CORS field to update.
#
# Does NOT create or configure the Auth0 tenant/API/Applications
# themselves (see docs/auth0-setup.md) — only patches the three URL lists
# on an Application that must already exist.
#
# Usage: auth0_sync_redirect_uris.sh <add|remove> <frontend-url>
#   add     appends <frontend-url> to all three lists if not already present
#   remove  removes <frontend-url> from all three lists if present
#
# Required environment variables:
#   AUTH0_DOMAIN             Tenant domain, e.g. equicast.eu.auth0.com
#                             (repo variable, same one auth workflows use).
#   AUTH0_CLIENT_ID           The frontend SPA Application's Client ID being
#                             patched (repo variable).
#   AUTH0_MGMT_CLIENT_ID      Client ID of a Machine-to-Machine Auth0
#                             Application authorized for the Auth0
#                             Management API with read:clients + update:clients
#                             scopes only (repo secret).
#   AUTH0_MGMT_CLIENT_SECRET  That Application's client secret (repo secret).
set -euo pipefail

ACTION="$1"
URL="$2"

if [ "$ACTION" != "add" ] && [ "$ACTION" != "remove" ]; then
  echo "::error::Usage: auth0_sync_redirect_uris.sh <add|remove> <frontend-url>" >&2
  exit 1
fi

for var in AUTH0_DOMAIN AUTH0_CLIENT_ID AUTH0_MGMT_CLIENT_ID AUTH0_MGMT_CLIENT_SECRET; do
  if [ -z "${!var:-}" ]; then
    echo "::error::$var is required" >&2
    exit 1
  fi
done

# Splits a curl response into its body and trailing HTTP status so a
# non-2xx can be reported with the actual Auth0 error body (a bare
# `curl -f` discards it), rather than just "curl: (22)".
request() {
  local method="$1" url="$2" data="${3:-}"
  local response status body
  if [ -n "$data" ]; then
    response=$(curl -sS -w '\n%{http_code}' -X "$method" "$url" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d "$data")
  else
    response=$(curl -sS -w '\n%{http_code}' -X "$method" "$url" \
      -H "Authorization: Bearer $TOKEN")
  fi
  status="${response##*$'\n'}"
  body="${response%$'\n'"$status"}"
  if [ "$status" -lt 200 ] || [ "$status" -ge 300 ]; then
    echo "::error::$method $url failed with HTTP $status: $body" >&2
    exit 1
  fi
  echo "$body"
}

TOKEN_RESPONSE=$(curl -sS -w '\n%{http_code}' -X POST "https://$AUTH0_DOMAIN/oauth/token" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg id "$AUTH0_MGMT_CLIENT_ID" --arg secret "$AUTH0_MGMT_CLIENT_SECRET" --arg audience "https://$AUTH0_DOMAIN/api/v2/" \
    '{client_id: $id, client_secret: $secret, audience: $audience, grant_type: "client_credentials"}')")
TOKEN_STATUS="${TOKEN_RESPONSE##*$'\n'}"
TOKEN_BODY="${TOKEN_RESPONSE%$'\n'"$TOKEN_STATUS"}"
if [ "$TOKEN_STATUS" -lt 200 ] || [ "$TOKEN_STATUS" -ge 300 ]; then
  echo "::error::Auth0 Management API token request failed with HTTP $TOKEN_STATUS: $TOKEN_BODY" >&2
  exit 1
fi
TOKEN=$(jq -r '.access_token' <<< "$TOKEN_BODY")

CURRENT=$(request GET "https://$AUTH0_DOMAIN/api/v2/clients/$AUTH0_CLIENT_ID?fields=callbacks,allowed_logout_urls,web_origins&include_fields=true")

BODY=$(jq -n --argjson current "$CURRENT" --arg url "$URL" --arg action "$ACTION" '
  def sync_list(arr):
    (arr // []) as $a |
    if $action == "add" then ($a + [$url] | unique)
    else ($a - [$url])
    end;
  {
    callbacks: sync_list($current.callbacks),
    allowed_logout_urls: sync_list($current.allowed_logout_urls),
    web_origins: sync_list($current.web_origins)
  }')

request PATCH "https://$AUTH0_DOMAIN/api/v2/clients/$AUTH0_CLIENT_ID" "$BODY" > /dev/null

echo "Auth0 Application $AUTH0_CLIENT_ID: ${ACTION}ed $URL"
