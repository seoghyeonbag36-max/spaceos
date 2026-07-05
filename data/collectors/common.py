"""수집기 공용 유틸 — Bronze/Silver/Gold 저장 규칙(data/README.md)을 한곳에서 강제.

Bronze 경로 규칙: data/bronze/{상권}/{YYYY-MM-DD}/{파일}.json — 원본 무가공 저장.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path
from typing import Any

# Windows cp949 콘솔에서 한글·특수문자 print 크래시 방지 (UnicodeEncodeError)
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

DATA_ROOT = Path(__file__).resolve().parents[1]  # data/
BRONZE = DATA_ROOT / "bronze"
SILVER = DATA_ROOT / "silver"
GOLD = DATA_ROOT / "gold"


def load_env() -> None:
    """data/.env 로드 — run_collection 의 인코딩 관대 로더를 재사용."""
    from data.run_collection import _load_env

    _load_env()


def today() -> str:
    return datetime.date.today().isoformat()


def bronze_dir(district: str, date: str | None = None) -> Path:
    d = BRONZE / district / (date or today())
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_json(obj: Any, district: str, name: str, date: str | None = None) -> Path:
    """Bronze 에 JSON 저장. obj 가 list 면 행 수를 로그로 남긴다."""
    path = bronze_dir(district, date) / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    n = f" ({len(obj)}행)" if isinstance(obj, list) else ""
    print(f"[bronze] {path.relative_to(DATA_ROOT)}{n}")
    return path


def latest_bronze(district: str, name: str) -> Path | None:
    """가장 최근 수집일 폴더에서 name 파일을 찾는다 (없으면 None)."""
    root = BRONZE / district
    if not root.exists():
        return None
    for day in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True):
        f = day / name
        if f.exists():
            return f
    return None


def load_latest(district: str, name: str) -> Any | None:
    f = latest_bronze(district, name)
    if f is None:
        return None
    return json.loads(f.read_text(encoding="utf-8"))
