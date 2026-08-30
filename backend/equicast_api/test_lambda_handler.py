"""Proves the Lambda packaging approach works: a real API Gateway HTTP API
(payload format 2.0) proxy-integration event, run through mangum, reaches
Django's actual URL routing and gets a real response back — not testing
Django itself (that's what the rest of the suite is for), just the
event-translation plumbing this whole deployment path depends on.
"""

import json
from typing import Any, cast

from equicast_api.lambda_handler import handler


def _api_gateway_v2_event(method: str, path: str) -> dict:
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {
            "host": "example.execute-api.eu-west-1.amazonaws.com",
            "x-forwarded-proto": "https",
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "example-api",
            "domainName": "example.execute-api.eu-west-1.amazonaws.com",
            "domainPrefix": "example",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            },
            "requestId": "test-request-id",
            "routeKey": f"{method} {path}",
            "stage": "$default",
            "time": "01/Jan/2026:00:00:00 +0000",
            "timeEpoch": 1735689600000,
        },
        "isBase64Encoded": False,
    }


def test_health_check_round_trips_through_mangum() -> None:
    event = _api_gateway_v2_event("GET", "/health/")

    # Nothing in this path touches the Lambda context arg, so a bare stand-in
    # is fine at runtime; `cast` just satisfies mangum's `LambdaContext` type.
    response = handler(event, cast(Any, {}))

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"status": "ok"}
