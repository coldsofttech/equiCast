from unittest.mock import patch

import pandas as pd
from django.test import TestCase
from django.urls import reverse


class TickerHistoryViewTests(TestCase):
    @patch("market_data.services.write_parquet")
    @patch("market_data.services.fetch_history")
    def test_get_returns_history(self, mock_fetch, mock_write) -> None:
        mock_fetch.return_value = pd.DataFrame(
            {"date": pd.to_datetime(["2024-01-01"]), "close": [100.0]}
        )

        response = self.client.get(reverse("ticker-history", args=["aapl"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ticker"], "AAPL")
        self.assertEqual(len(response.json()["results"]), 1)
