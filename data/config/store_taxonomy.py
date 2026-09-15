# -*- coding: utf-8 -*-
"""상가정보 업종 계층 → GNN 라벨 사상 (2026-09-15 신설).

## 왜 생겼나

GNN 노드의 라벨은 **카카오 `category_group_name` 7종**(음식점·카페·편의점·병원·약국·
숙박·문화시설)이었다. 그런데 카카오 로컬 API 는 응답 결과의 저장을 허용하지 않는다
(실시간 호출만) — 상호·좌표·`place_url` 을 Bronze 파일과 Gold 노드로 영구화하던 경로가
약관에 저촉했다. 근거와 경위는 `docs/finding-map-provider-google-2026-09-15.md` §7-2.

그래서 저장층을 **소상공인 상가(상권)정보**(공공데이터포털 15012005, 기관 B553077)로
옮긴다. 이쪽은 공공데이터라 영구 보관·재배포에 제약이 없고, 이미 `building_vacancy.py`
가 거점별 `bronze/{거점}/{날짜}/stores_raw.json` 으로 수집해 두고 있다.

## 왜 '조인' 이 아니라 '사상' 인가

상가정보 라벨을 카카오 노드에 **붙이는**(조인) 방식은 2026-08-17 에 실측으로 기각됐다 —
상호 일치 42.01%, 동일 좌표 중복률 **92.31%**(상가정보 좌표는 건물 단위이고 층·호는
`flrNo`/`hoNo` 별도 필드라 건물 안의 점포를 좌표로 구분할 수 없다).
→ `docs/finding-sequence-and-accuracy-2026-08-17.md` §5

여기서 하는 것은 조인이 아니다. **상가정보 행의 자기 업종 계층만 보고** 라벨을 정한다.
행 단위 식별 문제가 아예 발생하지 않는다.

## 라벨 어휘를 왜 7종으로 유지하나

게이트(`test_offprior_top3` · Top-3)와 서빙 체크포인트(`ml/artifacts/industry_gnn.pt`
의 `classes`)가 7종 어휘에 맞춰져 있다. 어휘를 바꾸면 기준선이 같이 움직여
**약관 조치와 정확도 변화가 한 커밋에 섞인다.** 그래서 두 컬럼을 같이 낸다:

  `category_group`  7종 호환 라벨 — 해당 없으면 None(→ Gold 에서 "미분류")
  `inds_lcls/mcls/scls`  상가정보 원본 계층 — 그래프 재구축(대분류 10 / 중분류 75 /
                         소분류 247) 경로를 재수집 없이 열어 둔다

계층별 기준선은 이미 측정돼 있다(같은 §6 표): 7종 Top-3 89.7% ↔ 상가정보 대분류 69.9%.
**어휘 교체는 재학습·게이트 재산정이 따르는 별도 판단이다.** 이 파일은 그 판단을
강제하지 않는다.

## 어휘 확정 상태 — ⚠ 부분 실측

`indsLclsNm` 은 코드에서 이미 쓰이는 값으로 확인된다(`NON_STOREFRONT_LCLS` =
과학·기술 / 부동산 / 시설관리·임대). 중·소분류 문자열은 **이 저장소에 표본이 없어**
(Bronze 는 커밋되지 않는다) 부분 일치 규칙으로 쓴다. 실제 어휘로 조이려면:

    python -m data.config.store_taxonomy --audit          # 전 거점
    python -m data.config.store_taxonomy --audit garosugil

미사상 상위 어휘와 사상 커버리지를 찍는다. 규칙을 조일 때 이 출력을 근거로 남길 것.
"""
from __future__ import annotations

import sys
from collections import Counter

# ── 7종 라벨 어휘 — 카카오 category_group_name 과 문자열까지 같아야 한다 ──────
# 체크포인트 classes 와 대조: python -c "import torch; print(torch.load(
#   'ml/artifacts/industry_gnn.pt', map_location='cpu', weights_only=False)['classes'])"
GROUP_FOOD = "음식점"
GROUP_CAFE = "카페"
GROUP_CVS = "편의점"
GROUP_HOSPITAL = "병원"
GROUP_PHARMACY = "약국"
GROUP_LODGING = "숙박"
GROUP_CULTURE = "문화시설"

