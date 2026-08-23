"""외부 AI 창업 코파일럿 어댑터 — 계약 `spaceos.posting/1` 검증 (2026-08-23).

공급자가 미정이라 **계약을 그대로 흉내내는 가짜 서버**로 어댑터를 돌린다. 여기서
지키는 불변식은 셋이다:

1. 계약을 지킨 응답은 코파일럿 값이 그대로 나간다 (`source == "copilot"`)
2. 계약을 어긴 응답은 **통째로** 버리고 폴백한다 — 부분 채용은 없다
3. 파생값(`month_net`·`roi_months`·`recommended`)은 공급자가 아니라 **우리가** 정한다

3번이 이 테스트의 핵심이다. 공급자가 자기 net/roi/추천을 실어 보내도 무시돼야 한다.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import districts as svc
from app.services import posting_copilot as pc

client = TestClient(app)
V1 = "/api/v1"
DISTRICT = "garosugil"


def _ok_scenarios() -> list[dict]:
    """계약을 지킨 3전략. 회수 서열을 폴백과 다르게 둬서 값이 실제로 갈아끼워졌는지 본다.

    factory 가 회수 최단(9 × 100 / 300 = 3.0개월)이 되도록 짰다 — 폴백 계산에서는
    factory 가 실 유닛 270건 중 1위를 한 번도 못 했으므로(districts.recommend_tier),
    응답에 factory 추천이 뜨면 그것은 코파일럿 값을 쓴 것이 확실하다.
    """
    return [
        {"tier": "premium", "invest_mn": 80.0, "month_cost": 1500.0,
         "month_rev": 2000.0, "basis": "rent+fitout+cogs+labor"},
        {"tier": "value", "invest_mn": 30.0, "month_cost": 900.0,
         "month_rev": 1300.0, "basis": "rent+fitout+cogs+labor"},
        {"tier": "factory", "invest_mn": 9.0, "month_cost": 600.0,
         "month_rev": 900.0, "basis": "rent+fitout+cogs+labor"},
    ]


class _Handler(BaseHTTPRequestHandler):
    """가짜 코파일럿. `payload` 를 그대로 돌려주거나 `status` 로 실패를 흉내낸다."""

    payload: object = None
    status: int = 200
    seen: dict | None = None

    def do_POST(self):  # noqa: N802 — BaseHTTPRequestHandler 규약
        n = int(self.headers.get("Content-Length", 0))
        _Handler.seen = {
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "body": json.loads(self.rfile.read(n).decode("utf-8")) if n else None,
        }
        raw = json.dumps(_Handler.payload).encode("utf-8")
        self.send_response(_Handler.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass  # 테스트 출력을 더럽히지 않는다


@pytest.fixture
def copilot(monkeypatch):
    """가짜 코파일럿을 띄우고 settings 를 거기로 돌린다.

    monkeypatch 로 settings 를 바꾸는 이유: 실제 .env 에 URL 이 채워져 있든 없든
    테스트 결과가 같아야 한다. 전역 settings 를 직접 쓰면 개발자 머신에서만 깨진다.
    """
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    monkeypatch.setattr(settings, "posting_copilot_url",
                        f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setattr(settings, "posting_copilot_key", "test-key")
    _Handler.payload, _Handler.status, _Handler.seen = None, 200, None
    yield _Handler
    srv.shutdown()
    srv.server_close()


def _simulate() -> dict:
    r = client.post(f"{V1}/ai/simulate-revenue", json={"district_id": DISTRICT})
    assert r.status_code == 200, r.text
    return r.json()


# ── 1) 정상 경로 ──────────────────────────────────────────────────────────────

def test_copilot_response_replaces_fallback(copilot):
    """계약을 지킨 응답은 코파일럿 값으로 나간다."""
    copilot.payload = {"contract": pc.CONTRACT, "scenarios": _ok_scenarios()}
    body = _simulate()

    assert body["source"] == "copilot"
    assert body["source_note"] is None
    assert set(body["scenarios"]) == {"premium", "value", "factory"}
    assert body["scenarios"]["factory"]["month_rev"] == 900
    assert body["scenarios"]["premium"]["basis"] == "rent+fitout+cogs+labor"


def test_request_follows_contract(copilot):
    """요청이 계약 v1 형태다 — 경로·인증·단위표·시드 서술필드 배제."""
    copilot.payload = {"contract": pc.CONTRACT, "scenarios": _ok_scenarios()}
    _simulate()

    seen = copilot.seen
    assert seen["path"] == "/simulate"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["contract"] == pc.CONTRACT
    assert seen["body"]["district_id"] == DISTRICT
    # 단위표를 실어 보내는 것이 단위 사고의 1차 방어다
    assert seen["body"]["units"]["month_rev"] == "manwon_per_month"
    assert seen["body"]["units"]["invest_mn"] == "million_krw"
    # 시드 서술 필드는 보내지 않는다 — 실제 건물 유닛에는 없는 값이라
    # 공급자가 그걸 읽으면 배선이 다시 시드에 묶인다
    assert "rec" not in seen["body"]["unit"]
    assert "was" not in seen["body"]["unit"]


# ── 2) 파생값은 우리가 정한다 ──────────────────────────────────────────────────

def test_derived_fields_are_ours_not_the_vendors(copilot):
    """공급자가 net·roi·recommended 를 실어 보내도 무시하고 우리가 계산한다."""
    rows = _ok_scenarios()
    for row in rows:                      # 공급자가 거짓말을 한다
        row["month_net"] = 99999
        row["roi_months"] = 0.1
        row["recommended"] = row["tier"] == "premium"
    copilot.payload = {"contract": pc.CONTRACT, "scenarios": rows}
    body = _simulate()

    sc = body["scenarios"]
    assert sc["factory"]["month_net"] == 300      # 900 - 600, 공급자의 99999 아님
    assert sc["factory"]["roi_months"] == 3.0     # 9 × 100 / 300
    assert sc["premium"]["roi_months"] == 16.0    # 80 × 100 / 500
    # 추천 = 회수 최단(우리 기준). 공급자가 찍은 premium 이 아니라 factory 여야 한다.
    assert sc["factory"]["recommended"] is True
    assert sc["premium"]["recommended"] is False
    assert svc.recommend_tier(sc) == "factory"
    # 내부 비교용 필드가 API 로 새 나가면 안 된다
    assert "_raw" not in sc["factory"]


def test_unviable_scenario_marked(copilot):
    """순익 0 이하는 viable=False · roi 99.0 — 폴백과 같은 표식을 쓴다."""
    rows = _ok_scenarios()
    rows[0]["month_rev"] = 1000.0        # premium: 비용 1500 > 매출 1000
    copilot.payload = {"contract": pc.CONTRACT, "scenarios": rows}
    sc = _simulate()["scenarios"]

    assert sc["premium"]["viable"] is False
    assert sc["premium"]["roi_months"] == 99.0
    assert sc["premium"]["recommended"] is False


def test_basis_absent_is_declared_not_hidden(copilot):
    """공급자가 basis 를 안 밝히면 숨기지 않고 모른다고 적는다."""
    rows = [{k: v for k, v in r.items() if k != "basis"} for r in _ok_scenarios()]
    copilot.payload = {"contract": pc.CONTRACT, "scenarios": rows}
    sc = _simulate()["scenarios"]

    assert sc["value"]["basis"] == pc.BASIS_UNKNOWN
    assert sc["value"]["basis"], "빈 문자열이면 화면이 조용히 비어 구분이 안 된다"


# ── 3) 계약 위반은 통째로 폴백 ─────────────────────────────────────────────────

@pytest.mark.parametrize("payload, expect", [
    ({"contract": "other/9", "scenarios": _ok_scenarios()}, "contract 불일치"),
    ({"contract": pc.CONTRACT, "scenarios": _ok_scenarios()[:2]}, "tier 누락"),
    ({"contract": pc.CONTRACT, "scenarios": "nope"}, "배열이 아니다"),
    # 3전략은 다 왔는데 한 tier 의 필드가 빠진 경우 (누락 검사보다 뒤에서 걸린다)
    ({"contract": pc.CONTRACT, "scenarios": [
        {k: v for k, v in r.items() if k != "month_rev"} if r["tier"] == "premium" else r
        for r in _ok_scenarios()]}, "premium.month_rev 없음"),
    ({"contract": pc.CONTRACT, "scenarios": [
        dict(r, tier="luxury") if r["tier"] == "premium" else r
        for r in _ok_scenarios()]}, "모르는 tier"),
    ({"contract": pc.CONTRACT, "scenarios": [
        dict(r, month_rev=-1.0) if r["tier"] == "value" else r
        for r in _ok_scenarios()]}, "음수"),
    ({"contract": pc.CONTRACT, "scenarios": [
        dict(r, month_rev="1300") if r["tier"] == "value" else r
        for r in _ok_scenarios()]}, "수치가 아니다"),
], ids=["contract-mismatch", "tier-missing", "not-a-list", "field-missing",
        "unknown-tier", "negative", "string-number"])
def test_contract_violation_falls_back_whole(copilot, payload, expect):
    """어긴 응답은 **통째로** 버린다 — 성한 tier 만 골라 쓰지 않는다."""
    copilot.payload = payload
    body = _simulate()

    assert body["source"] == "fallback-3tier"
    assert expect in body["source_note"]
    # 폴백은 온전한 3전략이어야 한다
    assert set(body["scenarios"]) == {"premium", "value", "factory"}
    for sc in body["scenarios"].values():
        assert sc["basis"] == svc.COST_BASIS   # 코파일럿 basis 가 섞이지 않았다


def test_unit_mistake_is_rejected(copilot):
    """자릿수 사고는 상한에 걸려 폴백한다 — 만원/백만원을 뒤집어 보낸 경우."""
    rows = [dict(r, month_rev=r["month_rev"] * 10_000) for r in _ok_scenarios()]
    copilot.payload = {"contract": pc.CONTRACT, "scenarios": rows}
    body = _simulate()

    assert body["source"] == "fallback-3tier"
    assert "단위 착오" in body["source_note"]


def test_http_error_falls_back_with_reason(copilot):
    """공급자 5xx 는 우리 5xx 가 되면 안 된다 — 폴백 200 + 사유."""
    copilot.status = 503
    copilot.payload = {"error": "down"}
    body = _simulate()

    assert body["source"] == "fallback-3tier"
    assert "HTTP 503" in body["source_note"]


def test_unreachable_copilot_falls_back_with_reason(monkeypatch):
    """설정은 됐는데 연결이 안 되는 경우도 사유를 남긴다(서버를 아예 안 띄운다)."""
    # 127.0.0.1:9 = discard 포트. 열려 있지 않다.
    monkeypatch.setattr(settings, "posting_copilot_url", "http://127.0.0.1:9")
    monkeypatch.setattr(settings, "posting_copilot_key", "")
    body = _simulate()

    assert body["source"] == "fallback-3tier"
    assert body["source_note"], "왜 폴백했는지 없으면 죽어 있어도 아무도 모른다"


# ── 4) 미설정과 실패를 구분한다 ────────────────────────────────────────────────

def test_unconfigured_is_not_a_failure(monkeypatch):
    """코파일럿 미설정은 정상 동작이다 — source_note 가 비어야 한다.

    "안 붙였다"와 "붙였는데 죽었다"가 같은 화면이면 장애를 아무도 못 본다.
    """
    monkeypatch.setattr(settings, "posting_copilot_url", "")
    body = _simulate()

    assert body["source"] == "fallback-3tier"
    assert body["source_note"] is None
