"""실측 수집 러너 — 사용자 PC(네트워크+API키)에서 실행.

`data/.env` 의 키를 로드해 4개 수집기를 실행하고, 각 기준이 '실측 LIVE'인지
'프록시 폴백'인지 진단한 뒤 Gold 점수표를 갱신한다.

실행(둘 중 편한 것):
    python score.py                  # repo 루트의 간편 런처 (권장)
    python -m data.run_collection    # 모듈 실행 (-m 은 짧은 하이픈)
"""
from __future__ import annotations

import os
from pathlib import Path

from data.config.seoul_districts import DISTRICTS

# .env 는 이 파일(run_collection.py)과 같은 data/ 폴더에 둔다 (cwd 무관).
_ENV_PATH = Path(__file__).resolve().parent / ".env"


def _load_env(path: Path = _ENV_PATH) -> None:
    """인코딩에 관대한 .env 로더 (utf-8 / cp949 / 메모장 ANSI 모두 허용)."""
    if not path.exists():
        print(f"[env] {path} 없음 — 모든 기준 프록시 폴백으로 실행")
        return
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:  # 그래도 안 되면 깨진 바이트 무시 (키 줄은 ASCII라 안전)
        text = raw.decode("utf-8", errors="ignore")

    loaded = 0
    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v:
            os.environ[k] = v  # .env 값이 우선
            loaded += 1
    print(f"[env] {path.name} 로드 완료 — 값이 채워진 키 {loaded}개")


def _is_live(values: dict[str, float], base_key: str) -> bool:
    """수집 결과가 base 앵커와 다르면 실측 LIVE로 판정."""
    base = {gu: float(m["base"][base_key]) for gu, m in DISTRICTS.items()}
    return any(abs(values[gu] - base[gu]) > 1e-6 for gu in DISTRICTS)


def main() -> None:
    _load_env()
    from data.collectors.living_population import fetch_living_population
    from data.collectors.naver_datalab import fetch_map_interest
    from data.collectors.sns_mentions import fetch_sns_mentions
    from data.collectors.vacancy import fetch_vacancy
    from data.pipelines.district_score import run

    print("\n-- 수집기 진단 --")
    checks = [
        ("SNS  업로드 ", fetch_sns_mentions, "SNS"),
        ("MAP  지도유입", fetch_map_interest, "MAP"),
        ("FOOT 유동인구", fetch_living_population, "FOOT"),
        ("VAC  공실   ", fetch_vacancy, "VAC"),
    ]
    for label, fn, key in checks:
        vals = fn()
        status = "[LIVE 실측]" if _is_live(vals, key) else "[프록시 폴백]"
        print(f"  {label}: {status}")

    print("\n-- Gold 점수표 --")
    run()


if __name__ == "__main__":
    main()