CATEGORY_GROUPS = (
    GROUP_FOOD, GROUP_CAFE, GROUP_CVS,
    GROUP_HOSPITAL, GROUP_PHARMACY, GROUP_LODGING, GROUP_CULTURE,
)

# ── 사상 불가 업종 — 분류체계에 아예 없다(2026-08-17 실측) ──────────────────
# 공방: mcls 75 · scls 247 · ksic 306 전수 검색 0건
# 배달전문: KSIC '계약배달 판매업' 23건(0.01%)
# 라벨을 만들 수 없다는 사실 자체가 근거다 — 재학습으로 풀리지 않는다.
UNMAPPABLE_DEMAND = ("공방", "배달전문")

# ── 사무실형 업종 — 상가 호수 분모와 도메인이 다르다 ────────────────────────
# building_vacancy.NON_STOREFRONT_LCLS 와 **같은 값이어야 한다**. 거기서 import 하지
# 않는 이유: 이 모듈은 requests 의존이 없는 순수 규칙이라 수집기를 끌고 오지 않는다.
# 어긋나면 test_store_taxonomy.py::test_non_storefront_matches_collector 가 잡는다.
NON_STOREFRONT_LCLS = ("과학·기술", "부동산", "시설관리·임대")


def _has(text: str, *needles: str) -> bool:
    return any(n in text for n in needles)


def to_category_group(row: dict) -> str | None:
    """상가정보 한 행 → 7종 라벨. 해당 없으면 None.

    판정 순서가 규칙의 일부다 — **좁은 것부터** 본다. '카페'는 대분류가 음식이고
    '약국'·'편의점'은 대분류가 소매라, 대분류를 먼저 보면 둘 다 음식점/기타로 접힌다.
    2026-08-17 교차표(상호일치 ≤50m)가 확인한 대응을 그대로 옮긴 것이다:
      병원→보건의료 2,025 · 약국→소매(의약·화장품) 744 · 숙박→숙박 375 ·
      음식점→음식 9,848 · 카페→음식(비알코올) 2,283 · 편의점→소매 276
    """
    lcls = str(row.get("indsLclsNm") or "")
    mcls = str(row.get("indsMclsNm") or "")
    scls = str(row.get("indsSclsNm") or "")

    # ① 약국 — 소매(의약·화장품) 하위. '약국' 은 소분류에만 뜬다
    if _has(scls, "약국") or _has(mcls, "약국"):
        return GROUP_PHARMACY

    # ② 편의점 — 소매(종합 소매점) 하위
    if _has(scls, "편의점") or _has(mcls, "편의점"):
        return GROUP_CVS

    # ③ 카페 — 음식(비알코올 음료점) 하위. 커피전문점·다방·제과류가 같은 묶음이다
    if _has(mcls, "비알코올", "음료") or _has(scls, "카페", "커피", "다방", "찻집"):
        return GROUP_CAFE

    # ④ 병원 — 대분류 보건의료. 의원·병원·한의원·치과 전부 포함이고, 같은 대분류의
    #    약국은 ① 에서 이미 빠졌다
    if _has(lcls, "보건", "의료") and not _has(scls, "약국"):
        return GROUP_HOSPITAL

    # ⑤ 숙박 — 대분류 숙박
    if _has(lcls, "숙박"):
        return GROUP_LODGING

    # ⑥ 문화시설 — 관광·여가·오락 대분류 중 '시설'성 업종만. 유흥·게임은 제외한다
    #    (카카오 CT1 문화시설의 모집단이 박물관·미술관·영화관·공연장이다)
    if _has(lcls, "관광", "여가", "오락", "예술", "스포츠"):
        if _has(mcls, "박물관", "미술관", "공연", "영화", "도서", "전시") or \
           _has(scls, "박물관", "미술관", "공연장", "영화관", "도서관", "전시", "갤러리"):
            return GROUP_CULTURE
        return None

    # ⑦ 음식점 — 대분류 음식에서 카페(③)가 빠진 나머지
    if _has(lcls, "음식"):
        return GROUP_FOOD

    return None


