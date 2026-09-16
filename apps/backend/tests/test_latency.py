"""API 응답시간 계측 잠금 — KPI② 가 다시 '선언만' 으로 돌아가지 않게.

2026-09-16 이전에는 `API p95 <200ms` 를 재는 코드가 **저장소 전체에 0줄**이었다.
여기서 잠그는 것은 숫자가 아니라 계측기의 성질이다:

1. 모든 `/api/` 요청이 **한 곳에서** 세어진다(새 엔드포인트가 조용히 빠지지 않는다).
2. 키는 **라우트 템플릿**이다(실제 URL 을 키로 쓰면 카디널리티가 터진다).
3. 표본이 적으면 **판정하지 않는다**(KPI 규칙 2 — 불확실성 없이 '달성'이라 적지 않는다).
4. 값이 **프로세스 로컬**이라는 사실이 응답에 남는다(떼면 전역 p95 로 오독된다).
"""
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import latency

V1 = "/api/v1"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    latency.reset()
    yield
    latency.reset()


@pytest.fixture()
def admin(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "t")
    return {"X-Admin-Token": "t"}


# ── 계산 ────────────────────────────────────────────────────────────────────

def test_percentile_uses_nearest_rank_not_interpolation() -> None:
    """보간하면 표본에 없는 값이 나온다 — 작은 표본에서 없는 정밀도를 만들지 않는다."""
    vals = [float(i) for i in range(1, 101)]          # 1..100
    assert latency._percentile(vals, 0.95) == 95.0
    assert latency._percentile(vals, 0.50) == 50.0
    assert latency._percentile([], 0.95) == 0.0
    assert latency._percentile([7.0], 0.95) == 7.0


def test_small_sample_is_not_judged() -> None:
    """**핵심 잠금.** n 이 적으면 p95 는 최댓값과 다르지 않다 — 판정하지 않는다."""
    for _ in range(latency.MIN_SAMPLES - 1):
        latency.record("/api/v1/x", 1.0)
    route = latency.summary()["routes"][0]
    assert route["n"] < latency.MIN_SAMPLES
    assert route["verdict"] == "표본부족", "표본이 적은데 달성/미달을 판정했다"


def test_verdict_appears_once_there_are_enough_samples() -> None:
    for _ in range(latency.MIN_SAMPLES):
        latency.record("/api/v1/fast", 5.0)
    for _ in range(latency.MIN_SAMPLES):
        latency.record("/api/v1/slow", latency.TARGET_MS + 50.0)
    by = {r["route"]: r for r in latency.summary()["routes"]}
    assert by["/api/v1/fast"]["verdict"] == "충족"
    assert by["/api/v1/slow"]["verdict"] == "미달"


def test_window_is_bounded() -> None:
    """무한히 쌓이면 안 된다 — 오래된 표본은 밀려난다."""
    for i in range(latency.WINDOW * 2):
        latency.record("/api/v1/x", float(i))
    assert latency.summary()["routes"][0]["n"] == latency.WINDOW


def test_route_cardinality_is_capped() -> None:
    """경로 수가 터지면 조용히 버린다 — 계측이 서비스를 해치지 않는다."""
    for i in range(latency.MAX_ROUTES + 50):
        latency.record(f"/api/v1/r{i}", 1.0)
    assert len(latency.summary()["routes"]) == latency.MAX_ROUTES


# ── 배선 ────────────────────────────────────────────────────────────────────

def test_api_requests_are_measured_without_touching_endpoints() -> None:
    """엔드포인트를 고치지 않아도 세어져야 한다 — 미들웨어 한 곳에 건 이유다."""
    client.get(f"{V1}/districts")
    routes = [r["route"] for r in latency.summary()["routes"]]
    assert routes, "API 요청이 하나도 안 세어졌다"
    assert all(r.startswith("/api/") or r == "<unmatched>" for r in routes)


def test_route_key_is_the_template_not_the_url() -> None:
    """경로 파라미터가 키에 박히면 카디널리티가 터진다."""
    client.get(f"{V1}/districts/garosugil")
    client.get(f"{V1}/districts/hongdae")
    keys = [r["route"] for r in latency.summary()["routes"]]
    assert not any("garosugil" in k or "hongdae" in k for k in keys), keys


