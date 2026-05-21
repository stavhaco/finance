import unittest

from demo_trader.market_data import _price_ils


class TestMarketData(unittest.TestCase):
    def test_ila_converts_agorot_to_shekels(self) -> None:
        self.assertEqual(_price_ils(9884.0, "ILA"), 98.84)

    def test_ils_unchanged(self) -> None:
        self.assertEqual(_price_ils(98.84, "ILS"), 98.84)

    def test_unknown_currency_unchanged(self) -> None:
        self.assertEqual(_price_ils(100.0, "USD"), 100.0)

    def test_price_to_ils_alias(self) -> None:
        self.assertEqual(price_to_ils(9884.0, "ILA"), 98.84)


if __name__ == "__main__":
    unittest.main()
