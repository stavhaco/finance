import unittest

from demo_trader.ollama_health import format_ollama_help, ollama_reachable


class TestOllamaHealth(unittest.TestCase):
    def test_unreachable_local(self) -> None:
        ok, detail = ollama_reachable("http://127.0.0.1:59999", timeout_sec=0.5)
        self.assertFalse(ok)
        self.assertTrue(detail)

    def test_help_text_mentions_setup(self) -> None:
        h = format_ollama_help("http://127.0.0.1:11434", "llama3.2")
        self.assertIn("setup_ollama", h)


if __name__ == "__main__":
    unittest.main()
