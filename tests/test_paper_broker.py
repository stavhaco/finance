import unittest

from demo_trader.paper_broker import Quote, apply_slippage, execute_trade, max_buy_qty, portfolio_nav
from demo_trader.state_store import PaperState


class TestPaperBroker(unittest.TestCase):
    def test_apply_slippage(self) -> None:
        self.assertGreater(apply_slippage("buy", 100.0, 100.0), 100.0)
        self.assertLess(apply_slippage("sell", 100.0, 100.0), 100.0)

    def test_buy_sell_roundtrip_nav(self) -> None:
        state = PaperState(cash_ils=100_000.0)
        q = Quote(symbol="TEVA.TA", last=50.0, currency="ILS")
        nav0 = portfolio_nav(state, {"TEVA.TA": 50.0})
        ok, _ = execute_trade(
            state,
            symbol="TEVA.TA",
            side="buy",
            qty=10.0,
            quote=q,
            slippage_bps=0.0,
            max_position_pct=100.0,
            nav=nav0,
            reason="test",
        )
        self.assertTrue(ok)
        nav1 = portfolio_nav(state, {"TEVA.TA": 50.0})
        self.assertAlmostEqual(nav0, nav1, places=6)

        ok2, _ = execute_trade(
            state,
            symbol="TEVA.TA",
            side="sell",
            qty=10.0,
            quote=q,
            slippage_bps=0.0,
            max_position_pct=100.0,
            nav=nav1,
            reason="test",
        )
        self.assertTrue(ok2)
        self.assertAlmostEqual(state.cash_ils, 100_000.0, places=6)
        self.assertEqual(state.positions, {})

    def test_max_buy_qty_respects_cap(self) -> None:
        state = PaperState(cash_ils=1_000_000.0)
        nav = 1_000_000.0
        room = max_buy_qty(state, "TEVA.TA", price=100.0, max_position_pct=10.0, nav=nav)
        self.assertAlmostEqual(room, 1000.0, places=6)


if __name__ == "__main__":
    unittest.main()