def is_storefront(row: dict) -> bool:
    """가두 점포인가 — 사무실형 대분류를 제외한다.

    `build_page_master` 가 분자를 셀 때 쓰는 것과 같은 필터다. 그래프 노드에도 같은
    필터를 걸어야 분모(상가 호수)와 모집단이 맞는다.
    """
    return str(row.get("indsLclsNm") or "") not in NON_STOREFRONT_LCLS


def category_path(row: dict) -> str:
    """사람이 읽는 업종 경로 — '음식 > 한식 > 백반/한정식'.

    카카오 `category_name` 의 자리를 메운다(Program 컨텍스트가 마지막 조각을 쓴다).
    """
    parts = [str(row.get(k) or "").strip()
             for k in ("indsLclsNm", "indsMclsNm", "indsSclsNm")]
    return " > ".join(p for p in parts if p)


# ══════════════════════════════════════════════════════════════════════════
#  감사 — 실제 Bronze 어휘로 규칙을 조일 때 쓴다
# ══════════════════════════════════════════════════════════════════════════
def audit(slugs: list[str] | None = None) -> dict:
    """거점 Bronze `stores_raw.json` 을 훑어 사상 커버리지와 미사상 어휘를 센다."""
    from data.collectors.common import load_latest
    from data.config.page_hubs import ACTIVE_HUBS

    targets = slugs or list(ACTIVE_HUBS)   # dict[str, PageHub] — 키가 거점 slug 다
    total = storefront = mapped = 0
    unmapped_lcls: Counter = Counter()
    unmapped_scls: Counter = Counter()
    by_group: Counter = Counter()
    missing: list[str] = []

    for slug in targets:
        rows = load_latest(slug, "stores_raw.json")
        if not rows:
            missing.append(slug)
            continue
        for r in rows:
            total += 1
            if not is_storefront(r):
                continue
            storefront += 1
            g = to_category_group(r)
            if g:
                mapped += 1
                by_group[g] += 1
            else:
                unmapped_lcls[str(r.get("indsLclsNm") or "(공란)")] += 1
                unmapped_scls[str(r.get("indsSclsNm") or "(공란)")] += 1

    out = {
        "hubs": len(targets), "hubs_missing_bronze": missing,
        "rows": total, "storefront": storefront, "mapped": mapped,
        "mapped_pct": round(mapped / storefront * 100, 2) if storefront else None,
        "by_group": dict(by_group.most_common()),
        "unmapped_top_lcls": dict(unmapped_lcls.most_common(15)),
        "unmapped_top_scls": dict(unmapped_scls.most_common(25)),
    }
    print(f"[taxonomy] 거점 {out['hubs']}곳 · 행 {total:,} · 가두 {storefront:,}")
    if missing:
        print(f"[taxonomy] ⚠ Bronze 없음 {len(missing)}곳: {', '.join(missing[:8])}"
              f"{' …' if len(missing) > 8 else ''}")
    if storefront:
        print(f"[taxonomy] 7종 사상 {mapped:,} ({out['mapped_pct']}%)")
        for g, n in by_group.most_common():
            print(f"    {g}: {n:,}")
        print("[taxonomy] 미사상 대분류 상위")
        for k, n in unmapped_lcls.most_common(10):
            print(f"    {k}: {n:,}")
        print("[taxonomy] 미사상 소분류 상위")
        for k, n in unmapped_scls.most_common(15):
            print(f"    {k}: {n:,}")
    else:
        print("[taxonomy] 셀 것이 없다 — building_vacancy 로 stores_raw 수집이 먼저다")
    return out


def main(argv: list[str]) -> int:
    if "--audit" not in argv:
        print(__doc__)
        print("사용: python -m data.config.store_taxonomy --audit [거점...]")
        return 0
    slugs = [a for a in argv if not a.startswith("-")]
    audit(slugs or None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
