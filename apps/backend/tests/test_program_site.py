"""Program 입력 계약 ①층(자리) 배선 검증 (2026-08-23).

재료(`gold/{거점}/vacant_units.json`)는 08-22 에 54/54 거점을 채웠는데 Program 이
그걸 **읽지 않아** 게이트가 33.3% 에 멈춰 있었다. 여기서 지키는 것은 셋이다:

1. 자리층이 실제로 읽힌다 — 산출물의 수치가 생성 입력까지 도달한다
2. 출처와 한계(`site_note`)가 응답에 남는다 — 호실당 평균 면적·1F 가정을 숨기지 않는다
3. `unit_id` 없는 요청에 자리가 **끼어들지 않는다** — 영업 중 가게 요청이 다수다
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import program_site

client = TestClient(app)
V1 = "/api/v1"
DISTRICT = "garosugil"


@pytest.fixture(autouse=True)
def _clear():
    program_site.clear_cache()
    yield
    program_site.clear_cache()


def _has_gold() -> bool:
    return program_site._path(DISTRICT).exists()


gold_only = pytest.mark.skipif(
    not _has_gold(),
    reason="gold/{거점}/vacant_units.json 미적재 — build_vacant_units 실행 필요")


# ── 1) 자리층이 읽힌다 ────────────────────────────────────────────────────────

@gold_only
def test_units_load_from_gold():
    us = program_site.units(DISTRICT)
    assert us, "공실 유닛이 비었다 — 배선이 아니라 재료를 먼저 볼 것"
    u = us[0]
    for f in ("id", "area", "vacancy_rate"):
        assert f in u, f"{f} 없음 — 산출물 스키마가 바뀌었다"


@gold_only
def test_representative_unit_is_highest_vacancy_not_first():
    """대표 유닛은 파일 첫 줄이 아니라 공실률 최고여야 한다.

    파일 순서는 대장 처리 순서라 아무 뜻이 없다. 첫 줄을 대표로 삼으면 그 무의미한
    순서가 화면 기본값이 된다.
    """
    us = program_site.units(DISTRICT)
    rep = program_site.unit(DISTRICT, None)
    assert rep is not None
    assert rep["vacancy_rate"] == max(u["vacancy_rate"] for u in us)


@gold_only
def test_unit_lookup_by_id():
    target = program_site.units(DISTRICT)[-1]
    got = program_site.unit(DISTRICT, target["id"])
    assert got is not None and got["id"] == target["id"]
    assert program_site.unit(DISTRICT, "vu-없는아이디") is None


@gold_only
def test_site_context_carries_real_numbers():
    """생성 입력 텍스트에 산출물의 실제 수치가 들어간다."""
    u = program_site.unit(DISTRICT, None)
    ctx = program_site.site_context(DISTRICT, u["id"])

    assert ctx and u["id"] in ctx
    assert f"{u['area']}평" in ctx
    assert "공실률" in ctx
    # 리뷰가 없다는 사실을 입력이 스스로 말해야 한다 — 이 층이 리뷰를 대신하는 자리다
    assert "방문 후기" in ctx or "리뷰" in ctx
    # 한계 표기가 붙는다
    assert "한계" in ctx


# ── 2) 출처·한계가 응답에 남는다 ──────────────────────────────────────────────

@gold_only
def test_sites_endpoint_declares_provenance():
    r = client.get(f"{V1}/marketing/sites", params={"district_id": DISTRICT})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["district_id"] == DISTRICT
    assert body["sites"], "공실 목록이 비었다"
    assert body["site_source"] != "unavailable"
    assert body["site_note"], "면적이 호실당 평균이라는 한계가 빠지면 실측처럼 읽힌다"
    assert body["site_built_at"]


@gold_only
def test_sites_endpoint_respects_limit():
    r = client.get(f"{V1}/marketing/sites",
                   params={"district_id": DISTRICT, "limit": 2})
    assert len(r.json()["sites"]) <= 2


def test_unknown_district_is_empty_not_404():
    """모르는 거점은 404 가 아니라 빈 목록 + unavailable 이다.

    "이 거점을 모른다"와 "이 거점에 공실 산출물이 없다"는 다른 상태인데, 404 로
    뭉개면 화면이 둘을 구분하지 못한다.
    """
    r = client.get(f"{V1}/marketing/sites", params={"district_id": "nope-없는거점"})
    assert r.status_code == 200
    body = r.json()
    assert body["sites"] == []
    assert body["site_source"] == "unavailable"


def test_path_traversal_slug_rejected():
    """슬러그 화이트리스트가 경로 조작을 막는다."""
    assert program_site.units("../../etc") == []
    assert program_site.unit("..", None) is None
    assert program_site.site_context("a/b") is None


# ── 3) unit_id 없으면 자리가 끼어들지 않는다 ──────────────────────────────────

@gold_only
def test_site_context_absent_without_unit_id():
    """`unit_id` 를 안 준 요청에는 자리층이 붙지 않는다.

    거점만 보고 대표 유닛을 자동으로 끼워 넣으면, 영업 중인 가게 요청(현행 다수)에
    엉뚱한 공실의 면적·직전 업종이 섞여 그 가게의 사실인 양 인용된다.
    """
    from app.services import marketing as mkt

    assert mkt._site_context({"district_id": DISTRICT}) is None
    assert mkt._site_context({"district_id": DISTRICT, "unit_id": None}) is None

    u = program_site.unit(DISTRICT, None)
    assert mkt._site_context({"district_id": DISTRICT, "unit_id": u["id"]})


@gold_only
def test_generate_accepts_unit_id():
    """`unit_id` 를 실은 생성 요청이 통과한다(LLM 미설정이면 스텁)."""
    u = program_site.unit(DISTRICT, None)
    r = client.post(f"{V1}/marketing/generate", json={
        "name": "(가칭) 신규 창업", "category": "카페",
        "district_id": DISTRICT, "unit_id": u["id"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["source"] in ("llm", "rule-stub")


# ── 4) 깨진 산출물에 죽지 않는다 ──────────────────────────────────────────────

def test_corrupt_artifact_degrades_quietly(tmp_path, monkeypatch):
    """JSON 이 깨졌거나 스키마가 다르면 예외 대신 빈 목록으로 떨어진다."""
    bad = tmp_path / "bad" / "vacant_units.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{ 이건 JSON 이 아니다", encoding="utf-8")
    monkeypatch.setattr(program_site, "_GOLD_DIR", tmp_path)
    program_site.clear_cache()
    assert program_site.units("bad") == []

    bad.write_text(json.dumps({"units": "리스트가 아님"}), encoding="utf-8")
    program_site.clear_cache()
    assert program_site.units("bad") == []
    assert program_site.provenance("bad")["site_source"] == "unavailable"
