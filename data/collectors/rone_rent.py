"""R-ONE 상업용부동산 임대동향 수집 — 54거점 공실률·임대료 분기 시계열 (Bronze).

소스: reb.or.kr SttsApiTblData.do (키: REB_RONE_API_KEY, 분기 QY)
산출: bronze/platform13/{날짜}/rone_{vac_small,vac_mid,rent_small}.json         — 54거점
      bronze/platform13/{날짜}/rone_{vac_small,vac_mid,rent_small}_bench.json  — 서울·권역 (§0-N)
  행마다 district_id 를 부가 (config/rone_districts.DISTRICT_RONE 매핑, 공유 상권은 복수 행).

실행: python -m data.collectors.rone_rent
"""
from __future__ import annotations

import json
import time
import urllib.request

from data.collectors.common import load_env, save_json
from data.config.platform_districts import SLUG as SLUG13
from data.config.rone_districts import DISTRICT_RONE, SERIES_TABLES, benchmark_scope

_BASE = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
_PAGE = 1000


def _key() -> str:
    import os

    load_env()
    k = os.environ.get("REB_RONE_API_KEY", "").strip()
    if not k:
        raise RuntimeError("REB_RONE_API_KEY 미설정 (data/.env)")
    return k


def _fetch_all(key: str, statbl_id: str) -> list[dict]:
    """통계표 전체 행 수집 (페이지네이션)."""
    rows: list[dict] = []
    pindex = 1
    while True:
        url = (f"{_BASE}?KEY={key}&Type=json&pIndex={pindex}&pSize={_PAGE}"
               f"&STATBL_ID={statbl_id}&DTACYCLE_CD=QY")
        with urllib.request.urlopen(url, timeout=30) as r:
            j = json.loads(r.read().decode("utf-8"))
        if "SttsApiTblData" not in j:
            print(f"  [경고] {statbl_id}: {str(j)[:120]}")
            return rows
        blk = j["SttsApiTblData"]
        total = blk[0]["head"][0]["list_total_count"]
        batch = blk[1].get("row", [])
        rows.extend(batch)
        if len(rows) >= total or not batch:
            return rows
        pindex += 1
        time.sleep(0.3)  # 공공 API 예의상 호출 간격


def _quarter_code(wrttime_desc: str) -> str:
    """'2022년 1분기' → '20221' (상권분석서비스 STDR_YYQU_CD 형식)."""
    s = str(wrttime_desc)
    try:
        year = s.split("년")[0].strip()
        q = s.split("년")[1].strip()[0]
        return f"{int(year)}{int(q)}"
    except (ValueError, IndexError):
        return ""


def collect() -> None:
    key = _key()
    # 역매핑: CLS_FULLNM → [district_id, ...] (뚝섬·이태원은 2거점 공유)
    rone_to_districts: dict[str, list[str]] = {}
    for did, cls in DISTRICT_RONE.items():
        rone_to_districts.setdefault(cls, []).append(did)

    for series, table_ids in SERIES_TABLES.items():
        out: list[dict] = []
        bench: list[dict] = []
        for sid in table_ids:
            rows = _fetch_all(key, sid)
            kept = 0
            kept_bench = 0
            for r in rows:
                cls = str(r.get("CLS_FULLNM", ""))
                scope = benchmark_scope(cls)
                if cls not in rone_to_districts and scope is None:
                    continue
                q = _quarter_code(r.get("WRTTIME_DESC", ""))
                if not q:
                    continue
                common = {
                    "quarter": q,
                    "value": r.get("DTA_VAL"),
                    "rone_cls": cls,
                    "statbl_id": sid,
                    "itm_nm": r.get("ITM_NM"),
                    "unit": r.get("UI_NM"),
                }
                # 벤치마크(서울·권역)와 거점은 배타적이지 않다 — 같은 응답에서 둘 다 뽑되
                # 산출물을 나눈다. 기존 rone_{series}.json 의 스키마·내용은 그대로다.
                if scope is not None:
                    bench.append({"scope": scope, **common})
                    kept_bench += 1
                for did in rone_to_districts.get(cls, ()):
                    out.append({"district_id": did, **common})
                    kept += 1
            print(f"  {series} {sid}: 원본 {len(rows)}행 → 매핑 {kept}행 · 벤치마크 {kept_bench}행")
        save_json(out, SLUG13, f"rone_{series}.json")
        save_json(bench, SLUG13, f"rone_{series}_bench.json")


if __name__ == "__main__":
    collect()
