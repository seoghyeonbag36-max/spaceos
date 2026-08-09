"""[Page·수집] 건축HUB 실패 분류 회귀 — 서버 장애를 '대장 없음'으로 굳히지 않는다.

2026-08-08 배치에서 드러난 두 결함을 고정한다.

1. **속도** — 전유부가 503·비JSON 을 뱉는 동안 그 실패가 DNS 블립용 백오프
   (1·3·8·15초 × 4회 = 건당 최대 27초)를 타서 수집이 1.47초/동 → 7.0~9.3초/동으로
   무너졌다. 서버가 "지금 못 준다"고 즉답하는데 27초를 기다릴 이유가 없다.

2. **데이터(더 중요)** — 재수집 판정이 429 에만 걸려 있었다. 그래서 503 으로 전유부를
   잃은 건물이 표제부 폴백을 타고 `floor_approx` 로 굳거나, 표제부까지 실패하면
   `no_ledger` 로 굳었다. 둘 다 **완료로 간주돼 영영 재시도되지 않는다.**
   실제로는 집합건물인데 층수 근사가 분모로 들어가므로 capacity 가 뒤바뀐다.
   같은 사고를 2026-07-26 에 429 로 한 번 겪고 고쳤는데 5xx 가 같은 구멍으로 샜다.

실행: (레포 루트에서) python -m pytest data/tests -q
"""
from __future__ import annotations

import pytest
import requests

from data.collectors import building_vacancy as bv


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _http_error(code: int) -> requests.HTTPError:
    err = requests.HTTPError(f"{code} Server Error")
    err.response = _Resp(code)
    return err


# ── 1. 실패 분류 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_5xx_is_server_busy(code: int) -> None:
    assert bv._is_server_busy(_http_error(code))


def test_non_json_body_is_server_busy() -> None:
    """2xx 인데 본문이 비어 JSON 파싱이 깨지는 경우도 서버 장애다."""
    assert bv._is_server_busy(ValueError("Expecting value: line 1 column 1 (char 0)"))


def test_429_is_not_server_busy() -> None:
    """429 는 전용 경로(Retry-After · 전역 감속)를 타야 한다 — 섞이면 안 된다."""
    exc = _http_error(429)
    assert bv._is_429(exc)
    assert not bv._is_server_busy(exc)


@pytest.mark.parametrize("exc", [
    _http_error(404),                       # 대장이 원래 없는 경우 — 재시도 대상 아님
    requests.ConnectionError("getaddrinfo failed"),   # DNS 블립 — 길게 기다려야 지나간다
])
def test_other_failures_are_not_server_busy(exc: Exception) -> None:
    assert not bv._is_server_busy(exc)


def test_server_backoff_is_shorter_than_dns_backoff() -> None:
    """서버 장애 백오프가 DNS 백오프보다 짧아야 한다 — 이게 뒤집히면 1번 결함이 재발한다."""
    assert sum(bv._BACKOFF_5XX[:bv._RETRIES_5XX]) < sum(bv._BACKOFF[:bv._RETRIES])


# ── 2. 재수집 판정 (핵심) ───────────────────────────────────────────────

def _patch_expos_failure(monkeypatch, *, title_ok: bool) -> None:
    """전유부는 서버 장애로 실패, 표제부는 성공/실패를 고르게 하는 _get_json 대역."""
    def fake(url: str, params: dict):
        if bv.EP_EXPOS in url:
            bv._LAST_RETRYABLE[0] = True        # 503 으로 재시도 소진된 상태
            return None
        bv._LAST_RETRYABLE[0] = False
        if not title_ok:
            bv._LAST_RETRYABLE[0] = True
            return None
        return {"response": {"body": {"items": {"item": [
            {"mainPurpsCdNm": "제2종근린생활시설", "grndFlrCnt": "5"},
        ]}, "totalCount": 1}}}
    monkeypatch.setattr(bv, "_get_json", fake)


def test_server_failure_on_expos_is_retryable_not_floor_approx(monkeypatch) -> None:
    """전유부만 서버 장애로 잃고 표제부는 성공해도 floor_approx 로 굳히면 안 된다.

    실제로는 집합건물인데 층수 근사가 분모가 되면 capacity 가 뒤바뀐다.
    """
    _patch_expos_failure(monkeypatch, title_ok=True)
    capacity, method = bv.fetch_capacity("KEY", {"sigunguCd": "11650"}, {})
    assert method == "rate_limited", f"재수집 대상이어야 하는데 {method} 로 굳었다"
    assert capacity is None


