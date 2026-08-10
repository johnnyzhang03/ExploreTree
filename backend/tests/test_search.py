import unittest

from app.search import _parse_finance


class FinanceResultParsingTests(unittest.TestCase):
    def test_parses_current_data_wrapped_instrument_shape(self) -> None:
        _, finance = _parse_finance(
            {
                "title": "SK hynix Inc",
                "url": "https://example.com/sk-hynix",
                "data": {
                    "$type": "Stock",
                    "instrument": {
                        "symbol": "000660",
                        "displayName": "SK hynix Inc.",
                        "price": 1567000,
                        "pricePreviousClose": 1718000,
                        "changeAmount": -151000,
                        "changePercent": -8.79,
                        "currency": "KRW",
                        "marketCap": 1254986000000000,
                    },
                },
            }
        )

        self.assertEqual(finance["type"], "stock")
        self.assertEqual(finance["symbol"], "000660")
        self.assertEqual(finance["changePercent"], -8.79)
        self.assertEqual(finance["priceHistory"], [1718000, 1567000])
        self.assertEqual(
            finance["priceHistoryLabel"],
            "Previous close to current price",
        )

    def test_prefers_returned_chart_series_over_previous_close(self) -> None:
        _, finance = _parse_finance(
            {
                "title": "Example index",
                "data": {
                    "$type": "Index",
                    "instrument": {
                        "symbol": "INDEX",
                        "price": 103,
                        "pricePreviousClose": 99,
                    },
                    "chart": {
                        "series": [
                            {"value": 100},
                            {"close": 101},
                            {"price": 103},
                        ]
                    },
                },
            }
        )

        self.assertEqual(finance["priceHistory"], [100, 101, 103])
        self.assertEqual(finance["priceHistoryLabel"], "Price history")