def test_non_api_paths_are_not_measured() -> None:
    """정적·헬스체크는 이 KPI 대상이 아니다."""
    client.get("/health")
    assert latency.summary()["routes"] == []


def test_failing_request_is_still_measured() -> None:
    """에러 응답도 시간을 쓴다 — 느린 실패가 통계에서 빠지면 p95 가 좋아 보인다."""
    client.get(f"{V1}/nope-does-not-exist")
    assert latency.summary()["overall"]["n"] >= 1


# ── 관측 창구 ───────────────────────────────────────────────────────────────

def test_latency_endpoint_requires_admin_token() -> None:
    os.environ.pop("ADMIN_TOKEN", None)
    assert client.get(f"{V1}/admin/latency").status_code == 403


def test_latency_endpoint_declares_that_it_is_process_local(admin) -> None:
    """전역 p95 로 오독되지 않도록 응답이 스스로 밝혀야 한다."""
    body = client.get(f"{V1}/admin/latency", headers=admin).json()
    assert body["scope"] == "process"
    assert "전역 p95 가 아니다" in body["note"]
    assert body["target_ms"] == latency.TARGET_MS
    assert body["min_samples"] == latency.MIN_SAMPLES


def test_empty_state_reports_zero_not_success(admin) -> None:
    """아무것도 안 쟀으면 '충족'이 아니라 표본부족이어야 한다."""
    body = client.get(f"{V1}/admin/latency", headers=admin).json()
    assert body["overall"]["verdict"] == "표본부족"


# ── 클라이언트 비콘 (신뢰 경계) ──────────────────────────────────────────────

def test_client_beacon_records_under_a_distinct_prefix() -> None:
    """**신뢰 경계 잠금.** 자가보고 값이 서버 실측과 한 키로 섞이면 안 된다."""
    assert client.post(f"{V1}/metrics/client",
                       json={"metric": "map_ready", "ms": 1200}).status_code == 204
    keys = [r["route"] for r in latency.summary()["routes"]]
    assert "client:map_ready" in keys, keys
    # 비콘 요청 자체(POST /metrics/client)도 서버 경로로 따로 세어진다 — 다른 키다.
    assert any(k.startswith("/api/") for k in keys)


def test_unknown_metric_names_are_dropped() -> None:
    """고정 목록 밖은 받지 않는다 — 카디널리티와 관리자 화면을 동시에 지킨다."""
    r = client.post(f"{V1}/metrics/client", json={"metric": "whatever", "ms": 5})
    assert r.status_code == 204, "비콘은 실패를 알려 봐야 프론트가 할 일이 없다"
    assert not any(x["route"].startswith("client:") for x in latency.summary()["routes"])


def test_absurd_values_are_clamped() -> None:
    """위조 가능한 입력이다 — 한 건이 통계를 통째로 흔들지 못하게 막는다."""
    from app.api.v1 import metrics

    client.post(f"{V1}/metrics/client", json={"metric": "map_ready", "ms": 10 ** 9})
    row = next(r for r in latency.summary()["routes"] if r["route"] == "client:map_ready")
    assert row["max_ms"] <= metrics.MAX_MS


def test_negative_values_are_rejected_by_schema() -> None:
    assert client.post(f"{V1}/metrics/client",
                       json={"metric": "map_ready", "ms": -1}).status_code == 422


def test_frontend_metric_names_match_the_server_allowlist() -> None:
    """프론트 `ClientMetric` 과 서버 `ALLOWED` 가 갈리면 비콘이 조용히 버려진다."""
    from pathlib import Path as _P

    from app.api.v1 import metrics

    # tests → backend → apps 이므로 parents[2] 가 apps/ 다.
    src = (_P(__file__).resolve().parents[2] / "frontend" / "src" / "lib"
           / "clientTiming.ts").read_text(encoding="utf-8")
    for name in metrics.ALLOWED:
        assert f'"{name}"' in src, f"프론트에 {name} 이 없다"
