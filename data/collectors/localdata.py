"""[B단계·Platform] LOCALDATA 지방행정 인허가 수집기 — 개·폐업 이력 (docs §8-B).

`LOCALDATA_API_KEY`(localdata.go.kr 오픈API 이용신청, 승인 1~2일)로 강남구 인허가
데이터를 받아 신사동 소재 행만 Bronze 에 저장한다. 폐업일자(dcbYmd)·영업상태가
LSTM 라벨과 공실 히스토리의 원천.

⚠️ 초기 전체 적재는 포털의 일괄 CSV 다운로드가 빠르다 — 이 수집기는 증분(REST)용 골격.
⚠️ 응답 JSON 구조·필드명은 승인 후 실호출로 확정할 것(TODO). 아래 파싱은 방어적.

실행: python -m data.collectors.localdata
"""
from __future__ import annotations

import os

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from data.collectors.common import load_env, save_json
from data.config.garosugil import LOCALDATA_LOCAL_CODE, SLUG

_URL = "http://www.localdata.go.kr/platform/rest/TO0/openDataApi"
_PAGE_SIZE = 500      # 문서상 최대
_MAX_PAGES = 200      # 폭주 방지 상한

# 업종(opnSvcId)별 조회 — 미지정 시 전 업종. 예: 일반음식점 07_24_04_P (※코드표 재확인)
_SVC_ID = os.getenv("LOCALDATA_SVC_ID", "")


def _rows_of(body: dict) -> list[dict]:
    """LOCALDATA 응답에서 행 목록 추출 — result.body.rows[].row 편차를 흡수."""
    rows = body.get("result", {}).get("body", {}).get("rows", [])
    out: list[dict] = []
    for r in rows if isinstance(rows, list) else [rows]:
        item = r.get("row", r) if isinstance(r, dict) else r
        out.extend(item if isinstance(item, list) else [item])
    return [r for r in out if isinstance(r, dict)]


def collect(state: str = "") -> list[dict]:
    """강남구 인허가 수집 → 신사동 행만 Bronze 저장.

    state: ""=전체 / "Y"=영업 / "N"=폐업 (TODO: 파라미터 명세 승인 후 확정).
    증분 수집은 lastModTsBgn/lastModTsEnd 파라미터 추가(TODO).
    """
    key = os.getenv("LOCALDATA_API_KEY")
    if not key or requests is None:
        print("[localdata] LOCALDATA_API_KEY 미설정(또는 requests 없음) — 건너뜀")
        return []

    acc: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        params = {
            "authKey": key,
            "localCode": LOCALDATA_LOCAL_CODE,
            "pageIndex": page,
            "pageSize": _PAGE_SIZE,
            "resultType": "json",
        }
        if state:
            params["state"] = state
        if _SVC_ID:
            params["opnSvcId"] = _SVC_ID
        try:
            resp = requests.get(_URL, params=params, timeout=30)
            resp.raise_for_status()
            rows = _rows_of(resp.json())
        except Exception as exc:
            print(f"[localdata] p{page} 실패 — {exc}")
            break
        acc.extend(rows)
        if len(rows) < _PAGE_SIZE:
            break

    # 거점 필터: 지번/도로명 주소에 '신사동' 포함 (bdMgtSn 조인은 Silver 단계에서)
    hit = [
        r for r in acc
        if "신사동" in str(r.get("siteWhlAddr", "")) or "신사동" in str(r.get("rdnWhlAddr", ""))
    ]
    save_json(hit, SLUG, "localdata_biz.json")
    print(f"[localdata] 강남구 {len(acc)}행 중 신사동 {len(hit)}행")
    return hit


if __name__ == "__main__":
    load_env()
    collect()
