import json
import sys
from pathlib import Path

from app.main import app


def main():
    if len(sys.argv) > 1:
        output = Path(sys.argv[1])
    else:
        output = Path(__file__).resolve().parents[2] / "outputs" / "backend"
    output.mkdir(parents=True, exist_ok=True)
    target = output / "openapi.json"
    target.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(target)


if __name__ == "__main__":
    main()
