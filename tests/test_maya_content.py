from __future__ import annotations

import json
import unittest

from demo_trader.maya_content import _attachments_from_snippet, is_maya_url


class TestMayaContent(unittest.TestCase):
    def test_is_maya_url(self) -> None:
        self.assertTrue(is_maya_url("https://maya.tase.co.il/he/reports/companies/1"))
        self.assertFalse(is_maya_url("https://www.globes.co.il/x"))

    def test_attachments_from_snippet(self) -> None:
        snip = json.dumps(
            {
                "channel": "breaking",
                "attachments": [{"fileType": "htm", "url": "rhtm/1741001-1742000/H1.htm"}],
            },
            ensure_ascii=False,
        )
        atts = _attachments_from_snippet(snip)
        self.assertEqual(len(atts), 1)
        self.assertEqual(atts[0]["fileType"], "htm")


if __name__ == "__main__":
    unittest.main()
