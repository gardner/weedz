import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.cache import Acquisition


class CacheTests(unittest.TestCase):
    def test_interrupted_data_write_can_be_refetched(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            client = Acquisition(root)
            with patch.object(client, "_fetch", return_value={"results": [1]}) as fetch:
                client.json("https://example.org", {"page": 1})
                next(root.glob("*.receipt.json")).unlink()
                self.assertEqual(client.json("https://example.org", {"page": 1}), {"results": [1]})
                self.assertEqual(fetch.call_count, 2)

    def test_corrupt_completed_reply_is_not_silently_refetched(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            client = Acquisition(root)
            with patch.object(client, "_fetch", return_value={"results": []}):
                client.json("https://example.org", {})
                next(
                    p for p in root.glob("*.json") if not p.name.endswith(".receipt.json")
                ).write_text("{}")
                with self.assertRaises(ValueError):
                    client.json("https://example.org", {})


if __name__ == "__main__":
    unittest.main()
