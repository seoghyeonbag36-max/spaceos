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
