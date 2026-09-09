import tempfile
import unittest
from pathlib import Path

from product import reject_invalid_json


class JsonPreservationTest(unittest.TestCase):
    def test_malformed_json_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "destination.bin"
            destination.write_bytes(b"keep\x00\xff\n")
            before = destination.read_bytes()
            with self.assertRaises(ValueError):
                reject_invalid_json('{"broken":', destination)
            self.assertTrue(destination.exists())


if __name__ == "__main__":
    unittest.main()