def test_server_failure_on_both_is_retryable_not_no_ledger(monkeypatch) -> None:
    """전유부·표제부가 모두 서버 장애면 '대장 없음'이 아니라 '수집 실패'다.

    no_ledger 로 기록되면 재개 로직이 완료로 보고 그 건물을 다시 시도하지 않는다.
    """
    _patch_expos_failure(monkeypatch, title_ok=False)
    capacity, method = bv.fetch_capacity("KEY", {"sigunguCd": "11650"}, {})
    assert method == "rate_limited", f"재수집 대상이어야 하는데 {method} 로 굳었다"
    assert capacity is None


def test_rate_limited_is_retried_on_resume() -> None:
    """rate_limited 는 재개 시 '완료'로 치지 않아야 한다 — 재수집 경로의 마지막 고리."""
    assert "rate_limited" in bv._RETRY_METHODS
    assert "no_ledger" not in bv._RETRY_METHODS       # 이건 사실이므로 다시 묻지 않는다


# ── 3. 전유부 페이지 캡 (2026-08-09) ────────────────────────────────────

def _patch_expos_pages(monkeypatch, total: int, *, commercial_from: int = 0):
    """전유부가 total 행을 100행/페이지로 돌려주는 대역. 호출된 페이지를 기록한다."""
    pages: list[int] = []

    def fake(url: str, params: dict):
        if bv.EP_EXPOS not in url:
            bv._LAST_RETRYABLE[0] = False
            return {"response": {"body": {"items": {"item": []}, "totalCount": 0}}}
        page = int(params["pageNo"])
        pages.append(page)
        start = (page - 1) * 100
        item = [
            {"exposPubuseGbCdNm": "전유", "mainPurpsCdNm": "소매점",
             "dongNm": "", "hoNm": str(i), "flrNoNm": "1"}
            for i in range(start, min(start + 100, total)) if i >= commercial_from
        ]
        bv._LAST_RETRYABLE[0] = False
        return {"response": {"body": {"items": {"item": item}, "totalCount": total}}}

    monkeypatch.setattr(bv, "_get_json", fake)
    monkeypatch.setattr(bv, "_SLEEP", 0)
    return pages


def test_large_expos_is_capped(monkeypatch) -> None:
    """대형 집합건물은 _EXPOS_FULL_MAX 에서 끊긴다 — 쿼터가 여기로 새면 거점 하나가
    하루 쿼터의 3.5배를 먹는다(2026-08-09 dongdaemun 40,854행 실측)."""
    pages = _patch_expos_pages(monkeypatch, 12418)
    raw: dict = {}
    capacity, method = bv.fetch_capacity("KEY", {"sigunguCd": "11680"}, raw)

    assert len(pages) == bv._EXPOS_FULL_MAX // 100, f"{len(pages)}페이지나 돌았다"
    assert raw["expos_capped"] is True          # refetch 가 되받지 않게 하는 표시
    assert raw["expos_total"] == 12418          # 원본 규모는 남긴다
    assert method == "expos_units"              # 집합건물 판정은 유지 — 집계 제외 근거
    assert capacity == bv._EXPOS_FULL_MAX


def test_small_expos_is_not_capped(monkeypatch) -> None:
    """상한 이하 건물은 종전대로 전량 수집한다 — 캡이 일반 건물까지 자르면 안 된다."""
    pages = _patch_expos_pages(monkeypatch, 250)
    raw: dict = {}
    capacity, method = bv.fetch_capacity("KEY", {"sigunguCd": "11680"}, raw)

    assert len(pages) == 3
    assert "expos_capped" not in raw
    assert method == "expos_units"
    assert capacity == 250


def test_capped_jibun_is_excluded_from_refetch() -> None:
    """의도적 부분 수집은 refetch 대상에서 빠진다 — 안 그러면 절감분이 되돌아온다."""
    from data.collectors.refetch_truncated_expos import truncated

    raw = {
        "capped": {"expos_total": 5000, "expos": [1] * 300, "expos_capped": True},
        "broken": {"expos_total": 900, "expos": [1] * 200},   # 서버 장애로 잘린 것
        "whole": {"expos_total": 50, "expos": [1] * 50},
    }
    assert truncated(raw) == ["broken"]
    assert truncated(raw, include_capped=True) == ["capped", "broken"]
