import unittest

from demo_trader.prompt_focus import prompt_focus_symbols


class TestPromptFocus(unittest.TestCase):
    def test_positions_first(self) -> None:
        wl = ("AAA.TA", "BBB.TA", "CCC.TA", "DDD.TA")
        focus = prompt_focus_symbols(wl, {"BBB.TA": 10}, max_symbols=2)
        self.assertEqual(focus[0], "BBB.TA")
        self.assertEqual(len(focus), 2)

    def test_cap_respected(self) -> None:
        wl = tuple(f"S{i}.TA" for i in range(20))
        focus = prompt_focus_symbols(wl, {}, max_symbols=5)
        self.assertEqual(len(focus), 5)


if __name__ == "__main__":
    unittest.main()
