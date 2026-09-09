import json
from pathlib import Path
def convert(raw, destination):
    value = json.loads(raw)
    Path(destination).write_text(json.dumps(value))
