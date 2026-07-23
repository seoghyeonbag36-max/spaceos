"""거점 API 테스트 — 서울 27 Page 시드(app/data/seoul_pages.py) 기준."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data import seoul_pages
from app.data.seoul_pages import DISTRICTS
from app.main import app

client = TestClient(app)
V1 = "/api/v1"

# 시드 주석의 개·폐업률 검증 기준 — gold 점포수 가중 분기율(build_gold 의 opbiz_rt/clsbiz_rt)
GOLD_TIMESERIES = (Path(__file__).resolve().parents[3]
                   / "data" / "gold" / "platform13" / "platform_district_timeseries.parquet")
GOLD_QUARTER = "20252"  # 2025Q2 — 주석이 인용하는 분기

SEOUL_DISTRICT_IDS = {
    "garosugil", "apgujeong-rodeo", "hongdae", "yeonnam", "ikseon", "seochon",
    "myeongdong", "euljiro", "seongsu", "seoulsup", "itaewon", "hannam", "songridan",
    # 2026-07-22 Phase 1 자치구 미커버 상권 확장분
    "gangnam", "hapjeong", "mangwon", "samcheong", "gwangjang", "dongdaemun",
    # 2026-07-22 Phase 2 자치구 확장분 (용산은 itaewon/hannam 이 이미 커버)
    "jamsil", "konkuk", "yeouido", "mullae", "banpo", "sinchon", "yeonhui", "cheongnyangni",
}


def test_list_districts():
    r = client.get(f"{V1}/commercial-districts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == len(DISTRICTS) == 27
    assert {d["id"] for d in data} == SEOUL_DISTRICT_IDS
    for d in data:
        assert 0 <= d["sentiment"] <= 100
        assert 0 <= d["vacancy_rate"] <= 100
        assert d["tier_mix"]["premium"] + d["tier_mix"]["value"] + d["tier_mix"]["factory"] == 5


def test_district_summary_and_detail():
    r = client.get(f"{V1}/commercial-districts/garosugil/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "신사동 가로수길"
    assert body["gu"] == "강남구"

    r = client.get(f"{V1}/commercial-districts/garosugil")
    assert r.status_code == 200
    assert len(r.json()["zones"]) == 6
    assert len(r.json()["units"]) == 5


def test_sentiment_and_heatmap():
    r = client.get(f"{V1}/commercial-districts/seongsu/sentiment")
    assert r.status_code == 200 and len(r.json()) == 6

    r = client.get(f"{V1}/heatmap/vacancy", params={"district": "seongsu"})
    assert r.status_code == 200
    hm = r.json()
    assert hm["resolution_m"] == 100
    assert hm["cells"] and hm["sum_stores"] > 0


def test_all_districts_have_heatmap_cells():
    """전 거점 그리드 합성 셀이 비어 있지 않아야 한다 (hot 스팟 정합 검증)."""
    for d in DISTRICTS:
        r = client.get(f"{V1}/heatmap/vacancy", params={"district": d["id"]})
        assert r.status_code == 200, d["id"]
        hm = r.json()
        assert hm["cells"], f"{d['id']} 그리드 셀 없음"
        assert hm["sum_stores"] > 0, d["id"]


def test_postings_and_marketing():
    r = client.get(f"{V1}/commercial-districts/hongdae/postings")
    assert r.status_code == 200
    postings = r.json()
    assert len(postings) == 5
    sc = postings[0]["scenarios"]
    assert set(sc.keys()) == {"premium", "value", "factory"}
    assert any(v["recommended"] for v in sc.values())

    r = client.get(f"{V1}/marketing/hongdae")
    assert r.status_code == 200
    assert len(r.json()["events"]) == 3


def test_seed_comment_rates_match_gold():
    """시드 주석의 점포수·개폐업률이 gold 2025Q2 값과 일치해야 한다.

    주석 기준이 두 가지로 갈렸던 회귀 방지용(2026-07-23 재산출). 과거 14~19번 주석은
    analyze_district_signals.py 의 '0 제외 단순평균'이라 gold 가중값보다 3~8배 높았다.
    데이터 레이어(pandas·parquet)가 없는 환경에서는 건너뛴다.
    """
    pd = pytest.importorskip("pandas", reason="데이터 레이어 미설치 — gold 대조 생략")
    if not GOLD_TIMESERIES.exists():
        pytest.skip(f"gold 산출물 없음: {GOLD_TIMESERIES}")

    df = pd.read_parquet(GOLD_TIMESERIES)
    rows = df[df["quarter"].astype(str) == GOLD_QUARTER]
    gold = {r.district_id: (r.clsbiz_rt, r.opbiz_rt, int(r.stor_co)) for r in rows.itertuples()}

    src = Path(seoul_pages.__file__).read_text(encoding="utf-8")
    # 거점 블록 단위로 잘라 주석 수치를 해당 거점 gold 와 대조
    blocks = re.split(r'\n(?=\{"id": )', src)
    checked = 0
    for block in blocks:
        m = re.match(r'\{"id": "([a-z0-9-]+)"', block)
        if not m:
            continue  # 모듈 헤더(재산출 이력에 옛 수치를 인용)는 대조 대상이 아니다
        did = m.group(1)
        assert did in gold, f"{did}: gold {GOLD_QUARTER} 행 없음 — 신규 거점은 gold 재빌드 필요"
        gold_cls, gold_op, gold_stor = gold[did]

        for cls, op in re.findall(r"폐업률 ([\d.]+)% (?:vs |· )개업률 ([\d.]+)%", block):
            assert float(cls) == pytest.approx(gold_cls, abs=0.005), f"{did} 폐업률 주석"
            assert float(op) == pytest.approx(gold_op, abs=0.005), f"{did} 개업률 주석"
            checked += 1
        for stor in re.findall(r"점포 ([\d,]+) ", block):
            assert int(stor.replace(",", "")) == gold_stor, f"{did} 점포수 주석"
            checked += 1

    # 현재 42건(요율쌍 28 + 점포수 14). 정규식이 조용히 빗나가면 0건 통과가 되므로 하한을 둔다
    assert checked >= 42, f"주석 대조 {checked}건 — 주석 형식이 바뀌었는지 확인"


def test_unknown_district_404():
    assert client.get(f"{V1}/commercial-districts/nope/summary").status_code == 404
    assert client.get(f"{V1}/heatmap/vacancy", params={"district": "nope"}).status_code == 404
