"""R-ONE 상업용부동산 임대동향 수집 — 13거점 공실률·임대료 분기 시계열 (Bronze).

소스: reb.or.kr SttsApiTblData.do (키: REB_RONE_API_KEY, 분기 QY)
산출: bronze/platform13/{날짜}/rone_{vac_small,vac_mid,rent_small}.json
  행마다 district_id 를 부가 (config/rone_districts.DISTRICT_RONE 매핑, 공유 상권은 복수 행).

실행: python -m data.collectors.rone_rent
"""
from __future__ import annotations

import json
import time
import urllib.request

from data.collectors.common import load_env, save_json
from data.config.platform_districts import SLUG as SLUG13
from data.config.rone_districts import DISTRICT_RONE, SERIES_TABLES

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
        for sid in table_ids:
            rows = _fetch_all(key, sid)
            kept = 0
            for r in rows:
                cls = str(r.get("CLS_FULLNM", ""))
                if cls not in rone_to_districts:
                    continue
                q = _quarter_code(r.get("WRTTIME_DESC", ""))
                if not q:
                    continue
                for did in rone_to_districts[cls]:
                    out.append({
                        "district_id": did,
                        "quarter": q,
                        "value": r.get("DTA_VAL"),
                        "rone_cls": cls,
                        "statbl_id": sid,
                        "itm_nm": r.get("ITM_NM"),
                        "unit": r.get("UI_NM"),
                    })
                    kept += 1
            print(f"  {series} {sid}: 원본 {len(rows)}행 → 매핑 {kept}행")
        save_json(out, SLUG13, f"rone_{series}.json")


if __name__ == "__main__":
    collect()
