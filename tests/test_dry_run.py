import unittest

from demo_trader.dry_run import dry_run_decision


class TestDryRun(unittest.TestCase):
    def test_trades_when_trading_allowed(self) -> None:
        d = dry_run_decision(
            watchlist=("TEVA.TA", "NICE.TA"),
            trading_allowed=True,
            max_trades=3,
            min_buys_when_trading=1,
        )
        self.assertTrue(d["trades"])
        self.assertEqual(d["trades"][0]["side"], "buy")

    def test_no_trades_when_blocked(self) -> None:
        d = dry_run_decision(
            watchlist=("TEVA.TA",),
            trading_allowed=False,
            max_trades=3,
            min_buys_when_trading=2,
        )
        self.assertEqual(d["trades"], [])


if __name__ == "__main__":
    unittest.main()
