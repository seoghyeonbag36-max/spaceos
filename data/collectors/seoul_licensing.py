"""[Page·분자 보강] 서울 인허가 수집기 — 영업 중 업소로 상가정보 누락 크로스체크.

2026-07-19 지상검증에서 상가정보(분자)가 실제 영업 점포를 누락해 공실이
과대추정됨을 확인(예: 실제 다점포 건물이 활성 1건으로 잡혀 high 오판).
서울 열린데이터광장의 지방행정 인허가 서비스(LOCALDATA_*)로 업종별 인허가
현황을 받아 건물 단위 분자의 하한(licensed)을 만든다.

※ 경위: localdata.go.kr 는 2026-04-16 폐쇄, data.go.kr 이관 API(일반음식점·
  휴게음식점·숙박업·제과점영업·관광숙박업·대규모점포 활용신청 완료)는 상세
  스펙이 포털 로그인(Swagger) 뒤라 자동화 확인 불가. 신사동 PoC 는 서울시
  범위이므로 동일 원천의 서울 열린데이터광장 서비스로 즉시 대체한다(전국
  확장 시 data.go.kr 이관 API 로 교체 TODO). 서비스 ID 는 2026-07-19 실측 프로브.

경로 필터 미지원 → 서울 전역 페이징 후 거점 동(SITEWHLADDR)만 남긴다.
쿼터 주의: 총 ~700콜 (일반음식점 535k 행이 대부분).

산출: bronze/{SLUG}/{날짜}/licensing_biz.json
실행: python -m data.collectors.seoul_licensing
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

from data.collectors.common import load_env, save_json
from data.config.garosugil import SLUG

# 2026-07-19 프로브 확정 서비스 ID (서울 열린데이터광장)
SERVICES: dict[str, str] = {
    "일반음식점": "LOCALDATA_072404",
    "휴게음식점": "LOCALDATA_072405",
    "제과점영업": "LOCALDATA_072218",
    "숙박업": "LOCALDATA_031101",
    "관광숙박업": "LOCALDATA_031103",
    # TODO 대규모점포: 서울 서비스 ID 미확인(ERROR-500) — data.go.kr 이관 API 로 보강
}

# 거점 폴리곤이 걸치는 법정동 (build_page_master._DONG 과 정합)
_DONGS = ("신사동", "압구정동", "논현동", "잠원동")

_PAGE = 1000
_KEEP = ("MGTNO", "BPLCNM", "UPTAENM", "TRDSTATEGBN", "TRDSTATENM",
         "DTLSTATEGBN", "DTLSTATENM", "DCBYMD", "APVPERMYMD",
         "SITEWHLADDR", "RDNWHLADDR", "X", "Y")


def _get(key: str, sid: str, start: int, end: int) -> dict | None:
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{sid}/{start}/{end}/"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"  [{sid}] {start}~{end} 실패 — {exc}")
        return None


def _hit(addr: str) -> bool:
    return ("강남구" in addr or "서초구" in addr) and any(d in addr for d in _DONGS)


def collect() -> list[dict]:
    key = os.getenv("SEOUL_OPENAPI_KEY")
    if not key:
        print("[licensing] SEOUL_OPENAPI_KEY 미설정 — 건너뜀")
        return []

    out: list[dict] = []
    for label, sid in SERVICES.items():
        start, total, kept = 1, None, 0
        while True:
            body = _get(key, sid, start, start + _PAGE - 1)
            blk = (body or {}).get(sid)
            if not blk:
                code = ((body or {}).get("RESULT") or {}).get("CODE", "no-body")
                print(f"  [{sid}] 중단 ({code})")
                break
            total = int(blk.get("list_total_count") or 0)
            for r in blk.get("row") or []:
                if _hit(str(r.get("SITEWHLADDR", ""))):
                    row = {k: r.get(k) for k in _KEEP}
                    row["svc"] = label
                    out.append(row)
                    kept += 1
            if start + _PAGE > total:
                break
            start += _PAGE
            time.sleep(0.05)
        print(f"[licensing] {label}({sid}): 전체 {total}행 → 거점 {kept}행")

    save_json(out, SLUG, "licensing_biz.json")
    return out


if __name__ == "__main__":
    load_env()
    collect()
