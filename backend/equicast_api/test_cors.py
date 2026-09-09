"""Retry-After needs to actually be readable by the frontend's fetch() for
a 429 to be handleable at all — see settings.py's CORS_EXPOSE_HEADERS
comment for why a cross-origin response hides it by default otherwise."""

from django.test import TestCase


class CorsExposeHeadersTests(TestCase):
    def test_retry_after_is_exposed_to_cross_origin_requests(self) -> None:
        response = self.client.get("/health/", HTTP_ORIGIN="http://localhost:5173")

        self.assertIn("Retry-After", response.headers.get("Access-Control-Expose-Headers", ""))
