import unittest
from datetime import date, datetime
from unittest import mock
from zoneinfo import ZoneInfo

from demo_trader.daily_report import build_daily_report, should_send_daily_report_il
from demo_trader.holdings_pnl import compute_holdings_pnl, il_date_from_ts, trades_on_il_date
from demo_trader.state_store import PaperState, TradeRecord, append_trade
from demo_trader.telegram_notify import _split_message, send_message


class TestHoldingsPnL(unittest.TestCase):
    def test_unrealized_after_buy(self) -> None:
        state = PaperState(cash_ils=0.0, positions={"TEVA.TA": 10.0})
        append_trade(
            state,
            TradeRecord(
                ts="2026-05-16T10:00:00+00:00",
                symbol="TEVA.TA",
                side="buy",
                qty=10.0,
                price=50.0,
                notional_ils=500.0,
                reason="test buy",
            ),
        )
        rows = compute_holdings_pnl(state, prices={"TEVA.TA": 55.0})
        self.assertEqual(len(rows), 1)
        h = rows[0]
        self.assertAlmostEqual(h.cost_basis_ils, 500.0)
        self.assertAlmostEqual(h.unrealized_pnl_ils or 0.0, 50.0)
        self.assertAlmostEqual(h.unrealized_pnl_pct or 0.0, 10.0)

    def test_realized_on_sell(self) -> None:
        state = PaperState(cash_ils=1000.0, positions={})
        append_trade(
            state,
            TradeRecord(
                ts="2026-05-16T09:00:00+00:00",
                symbol="NICE.TA",
                side="buy",
                qty=5.0,
                price=100.0,
                notional_ils=500.0,
                reason="buy",
            ),
        )
        append_trade(
            state,
            TradeRecord(
                ts="2026-05-16T15:00:00+00:00",
                symbol="NICE.TA",
                side="sell",
                qty=5.0,
                price=110.0,
                notional_ils=550.0,
                reason="take profit",
            ),
        )
        rows = compute_holdings_pnl(state, prices={"NICE.TA": 100.0})
        nice = next(r for r in rows if r.symbol == "NICE.TA")
        self.assertAlmostEqual(nice.realized_pnl_ils, 50.0)
        self.assertEqual(nice.qty, 0.0)

    def test_trades_on_il_date(self) -> None:
        state = PaperState(cash_ils=100_000.0)
        append_trade(
            state,
            TradeRecord(
                ts="2026-05-16T12:00:00+03:00",
                symbol="TEVA.TA",
                side="buy",
                qty=1.0,
                price=10.0,
                notional_ils=10.0,
                reason="r1",
            ),
        )
        day = date(2026, 5, 16)
        self.assertEqual(il_date_from_ts("2026-05-16T12:00:00+03:00"), day)
        actions = trades_on_il_date(state, day)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].reason, "r1")


class TestDailyReport(unittest.TestCase):
    def test_build_report_contains_sections(self) -> None:
        state = PaperState(cash_ils=90_000.0, positions={"TEVA.TA": 2.0})
        append_trade(
            state,
            TradeRecord(
                ts="2026-05-16T10:00:00+00:00",
                symbol="TEVA.TA",
                side="buy",
                qty=2.0,
                price=50.0,
                notional_ils=100.0,
                reason="earnings beat",
            ),
        )
        text = build_daily_report(
            state=state,
            prices={"TEVA.TA": 52.0, "TA35.TA": 1000.0},
            benchmark_last=1000.0,
            benchmark_symbol="TA35.TA",
            day=date(2026, 5, 16),
        )
        self.assertIn("Actions today", text)
        self.assertIn("Holdings P&L", text)
        self.assertIn("earnings beat", text)
        self.assertIn("TEVA.TA", text)


class TestTelegramNotify(unittest.TestCase):
    def test_split_long_message(self) -> None:
        text = "x" * 5000
        parts = _split_message(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= 4096 for p in parts))

    @mock.patch("demo_trader.telegram_notify.urllib.request.urlopen")
    def test_send_message_posts(self, urlopen_mock: mock.MagicMock) -> None:
        resp = mock.MagicMock()
        resp.status = 200
        resp.__enter__.return_value = resp
        urlopen_mock.return_value = resp
        send_message(bot_token="tok", chat_id="123", text="hello")
        self.assertTrue(urlopen_mock.called)


class TestDailySchedule(unittest.TestCase):
    def test_should_send_once_per_day(self) -> None:
        late = datetime(2026, 5, 16, 18, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        self.assertTrue(
            should_send_daily_report_il(last_report_il_date=None, now=late, after_hour=17, after_minute=36)
        )
        self.assertFalse(
            should_send_daily_report_il(
                last_report_il_date="2026-05-16", now=late, after_hour=17, after_minute=36
            )
        )
        early = datetime(2026, 5, 16, 10, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        self.assertFalse(
            should_send_daily_report_il(last_report_il_date=None, now=early, after_hour=17, after_minute=36)
        )


if __name__ == "__main__":
    unittest.main()
