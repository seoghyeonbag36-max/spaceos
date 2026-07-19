"""일회성 프로브 — 상권 마스터(relm) 키워드 매칭 + 분기·코드 필터 확인 (platform-autorun A단계)."""
from __future__ import annotations

import json
import os

import requests

from data.run_collection import _load_env

_load_env()
KEY = os.getenv("SEOUL_OPENAPI_KEY")

# 13거점 후보 키워드 (seoul_pages.py의 id 순)
CANDIDATES: dict[str, tuple[str, ...]] = {
    "garosugil": ("가로수길", "신사역", "신사동"),
    "apgujeong-rodeo": ("압구정",),
    "hongdae": ("홍대", "홍익"),
    "yeonnam": ("연남",),
    "ikseon": ("익선", "종로3가", "낙원"),
    "seochon": ("서촌", "통인", "체부", "경복궁", "자하문"),
    "myeongdong": ("명동",),
    "euljiro": ("을지로",),
    "seongsu": ("성수",),
    "seoulsup": ("서울숲", "뚝섬"),
    "itaewon": ("이태원",),
    "hannam": ("한남", "한강진", "용리단", "이촌로"),
    "songridan": ("송리단", "석촌", "송파나루", "방이"),
}


def fetch(service: str, start: int, end: int, extra: str = "") -> dict:
    url = f"http://openapi.seoul.go.kr:8088/{KEY}/json/{service}/{start}/{end}{extra}"
    body = requests.get(url, timeout=30).json()
    return body.get(service, {"RESULT": body.get("RESULT")})


# 1) relm 전량 (1650행 = 2페이지)
rows: list[dict] = []
for s in (1, 1001):
    rows.extend(fetch("TbgisTrdarRelm", s, s + 999).get("row", []))
print(f"relm: {len(rows)}행")

for did, kws in CANDIDATES.items():
    hits = [r for r in rows if any(k in r["TRDAR_CD_NM"] for k in kws)]
    print(f"\n[{did}]")
    for r in hits:
        print(f"  {r['TRDAR_CD']} {r['TRDAR_SE_CD_NM']:6s} {r['TRDAR_CD_NM']} ({r['SIGNGU_CD_NM']} {r['ADSTRD_CD_NM']})")

# 2) 분기+상권코드 필터 경로 지원 확인 (이태원 관광특구 3001491)
for svc in ("VwsmTrdarSelngQq", "VwsmTrdarStorQq"):
    p = fetch(svc, 1, 5, "/20244/3001491")
    print(f"\n{svc}/20244/3001491: total={p.get('list_total_count')} rows={len(p.get('row', []))} RESULT={p.get('RESULT')}")
