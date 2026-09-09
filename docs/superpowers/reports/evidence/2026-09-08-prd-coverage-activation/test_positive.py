import tempfile, unittest
from pathlib import Path
from product import convert
class Coverage(unittest.TestCase):
    def test_rejected_input_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)/"out"
            before = b"original bytes\x00"
            dest.write_bytes(before)
            with self.assertRaises(ValueError): convert("{", dest)
            self.assertEqual(dest.read_bytes(), before)
if __name__ == "__main__": unittest.main()
