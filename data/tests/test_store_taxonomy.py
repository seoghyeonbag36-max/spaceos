"""점포 노드 소스 교체 회귀 테스트 — 카카오 로컬 → 상가정보 (2026-09-15).

## 무엇을 고정하나

카카오 로컬 API 는 응답 결과의 저장을 허용하지 않는다(실시간 호출만). 그런데 이
저장소는 `bronze/*/kakao_places.json` 을 남기고 Gold 노드(47,442행)로 영구화하고
있었다 → `docs/finding-map-provider-google-2026-09-15.md` §7-2.

저장층을 소상공인 상가(상권)정보로 옮긴 뒤, **되돌아가지 않도록** 두 종류를 고정한다:

  ① 약관 불변식 — 저장 경로에 카카오가 다시 들어오면 실패한다(§3)
  ② 사상 규칙   — 7종 라벨 어휘가 상가정보 계층에서 재현되는지(§1·§2)

②를 테스트로 두는 이유: 판정 **순서**가 규칙의 알맹이다. 대분류를 먼저 보면 카페가
음식점으로, 약국·편의점이 소매로 접혀 라벨이 조용히 degenerate 한다.

실행: (레포 루트에서) python -m pytest data/tests -q
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from data.config.store_taxonomy import (
    CATEGORY_GROUPS,
    NON_STOREFRONT_LCLS,
    category_path,
    is_storefront,
    to_category_group,
)

ROOT = Path(__file__).resolve().parents[2]


# ── 1. 7종 사상 — 교차표(2026-08-17 상호일치 ≤50m)가 확인한 대응 ─────────────────
@pytest.mark.parametrize("row, expected", [
    # 음식 → 음식점 (교차표 9,848건)
    ({"indsLclsNm": "음식", "indsMclsNm": "한식", "indsSclsNm": "백반/한정식"}, "음식점"),
    ({"indsLclsNm": "음식", "indsMclsNm": "양식", "indsSclsNm": "이탈리아식"}, "음식점"),
    # 음식(비알코올) → 카페 (2,283건). 대분류가 '음식'이라 순서가 틀리면 음식점이 된다
    ({"indsLclsNm": "음식", "indsMclsNm": "비알코올 음료점",
      "indsSclsNm": "커피전문점/카페/다방"}, "카페"),
    # 소매(종합) → 편의점 (276건). 대분류가 '소매'라 순서가 틀리면 None 이 된다
    ({"indsLclsNm": "소매", "indsMclsNm": "종합 소매점", "indsSclsNm": "편의점"}, "편의점"),
    # 소매(의약·화장품) → 약국 (744건)
    ({"indsLclsNm": "소매", "indsMclsNm": "의약/의료품 소매업", "indsSclsNm": "약국"}, "약국"),
    # 보건의료 → 병원 (2,025건)
    ({"indsLclsNm": "보건의료", "indsMclsNm": "일반 병원", "indsSclsNm": "내과/소아과"}, "병원"),
    ({"indsLclsNm": "보건/의료", "indsMclsNm": "치과 병원", "indsSclsNm": "치과"}, "병원"),
    # 숙박 → 숙박 (375건)
    ({"indsLclsNm": "숙박", "indsMclsNm": "일반 숙박업", "indsSclsNm": "모텔/여관/여인숙"}, "숙박"),
    # 관광·여가·오락 중 시설성 업종만 문화시설
    ({"indsLclsNm": "관광/여가/오락", "indsMclsNm": "박물관/전시장",
      "indsSclsNm": "미술관"}, "문화시설"),
])
def test_maps_to_seven_group_vocabulary(row, expected):
    assert to_category_group(row) == expected
    assert expected in CATEGORY_GROUPS


@pytest.mark.parametrize("row", [
    # 7종 밖 — 라벨을 만들지 않는다(None). '기타'로 억지로 채우면 라벨이 오염된다
    {"indsLclsNm": "소매", "indsMclsNm": "의류/패션", "indsSclsNm": "여성casual의류"},
    {"indsLclsNm": "생활서비스", "indsMclsNm": "이/미용/건강", "indsSclsNm": "미용실"},
    {"indsLclsNm": "학문/교육", "indsMclsNm": "학원-보습교습입시", "indsSclsNm": "종합학원"},
    # 유흥·게임은 관광/여가/오락이지만 '문화시설' 이 아니다(카카오 CT1 모집단과 다르다)
    {"indsLclsNm": "관광/여가/오락", "indsMclsNm": "유흥주점", "indsSclsNm": "룸살롱/클럽"},
    {"indsLclsNm": "관광/여가/오락", "indsMclsNm": "PC/오락/당구/볼링등",
     "indsSclsNm": "PC방"},
    {},
])
def test_returns_none_outside_seven_groups(row):
    assert to_category_group(row) is None


# ── 1-B. 실측 중분류 어휘 (2026-09-15 감사) ─────────────────────────────────
# 커밋된 Gold 산출물에서 뽑은 **실제** 상가정보 중분류다
# (`gold/*/vacant_{units,floor_units}.json` 의 `grp`/`was` = `indsMclsNm` 최빈값,
#  135파일·65종·등장 13,855회). 처음 규칙은 대분류·소분류만 봐서 이 어휘의
# **65종 중 2종(3.1%)만** 사상했다 — 감사가 그걸 잡았다.
@pytest.mark.parametrize("mcls, expected", [
    # 음식점 — 중분류만 와도 잡아야 한다(대분류가 빠진 호출이 실제로 있었다)
    ("한식", "음식점"), ("서양식", "음식점"), ("일식", "음식점"), ("중식", "음식점"),
    ("주점", "음식점"), ("기타 간이", "음식점"), ("동남아시아", "음식점"),
    ("구내식당·뷔페", "음식점"),
    ("비알코올", "카페"),
    ("의원", "병원"), ("병원", "병원"), ("기타 보건", "병원"),
    ("일반 숙박", "숙박"), ("기타 숙박", "숙박"),
    ("도서관·사적지", "문화시설"),
])
def test_real_mid_category_vocabulary_maps(mcls, expected):
    assert to_category_group({"indsMclsNm": mcls}) == expected


@pytest.mark.parametrize("row, why", [
    # 🔴 감사가 실제로 잡은 오사상 — '음료' 로 카페를 판정하면 소매점이 카페가 된다
    ({"indsMclsNm": "음료 소매"}, "음료 소매(26건)는 소매점이다"),
    # 소매 대분류의 의약·화장품은 병원도 약국도 아니다(약국은 소분류로만 잡는다)
    ({"indsLclsNm": "소매", "indsMclsNm": "의약·화장품 소매"}, "화장품 가게"),
    # 카카오 CT1 문화시설의 모집단은 박물관·미술관·영화관·공연장이다
    ({"indsMclsNm": "유원지·오락"}, "놀이공원·오락실(299건)"),
    ({"indsMclsNm": "스포츠 서비스"}, "체육시설(279건)"),
    # 중분류 '종합 소매' 를 편의점으로 사상하면 슈퍼·잡화까지 편의점이 된다
    ({"indsMclsNm": "종합 소매"}, "종합 소매(483건)"),
    # 7종 밖 — 미사상이 정상이다
    ({"indsMclsNm": "섬유·의복·신발 소매"}, "의류 소매(1,265건)"),
    ({"indsMclsNm": "기타 교육"}, "학원(815건)"),
    ({"indsMclsNm": "이용·미용"}, "미용실(648건)"),
])
def test_real_vocabulary_that_must_not_map(row, why):
    assert to_category_group(row) is None, why


def test_retail_marker_blocks_cafe_and_hospital():
    """'소매' 가 붙은 중분류는 카페·병원으로 가지 않는다 — 오사상 차단 규칙 자체를 고정."""
    assert to_category_group({"indsMclsNm": "음료 소매"}) is None
    assert to_category_group({"indsLclsNm": "보건의료", "indsMclsNm": "의약품 소매"}) is None
    # 다만 소분류가 '약국' 이면 ① 이 먼저 잡는다(소매여도 약국이다)
    assert to_category_group(
        {"indsLclsNm": "소매", "indsMclsNm": "의약·화장품 소매",
         "indsSclsNm": "약국"}) == "약국"


def test_cafe_is_not_folded_into_food():
    """판정 순서 회귀 — 카페가 음식점으로 접히면 라벨이 degenerate 한다.

    2026-08-17 실측: 카카오 category_name 1단계는 카페를 음식점 하위로 접어 음식점이
    78% 였고 그래서 라벨로 부적합했다. 같은 함정을 상가정보에서 반복하지 않는다.
    """
    cafe = {"indsLclsNm": "음식", "indsMclsNm": "비알코올 음료점",
            "indsSclsNm": "커피전문점/카페/다방"}
    assert to_category_group(cafe) == "카페"


def test_pharmacy_is_not_hospital():
    """약국은 보건의료 대분류에 들어가도 '병원'이 아니다 — ① 이 ④ 보다 앞서야 한다."""
    assert to_category_group(
        {"indsLclsNm": "보건의료", "indsMclsNm": "의약/의료품 소매업",
         "indsSclsNm": "약국"}) == "약국"


# ── 2. 필터·표시 계약 ──────────────────────────────────────────────────────────
def test_non_storefront_matches_collector():
    """사무실형 제외 목록이 수집기와 어긋나면 분자·노드 모집단이 갈린다."""
    from data.collectors.building_vacancy import (
        NON_STOREFRONT_LCLS as COLLECTOR_LCLS,
    )
    assert tuple(NON_STOREFRONT_LCLS) == tuple(COLLECTOR_LCLS)


@pytest.mark.parametrize("lcls, expected", [
    ("음식", True), ("소매", True), ("보건의료", True),
    ("과학·기술", False), ("부동산", False), ("시설관리·임대", False),
])
def test_is_storefront(lcls, expected):
    assert is_storefront({"indsLclsNm": lcls}) is expected


def test_category_path_uses_same_separator_as_before():
    """Program 컨텍스트가 마지막 조각을 쓴다 — 구분자가 ' > ' 여야 한다."""
    row = {"indsLclsNm": "음식", "indsMclsNm": "한식", "indsSclsNm": "백반/한정식"}
    assert category_path(row) == "음식 > 한식 > 백반/한정식"
    assert category_path(row).split(" > ")[-1] == "백반/한정식"
    # 공란 계층은 건너뛴다(빈 조각이 남으면 마지막 조각이 "" 가 된다)
    assert category_path({"indsLclsNm": "음식", "indsSclsNm": "백반"}) == "음식 > 백반"


# ── 3. 약관 불변식 — 저장 경로에 카카오가 다시 들어오면 실패한다 ────────────────
def _called_names(tree) -> set[str]:
    """모듈 안에서 호출되는 이름들(`f()` · `mod.f()` 모두)."""
    import ast

    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name):
            out.add(fn.id)
        elif isinstance(fn, ast.Attribute):
            out.add(fn.attr)
    return out


def _string_args(tree) -> set[str]:
    """호출 인자로 쓰인 문자열 리터럴 — 산문(독스트링·주석)은 안 걸린다.

    소스 전체 문자열 검색으로 검사하면 이 교체의 **경위를 적은 문장**이 걸려
    테스트가 문서를 못 쓰게 만든다. 그래서 AST 로 '실제로 호출에 넘어가는 값'만 본다.
    """
    import ast

    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.add(arg.value)
    return out


def _parse(rel: str):
    import ast

    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def test_kakao_collector_does_not_persist():
    """kakao_local 은 Bronze 를 쓰지 않는다(실시간 반환 전용)."""
    tree = _parse("data/collectors/kakao_local.py")
    assert "save_json" not in _called_names(tree), \
        "kakao_local 이 다시 Bronze 에 저장한다 — 약관 위반"
    assert "kakao_places.json" not in _string_args(tree), \
        "kakao_places.json 이 다시 파일 인자로 쓰인다 — 약관 위반"


def test_gold_builder_does_not_read_kakao_bronze():
    """build_gold 가 kakao_places.json 을 읽지 않는다."""
    assert "kakao_places.json" not in _string_args(_parse("data/pipelines/build_gold.py"))


def test_no_pipeline_reads_or_writes_kakao_bronze():
    """저장층 전체 — 어느 수집기·파이프라인도 kakao_places.json 을 다루지 않는다.

    한 곳만 막으면 다음 사람이 옆 모듈에 같은 것을 만든다. 디렉터리 단위로 고정한다.
    """
    offenders = []
    for rel_dir in ("data/collectors", "data/pipelines", "data/validation"):
        for path in sorted((ROOT / rel_dir).glob("*.py")):
            if "kakao_places.json" in _string_args(_parse(str(path.relative_to(ROOT)))):
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"kakao_places.json 을 다시 다루는 모듈: {offenders}"


def test_node_rows_are_sourced_from_public_data(monkeypatch):
    """노드 행 계약 — node_id 접두가 sdsc: 이고 source 가 카카오가 아니다."""
    from data.pipelines import build_gold

    sample = [
        {"bizesId": "MA0101", "bizesNm": "테스트식당", "indsLclsNm": "음식",
         "indsMclsNm": "한식", "indsSclsNm": "백반/한정식", "lon": 127.02, "lat": 37.52,
         "rdnmAdr": "서울 강남구 압구정로 1", "bldMngNo": "1168010100100010000",
         "lnoCd": "1168010100100010000", "flrNo": "1", "hoNo": "101"},
        # 사무실형 — 제외돼야 한다
        {"bizesId": "MA0102", "bizesNm": "테스트공인중개", "indsLclsNm": "부동산",
         "lon": 127.02, "lat": 37.52},
        # bizesId 공란 — 키가 없으면 노드가 될 수 없다
        {"bizesId": "", "bizesNm": "무키", "indsLclsNm": "음식"},
    ]
    monkeypatch.setattr(build_gold, "load_latest", lambda slug, name: sample)

    rows = build_gold._store_node_rows("garosugil", "garosugil")
    assert len(rows) == 1, "사무실형·무키 행이 걸러지지 않았다"
    r = rows[0]
    assert r["node_id"] == "sdsc:MA0101"
    assert r["source"] == "sdsc"
    assert "kakao" not in r["source"]
    assert r["category_group"] == "음식점"
    assert r["category"] == "음식 > 한식 > 백반/한정식"
    assert r["district_id"] == "garosugil"
    # 카카오에는 없던 세 키 — 이게 교체의 이득이다
    assert r["bd_mgt_sn"] and r["pnu"] and r["floor"]
    # place_url 은 카카오 응답 내용이라 더 담지 않는다
    assert "place_url" not in r


def test_hub_iterating_builders_pass_slugs_not_hub_objects(monkeypatch):
    """거점 순회 빌더가 ACTIVE_HUBS 를 **slug 로** 읽는다.

    `ACTIVE_HUBS` 는 `dict[str, PageHub]` 다. `for hub in ACTIVE_HUBS` 는 PageHub 가
    아니라 **키(slug 문자열)** 를 준다 — 이걸 객체로 알고 `hub.slug` 를 쓰면
    AttributeError 로 빌더가 통째로 죽는다(2026-09-15 교체 중 실제로 세 곳에서 냈다).
    Bronze 가 없는 CI 에서도 이 실수는 잡혀야 하므로, load_latest 를 빈 응답으로
    묶어 **순회 자체**를 검사한다(pandas 없이 조기 반환 경로를 탄다).
    """
    from data.config.page_hubs import ACTIVE_HUBS
    from data.pipelines import build_gold

    seen: list[object] = []

    def spy(slug, name):
        seen.append(slug)
        return []

    monkeypatch.setattr(build_gold, "load_latest", spy)
    build_gold.build_platform13_store_graph_nodes()
    build_gold.build_program13_context()

    assert seen, "거점을 한 번도 순회하지 않았다"
    hub_args = [s for s in seen if s != "platform13"]
    assert all(isinstance(s, str) for s in hub_args), \
        f"slug 가 아닌 값이 넘어갔다: {[s for s in hub_args if not isinstance(s, str)]}"
    assert set(hub_args) <= set(ACTIVE_HUBS), \
        f"ACTIVE_HUBS 에 없는 키: {set(hub_args) - set(ACTIVE_HUBS)}"
    assert len(set(hub_args)) == len(ACTIVE_HUBS), "일부 거점을 빠뜨렸다"


def test_gold_audit_reproduces_the_measurement():
    """`--gold` 감사가 저장소 Gold 에서 실제로 돌고, 오사상 유형이 되돌아오지 않는다.

    Bronze 없는 환경(신규 클론·CI)에서도 사상 규칙을 검사할 수 있어야 한다.
    2026-09-15 측정: 파일 135 · 중분류 65종 · 등장 13,855회 · 사상 15종(23.1%)/47.0%.
    Gold 가 재생성되면 수치는 움직이므로 **하한과 불변식**으로만 고정한다.
    """
    from data.config.store_taxonomy import audit_gold

    out = audit_gold()
    assert out["files"] > 0, "Gold 산출물을 못 찾았다 — 감사가 아무것도 세지 않는다"
    assert out["terms"] > 0 and out["occurrences"] > 0
    assert out["mapped_terms"] >= 10, f"사상 어휘가 급감했다: {out['mapped_terms']}"
    assert out["occurrence_pct"] >= 30, f"등장 기준 사상률이 급감했다: {out['occurrence_pct']}%"
    # 핵심 그룹이 살아 있어야 한다 — 하나라도 0 이면 규칙이 무너진 것이다
    assert {"음식점", "병원", "카페", "숙박"} <= set(out["by_group"])


def test_gold_audit_maps_no_retail_term():
    """'소매' 가 든 중분류는 하나도 사상되지 않는다 — 실측이 잡은 오사상 유형의 불변식.

    `--gold` 감사는 중분류만 넘기므로, 여기서 소매가 사상되면 그건 '음료 소매 → 카페'
    같은 오사상이 되돌아온 것이다(약국·편의점은 소분류가 있어야 잡히고, 그건 정상).
    """
    from data.config.store_taxonomy import audit_gold

    out = audit_gold()
    # 그룹별 등장 합이 사상 등장과 일치해야 한다(집계가 새지 않았다)
    assert sum(out["by_group"].values()) == out["mapped_occurrences"]
    # 소매 어휘가 사상되면 미사상 상위에서 사라진다 — 대표 3종이 남아 있는지로 확인한다
    for term in ("섬유·의복·신발 소매", "종합 소매", "의약·화장품 소매"):
        assert to_category_group({"indsMclsNm": term}) is None, term


def test_roadview_sample_has_no_stored_place_names():
    """검증 CSV 에 카카오 상호 열(kakao_names)이 없다 — 건수만 남긴다."""
    csv_path = ROOT / "data" / "validation" / "roadview_sample.csv"
    with csv_path.open(encoding="utf-8-sig") as fp:
        fields = csv.DictReader(fp).fieldnames or []
    assert "kakao_names" not in fields, "카카오 상호가 CSV 에 다시 저장된다 — 약관 위반"
    # 건수·상충 열은 우리 예측에 대한 판정이라 남는다
    assert {"kakao_pip", "kakao_30m", "crosscheck"} <= set(fields)


def test_jipgyegu_sidecar_holds_no_kakao_ids():
    """집계구 배정표가 카카오 장소 id 를 키로 들고 있지 않다.

    node_id 체계가 sdsc:* 로 갈렸으므로 옛 배정은 어차피 죽은 키다 — 지운 뒤
    build_gold(--platform13) → build_node_jipgyegu 로 재생성한다.
    oa_codes(통계청 집계구 코드)는 공공데이터라 그대로 유효하다.
    """
    import json

    path = ROOT / "data" / "silver" / "node_jipgyegu.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert not [k for k in (doc.get("nodes") or {}) if str(k).startswith("kakao:")]
    assert doc.get("oa_codes"), "집계구 코드 목록은 남아 있어야 한다(수집 keep-list)"


# ══════════════════════════════════════════════════════════════════════════
#  어휘 사이드카 (2026-09-16) — 소분류를 Bronze 없이 감사하기 위한 최소 기록
# ══════════════════════════════════════════════════════════════════════════
# 왜: Bronze 는 커밋 안 되고 Gold 공실 산출물은 중분류만 담아 **소분류 어휘가 저장소에
# 하나도 안 남는다.** 2026-09-15 재학습이 그래서 0단계에서 멈췄다(finding §7-2-3-1).
# 아래 테스트는 합성 행만 쓴다 — Bronze 도 네트워크도 타지 않는다.
from data.config import store_taxonomy as _tx  # noqa: E402

_VOCAB_SAMPLE = [
    {"indsLclsNm": "음식", "indsMclsNm": "한식", "indsSclsNm": "백반/한정식",
     "bizesNm": "김밥천국", "lat": 37.5, "lon": 127.0, "bizesId": "MA0101"},
    {"indsLclsNm": "음식", "indsMclsNm": "한식", "indsSclsNm": "백반/한정식",
     "bizesNm": "다른집", "lat": 37.6, "lon": 127.1, "bizesId": "MA0102"},
    {"indsLclsNm": "소매", "indsMclsNm": "종합 소매", "indsSclsNm": "편의점",
     "bizesNm": "가게", "lat": 37.7, "lon": 127.2, "bizesId": "MA0103"},
    {"indsLclsNm": "부동산", "indsMclsNm": "부동산 중개", "indsSclsNm": "부동산 중개",
     "bizesNm": "공인중개사", "lat": 37.8, "lon": 127.3, "bizesId": "MA0104"},
]


def test_vocab_table_aggregates_the_three_tier_code_only():
    table = _tx.vocab_table(_VOCAB_SAMPLE)
    by_scls = {t["scls"]: t for t in table}
    assert by_scls["백반/한정식"]["n"] == 2       # 같은 삼단은 합쳐진다
    assert by_scls["편의점"]["n"] == 1
    assert by_scls["백반/한정식"]["group"] == "음식점"


def test_vocab_table_carries_no_place_records():
    """이 사이드카는 커밋된다 — 점포를 식별하는 값이 한 줄도 들어가면 안 된다.

    (상가정보는 공공데이터라 적재 자체는 자유롭지만, 커밋되는 산출물의 성격을
    '분류 어휘 집계'로 못박아 둔다 — 여기가 넓어지면 Bronze 를 커밋하는 것과 같아진다.)
    """
    forbidden = {"bizesNm", "bizesId", "lat", "lon", "rdnmAdr", "bldMngNo",
                 "name", "node_id", "road_address"}
    for row in _tx.vocab_table(_VOCAB_SAMPLE):
        assert not (set(row) & forbidden), row
        assert set(row) == {"lcls", "mcls", "scls", "n", "storefront", "group"}


def test_vocab_table_marks_non_storefront_like_the_collector():
    table = {t["scls"]: t for t in _tx.vocab_table(_VOCAB_SAMPLE)}
    assert table["부동산 중개"]["storefront"] is False   # 사무실형 대분류
    assert table["백반/한정식"]["storefront"] is True


def test_vocab_verdicts_confirm_or_say_absent():
    """프롬프트의 완료 기준 — 세 규칙 각각이 '확정' 또는 '이 표본에 없다' 로 닫힌다."""
    v = _tx.vocab_verdicts(_tx.vocab_table(_VOCAB_SAMPLE))
    assert v["편의점"]["confirmed"] is True
    assert "편의점" in v["편의점"]["scls"]
    # 이 합성 표본에는 약국·카페 소분류가 없다 — 추측으로 채우지 않고 '없다'로 닫는다
    assert v["약국"]["confirmed"] is False
    assert v["카페"]["confirmed"] is False
    assert v["약국"]["why"]          # 왜 미검증인지가 판정에 같이 실린다


def test_audit_vocab_reads_the_sidecar_without_bronze(tmp_path, capsys):
    _tx.write_vocab(_tx.vocab_table(_VOCAB_SAMPLE),
                    {"built": "2026-09-16", "hubs": 66, "rows": 4, "storefront": 3},
                    root=tmp_path)
    out = _tx.audit_vocab(root=tmp_path)
    assert out["exists"] is True
    # 가두 분류조합 2종 — 부동산 중개는 사무실형이라 빠진다(행 4 → 삼단 3종 → 가두 2종)
    assert out["terms"] == 2
    assert out["mapped_terms"] == 2               # 백반/한정식 · 편의점
    assert out["occurrences"] == 3                # 백반 2 + 편의점 1
    assert out["occurrence_pct"] == 100.0
    assert out["by_group"] == {"음식점": 2, "편의점": 1}
    assert out["rule_drift_terms"] == 0
    assert "편의점" in capsys.readouterr().out


def test_audit_vocab_flags_rule_drift(tmp_path):
    """규칙을 고친 뒤 사이드카를 다시 안 만든 상태를 잡는다 — 조용히 지나가면 안 된다."""
    table = _tx.vocab_table(_VOCAB_SAMPLE)
    for t in table:
        if t["scls"] == "편의점":
            t["group"] = "음식점"                  # 옛 규칙이 냈다고 치자
    _tx.write_vocab(table, {"built": "2026-09-16", "hubs": 1}, root=tmp_path)
    out = _tx.audit_vocab(root=tmp_path)
    assert out["rule_drift_terms"] == 1
    assert out["by_group"]["편의점"] == 1          # 수치는 **현재 규칙** 기준이다


def test_audit_vocab_says_so_when_the_sidecar_is_missing(tmp_path):
    out = _tx.audit_vocab(root=tmp_path)
    assert out["exists"] is False                 # 없는 것을 추측으로 메우지 않는다


def test_committed_sidecar_if_present_holds_no_place_records():
    """저장소에 사이드카가 커밋되면 그 내용도 같은 불변식을 지켜야 한다."""
    import json

    path = _tx.vocab_path()
    if not path.exists():
        pytest.skip("어휘 사이드카 미생성 — Bronze 가 있는 머신의 --audit 가 만든다")
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc.get("schema") == _tx.VOCAB_SCHEMA
    for row in doc["terms"]:
        assert set(row) == {"lcls", "mcls", "scls", "n", "storefront", "group"}


def test_audit_writes_the_sidecar_when_bronze_exists(tmp_path, monkeypatch, capsys):
    """생산 경로 — Bronze 가 있는 머신에서 `--audit` 가 사이드카를 쓴다.

    이 저장소의 CI·원격 세션에는 Bronze 가 없어서 실행으로 확인할 수 없는 경로다.
    그래서 `load_latest` 를 합성 행으로 갈아끼워 **쓰기까지** 확인한다 —
    안 그러면 '돌려보지 않은 생산자'를 커밋하게 된다.
    """
    import json

    from data.collectors import common as _common

    monkeypatch.setattr(_common, "load_latest",
                        lambda slug, name: _VOCAB_SAMPLE if name == "stores_raw.json" else None)
    out = _tx.audit(["garosugil"], root=tmp_path)

    assert out["rows"] == len(_VOCAB_SAMPLE)
    assert out["vocab_terms"] == 3                      # 삼단 3종(사무실형 포함)
    path = _tx.vocab_path(tmp_path)
    assert path.exists()
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["schema"] == _tx.VOCAB_SCHEMA
    assert doc["hubs"] == 1 and doc["built"]
    # 쓴 것을 그대로 다시 읽어 감사가 성립한다(왕복)
    assert _tx.audit_vocab(root=tmp_path)["mapped_terms"] == 2
    assert "커밋할 것" in capsys.readouterr().out      # 커밋하라고 말해 준다
