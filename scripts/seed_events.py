"""Загрузка тестовых событий из tests_data/events.jsonl."""

import json
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
DATA = Path(__file__).resolve().parent.parent / "tests_data" / "events.jsonl"


def main() -> None:
    ok, fail = 0, 0
    with httpx.Client(base_url=BASE, timeout=10) as client:
        with DATA.open(encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                r = client.post("/events", json=data)
                if r.status_code == 201:
                    ok += 1
                    print(f"  [{i}] OK  event_id={r.json()['event_id']}")
                else:
                    fail += 1
                    print(f"  [{i}] FAIL {r.status_code} {r.text[:120]}")
    print(f"\nИтого: {ok} успешно, {fail} с ошибкой валидации")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        BASE = sys.argv[1]
    main()
