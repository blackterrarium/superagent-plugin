import json
from pathlib import Path


def reject_invalid_json(text: str, destination: Path) -> None:
    """Reject malformed JSON without writing to the destination."""
    json.loads(text)
