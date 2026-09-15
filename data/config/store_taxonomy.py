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

## 어휘 확정 상태 — 중분류는 실측했다 (2026-09-15 감사)

Bronze 는 커밋되지 않아 `--audit` 가 셀 것이 없었다. 대신 **커밋된 Gold 산출물**에서
실제 상가정보 중분류를 뽑았다 — `gold/*/vacant_{units,floor_units}.json` 의
`grp`/`was` 가 `building_vacancy.py:346` 의 `indsMclsNm` 최빈값이다.
**135파일 · 고유 65종 · 등장 13,855회.**

그 감사가 결함 셋을 잡았다:

| 결함 | 내용 |
|---|---|
| 중분류 통째 미사상 | 대분류·소분류만 보던 규칙이 65종 중 **2종(3.1%)** 만 사상했다. '한식'(1,919)·'의원'(1,023)·'일반 숙박'(220)이 전부 빠졌다 |
| 오사상 1건 | `'음료'` 로 카페를 판정해 **'음료 소매'(26)** 가 카페가 됐다 — 소매점이다 |
| 시설성 판정 누락 | 실측 문화시설 어휘가 **'도서관·사적지'(34)** 인데 규칙은 박물관/미술관만 찾았다 |

고친 뒤 재측정: 어휘 기준 **3.1% → 23.1%**(15/65종) · 등장 기준 **6.6% → 47.0%**.
미사상 잔여는 소매·교육·미용·유원지·스포츠로 **7종 밖이라 미사상이 정상**이다.

⚠ 이 47% 를 프로덕션 사상률로 읽지 말 것. 측정 모집단이 **공실·저활성 건물의 대표
업종**이라 소매·교육으로 치우쳐 있고, `편의점`(← 종합 소매)·`약국`(← 의약·화장품 소매)은
**소분류가 있어야** 잡히므로 이 표본에서는 0 이다. 전수 사상률은 Bronze 가 있는 데서:

    python -m data.config.store_taxonomy --audit          # 전 거점
    python -m data.config.store_taxonomy --audit garosugil

Bronze 가 없는 데(신규 클론·CI)서 위 감사를 **재현**하려면:

    python -m data.config.store_taxonomy --gold

⚠ **소분류 어휘는 아직 실측하지 못했다.** `편의점`·`약국`·`커피전문점` 판정이 소분류
문자열에 달려 있는데 저장소에 소분류 표본이 없다(Gold 는 중분류만 담는다).
그 실측을 하는 절차·통과 조건·금지 사항이 프롬프트로 정리돼 있다:

    docs/prompt-store-taxonomy-scls-2026-09-15.md

⚠ 그 작업 전까지 세 규칙(`scls` 의 "편의점"·"약국"·"카페/커피/다방/찻집")은
**미검증 추측**이다. 값이 안 맞으면 그 셋을 먼저 의심할 것.

## 왜 Bronze 없는 머신에서 이 실측이 매번 막히나 (2026-09-16 조치)

소분류 어휘가 **저장소 어디에도 안 남기 때문**이다 — Bronze 는 커밋되지 않고, 커밋된
Gold(`vacant_units.grp`)는 중분류만 담는다. 2026-09-15 재학습 시도가 정확히 여기서
멈췄다(finding §7-2-3-1). 소스가 공공데이터로 바뀐 뒤로는 그 제약이 불필요하다:
**점포 레코드가 아니라 분류 어휘 집계만** 남기면 된다.

    python -m data.config.store_taxonomy --audit    # Bronze 있는 머신 — 사이드카를 쓴다
    git add data/gold/store_taxonomy_vocab.json     # ← 이 커밋이 이 문제를 닫는다
    python -m data.config.store_taxonomy --vocab    # Bronze 없는 머신 — 소분류까지 감사

`--vocab` 은 사이드카의 분류 삼단을 **현재 규칙으로 다시 사상해** 사상률을 내고,
위 세 규칙 각각을 '실측 문자열 확정' 또는 '이 표본에 없다' 로 닫는다.
사이드카가 없으면 그 사실만 말하고 끝난다 — 추측으로 메우지 않는다.
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

# ── 실측 중분류 어휘 (2026-09-15) ────────────────────────────────────────────
# 저장소에 커밋된 Gold 산출물에서 **실제 상가정보 중분류 65종**을 뽑아 확정했다
# (`gold/*/vacant_{units,floor_units}.json` 의 `grp`/`was` = `building_vacancy.py:346`
#  의 `indsMclsNm` 최빈값 · 135파일 · 등장 13,855회).
#
# 이 상수가 필요한 이유: 종전 규칙은 **대분류와 소분류만** 봤다. 대분류(`indsLclsNm`)가
# 빠진 호출에서는 '한식'·'의원'·'일반 숙박' 같은 **중분류가 통째로 미사상**된다.
# 실측 결과가 그것을 잡았다 — 65종 중 2종(3.1%)만 사상됐다.
# 중분류만으로 판정할 수 있는 것은 여기서 직접 판정한다.
#
# ⚠ '편의점'(← 종합 소매)과 '약국'(← 의약·화장품 소매)은 **중분류로 가를 수 없다.**
#   둘 다 소분류라서, 대분류·소분류가 있는 정상 호출에서만 잡힌다. 그게 맞는 동작이다 —
#   중분류 '종합 소매'를 편의점으로 사상하면 슈퍼·잡화까지 편의점이 된다.
MCLS_FOOD = ("한식", "서양식", "일식", "중식", "주점", "기타 간이",
             "동남아시아", "구내식당", "뷔페", "분식", "제과")
MCLS_CAFE = ("비알코올",)
MCLS_HOSPITAL = ("의원", "병원", "기타 보건", "치과", "한의원")
MCLS_LODGING = ("일반 숙박", "기타 숙박")
MCLS_CULTURE = ("도서관", "사적지", "박물관", "미술관", "공연", "영화")

# 소매업은 7종에서 제외한다 — 실측에서 '음료 소매'가 카페로 잘못 사상됐다(26건).
# '음료'만 보고 카페를 판정하면 음료 **소매점**(편의점형 판매)이 카페가 된다.
RETAIL_MARKER = "소매"

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

    # ③ 카페 — 중분류 '비알코올' 또는 소분류 커피전문점/카페/다방.
    #    ⚠ '음료' 만 보고 판정하면 안 된다 — 실측 어휘에 **'음료 소매'**(26건)가 있고
    #    그건 소매점이다(2026-09-15 실측이 잡은 오사상).
    if not _has(mcls, RETAIL_MARKER) and not _has(scls, RETAIL_MARKER):
        if _has(mcls, *MCLS_CAFE) or _has(scls, "카페", "커피", "다방", "찻집"):
            return GROUP_CAFE

    # ④ 병원 — 대분류 보건의료 **또는** 중분류 의원/병원/기타 보건.
    #    소매(의약·화장품 소매)는 제외한다 — 약국은 ① 에서 이미 빠졌고, 화장품 가게가
    #    병원으로 접히면 안 된다.
    if not _has(mcls, RETAIL_MARKER) and not _has(scls, "약국"):
        if _has(lcls, "보건", "의료") or _has(mcls, *MCLS_HOSPITAL):
            return GROUP_HOSPITAL

    # ⑤ 숙박 — 대분류 숙박 또는 중분류 일반/기타 숙박
    if _has(lcls, "숙박") or _has(mcls, *MCLS_LODGING):
        return GROUP_LODGING

    # ⑥ 문화시설 — '시설'성 업종만. 실측 중분류의 '도서관·사적지'가 여기다.
    #    유원지·오락(299)·스포츠 서비스(279)는 **제외** — 카카오 CT1 의 모집단은
    #    박물관·미술관·영화관·공연장이고, 놀이공원·오락실·체육시설은 다른 그룹이다.
    if _has(mcls, *MCLS_CULTURE) or \
       _has(scls, "박물관", "미술관", "공연장", "영화관", "도서관", "전시", "갤러리"):
        return GROUP_CULTURE
    if _has(lcls, "관광", "여가", "오락", "예술", "스포츠"):
        return None      # 대분류는 맞지만 시설성이 아니다 — 음식점(⑦)으로 새지 않게 막는다

    # ⑦ 음식점 — 대분류 음식(카페는 ③ 에서 빠졌다) 또는 중분류 실측 어휘
    if _has(lcls, "음식") or _has(mcls, *MCLS_FOOD):
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
def audit(slugs: list[str] | None = None, root=None) -> dict:
    """거점 Bronze `stores_raw.json` 을 훑어 사상 커버리지와 미사상 어휘를 센다."""
    from data.collectors.common import load_latest
    from data.config.page_hubs import ACTIVE_HUBS

    targets = slugs or list(ACTIVE_HUBS)   # dict[str, PageHub] — 키가 거점 slug 다
    total = storefront = mapped = 0
    vocab_counts: Counter = Counter()      # 사이드카용 — 분류 삼단만 센다
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
            vocab_counts[vocab_key(r)] += 1
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
        # 25개까지 찍는다 — 이 목록이 소분류 규칙을 조일 때의 판단 재료다
        # (`docs/prompt-store-taxonomy-scls-2026-09-15.md` 가 이 출력을 전제한다).
        print("[taxonomy] 미사상 소분류 상위")
        for k, n in unmapped_scls.most_common(25):
            print(f"    {k}: {n:,}")
        # 여기서 찾지 말 것 — 분류체계에 아예 없는 수요다(2026-08-17 전수 검색).
        print(f"[taxonomy] ※ 사상 불가(분류체계 부재): {' · '.join(UNMAPPABLE_DEMAND)}"
              f" — 라벨을 만들 수 없다. 재학습으로 풀리지 않는다")
        # 어휘를 저장소에 남긴다 — 이 파일이 있어야 다음 사람이 Bronze 없이 감사한다.
        # 점포 레코드가 아니라 분류 삼단 집계다(위 VOCAB_SCHEMA 주석).
        from datetime import date
        table = vocab_table_from_counts(vocab_counts)
        path = write_vocab(table, {"built": date.today().isoformat(),
                                   "hubs": len(targets) - len(missing),
                                   "rows": total, "storefront": storefront}, root=root)
        out["vocab_path"] = str(path)
        out["vocab_terms"] = len(table)
        print(f"[taxonomy] 어휘 사이드카 {len(table):,}종 → {path}")
        print("[taxonomy] ⚠ 이 파일을 **커밋할 것** — 커밋해야 Bronze 없는 머신에서 "
              "`--vocab` 으로 소분류까지 감사된다(2026-09-15 재학습이 막힌 자리다)")
        for label, v in vocab_verdicts(
                [t for t in table if t.get("storefront")]).items():
            mark = "✅" if v["confirmed"] else "❌ 이 표본에 없다 —"
            detail = (", ".join(f"{k}({n:,})" for k, n in v["scls"].items())
                      if v["confirmed"] else v["why"])
            print(f"    {mark} {label} {detail}")
    else:
        print("[taxonomy] 셀 것이 없다 — building_vacancy 로 stores_raw 수집이 먼저다")
    return out


def audit_gold(root=None) -> dict:
    """Bronze 없이 **커밋된 Gold** 로 중분류 어휘를 감사한다 (2026-09-15 신설).

    Bronze(`stores_raw.json`)는 커밋되지 않으므로 신규 클론·CI 에서는 `audit()` 가 셀
    것이 없다. 그때도 규칙을 검사할 수 있어야 한다 — `gold/*/vacant_{units,
    floor_units}.json` 의 `grp`/`was` 가 `building_vacancy.py:346` 의 `indsMclsNm`
    최빈값이라 **실제 중분류 어휘**가 저장소에 남아 있다.

    ⚠ 이 수치는 전수 사상률이 아니다. 모집단이 **공실·저활성 건물의 대표 업종**이라
    소매·교육으로 치우치고, 소분류가 없어 `편의점`·`약국` 은 구조적으로 0 이다.
    """
    import json
    from pathlib import Path

    from data.collectors.common import GOLD

    base = Path(root) if root else GOLD
    vocab: Counter = Counter()
    files = 0
    for name in ("vacant_units.json", "vacant_floor_units.json"):
        for path in sorted(base.glob(f"*/{name}")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            files += 1
            rows = doc.get("units") or doc.get("rows") or (doc if isinstance(doc, list) else [])
            for r in rows:
                for key in ("grp", "was"):
                    term = str(r.get(key) or "").strip()
                    if term:
                        vocab[term] += 1

    mapped: list[tuple[str, int, str]] = []
    unmapped: list[tuple[str, int]] = []
    for term, n in vocab.most_common():
        g = to_category_group({"indsMclsNm": term})
        (mapped.append((term, n, g)) if g else unmapped.append((term, n)))
    m_hits = sum(n for _, n, _ in mapped)
    u_hits = sum(n for _, n in unmapped)
    total = m_hits + u_hits

    out = {
        "source": "gold/*/vacant_{units,floor_units}.json grp·was (= indsMclsNm 최빈값)",
        "files": files, "terms": len(vocab), "occurrences": total,
        "mapped_terms": len(mapped), "mapped_occurrences": m_hits,
        "term_pct": round(len(mapped) / len(vocab) * 100, 1) if vocab else None,
        "occurrence_pct": round(m_hits / total * 100, 1) if total else None,
        "by_group": dict(Counter({g: 0 for _, _, g in mapped})),
        "unmapped_top": dict(unmapped[:20]),
    }
    by_group: Counter = Counter()
    for _, n, g in mapped:
        by_group[g] += n
    out["by_group"] = dict(by_group.most_common())

    print(f"[taxonomy:gold] 파일 {files} · 고유 중분류 {len(vocab)}종 · 등장 {total:,}회")
    if not vocab:
        print("[taxonomy:gold] Gold 산출물이 없다 — build_vacant_units 먼저")
        return out
    print(f"[taxonomy:gold] 어휘 기준 사상 {len(mapped)}/{len(vocab)}종 ({out['term_pct']}%)")
    print(f"[taxonomy:gold] 등장 기준 사상 {m_hits:,}/{total:,}회 ({out['occurrence_pct']}%)")
    for term, n, g in mapped:
        print(f"    {g} ← {term} ({n:,})")
    print(f"[taxonomy:gold] 그룹별 등장: {out['by_group']}")
    print("[taxonomy:gold] 미사상 상위 (소매·교육·미용 등 7종 밖이면 정상)")
    for term, n in unmapped[:12]:
        print(f"    {term}: {n:,}")
    print("[taxonomy:gold] ⚠ 전수 사상률이 아니다 — 모집단이 공실·저활성 건물 대표 업종이고 "
          "소분류가 없어 편의점·약국은 구조적으로 0 이다. 전수는 --audit(Bronze) 로.")
    return out


# ══════════════════════════════════════════════════════════════════════════
#  어휘 사이드카 — 소분류를 저장소에 남긴다 (2026-09-16 신설)
# ══════════════════════════════════════════════════════════════════════════
# 왜 생겼나: **소분류 어휘가 저장소 어디에도 안 남는다.** Bronze 는 커밋되지 않고,
# 커밋된 Gold(`vacant_units.grp`)는 중분류만 담는다. 그래서 Bronze 가 없는 머신
# (신규 클론·CI·원격 세션)에서는 `--audit` 가 셀 것이 없고, `편의점`·`약국`·
# `커피전문점` 세 규칙이 **미검증 추측인 채로 남는다** — 2026-09-15 재학습 시도가
# 정확히 여기서 멈췄다(finding §7-2-3-1).
#
# 고치는 방법은 Bronze 를 커밋하는 게 아니라, **어휘 집계만** 남기는 것이다.
# 이 사이드카에는 분류 삼단(대/중/소)과 등장 횟수뿐이고 상호·좌표·bizesId 같은
# 점포 레코드는 들어가지 않는다 — 공공데이터의 분류체계 어휘이고 용량은 수십 KB 다.
# 한 번 만들어 커밋하면 그 뒤로는 **Bronze 없이 규칙을 감사할 수 있다**(--vocab).
VOCAB_SCHEMA = "store-taxonomy-vocab/1"
VOCAB_NAME = "store_taxonomy_vocab.json"

# 미검증 추측 3종 — `--vocab`·`--audit` 가 이 규칙들이 실제 어휘에 걸리는지 판정한다.
# (라벨, 그 라벨을 내야 하는 규칙의 설명)
UNVERIFIED_SCLS_RULES = (
    (GROUP_CVS, "중분류 '종합 소매' 하위 — 슈퍼·잡화와 갈라야 한다"),
    (GROUP_PHARMACY, "중분류 '의약·화장품 소매' 하위 — 화장품 가게와 갈라야 한다"),
    (GROUP_CAFE, "중분류 '비알코올' 하위 — 커피전문점/다방/찻집 표기 확인 필요"),
)


def vocab_table(rows) -> list[dict]:
    """점포 행 → **분류 삼단 집계**. 점포 레코드는 한 줄도 담지 않는다.

    순수 함수다(파일·네트워크를 안 탄다) — 그래서 Bronze 없이도 테스트된다.
    `is_storefront` 필터는 여기서 걸지 않고 플래그로 남긴다: 사무실형 대분류가
    무엇이었는지도 감사 재료이기 때문이다(분모가 달라지는 자리).
    """
    agg: Counter = Counter()
    for r in rows:
        agg[vocab_key(r)] += 1
    return vocab_table_from_counts(agg)


def vocab_key(row: dict) -> tuple[str, str, str]:
    """집계 키 — 분류 삼단만. 점포를 식별하는 값은 키에 안 들어간다."""
    return (str(row.get("indsLclsNm") or ""), str(row.get("indsMclsNm") or ""),
            str(row.get("indsSclsNm") or ""))


def vocab_table_from_counts(agg: Counter) -> list[dict]:
    """이미 센 삼단 카운터 → 사이드카 행. `audit()` 는 222,260행을 메모리에 쌓지 않고
    거점을 훑으면서 이 카운터만 키운다(이 환경은 메모리 여유가 빠듯하다)."""
    out = []
    for (lcls, mcls, scls), n in agg.most_common():
        row = {"indsLclsNm": lcls, "indsMclsNm": mcls, "indsSclsNm": scls}
        out.append({"lcls": lcls, "mcls": mcls, "scls": scls, "n": n,
                    "storefront": bool(is_storefront(row)),
                    # 이 커밋 시점 규칙이 낸 값 — `--vocab` 이 재계산해서 대조한다.
                    # 규칙을 고쳤는데 사이드카가 그대로면 그 표류를 잡아 준다.
                    "group": to_category_group(row) or ""})
    return out


def vocab_verdicts(table: list[dict]) -> dict[str, dict]:
    """미검증 3규칙 판정 — 실제 어휘에서 그 라벨을 내는 **소분류 문자열**을 모은다.

    프롬프트(docs/prompt-store-taxonomy-scls-2026-09-15.md)의 완료 기준이 요구하는
    '실측 문자열 확정 **또는** 이 표본에 없다' 를 기계가 판정하게 만든 것이다.
    """
    out: dict[str, dict] = {}
    for label, why in UNVERIFIED_SCLS_RULES:
        hits = [(t["scls"], t["n"]) for t in table
                if to_category_group({"indsLclsNm": t["lcls"], "indsMclsNm": t["mcls"],
                                       "indsSclsNm": t["scls"]}) == label and t["scls"]]
        hits.sort(key=lambda kv: -kv[1])
        out[label] = {"why": why, "confirmed": bool(hits),
                      "scls": dict(hits[:10]),
                      "occurrences": sum(n for _, n in hits)}
    return out


def vocab_path(root=None):
    from pathlib import Path

    from data.collectors.common import GOLD
    return (Path(root) if root else GOLD) / VOCAB_NAME


def write_vocab(table: list[dict], meta: dict, root=None):
    """사이드카를 쓴다. 호출자는 `audit()`(Bronze 가 있는 머신)뿐이다."""
    import json

    path = vocab_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"schema": VOCAB_SCHEMA, **meta, "terms": table}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def audit_vocab(root=None) -> dict:
    """**Bronze 없이** 커밋된 어휘 사이드카로 규칙을 감사한다 (2026-09-16 신설).

    `--gold`(중분류만)와 달리 이쪽은 **소분류까지** 본다. 사이드카가 없으면 그 사실을
    그대로 말하고 끝낸다 — 없는 것을 추측으로 메우지 않는다.
    """
    import json

    path = vocab_path(root)
    if not path.exists():
        print(f"[taxonomy:vocab] 사이드카 없음 — {path}")
        print("[taxonomy:vocab] Bronze 가 있는 머신에서 `--audit` 를 한 번 돌리면 "
              "이 파일이 생기고, 그 뒤로는 Bronze 없이 감사된다")
        return {"exists": False, "path": str(path)}
    doc = json.loads(path.read_text(encoding="utf-8"))
    table = doc.get("terms") or []
    store = [t for t in table if t.get("storefront")]

    mapped_terms = drift = 0
    mapped_hits = total_hits = 0
    unmapped_scls: Counter = Counter()
    by_group: Counter = Counter()
    for t in store:
        n = int(t.get("n") or 0)
        total_hits += n
        g = to_category_group({"indsLclsNm": t["lcls"], "indsMclsNm": t["mcls"],
                               "indsSclsNm": t["scls"]}) or ""
        if g != (t.get("group") or ""):
            drift += 1
        if g:
            mapped_terms += 1
            mapped_hits += n
            by_group[g] += n
        else:
            unmapped_scls[t["scls"] or "(공란)"] += n

    verdicts = vocab_verdicts(store)
    out = {
        "exists": True, "path": str(path), "built": doc.get("built"),
        "hubs": doc.get("hubs"), "terms": len(store),
        "occurrences": total_hits,
        "mapped_terms": mapped_terms, "mapped_occurrences": mapped_hits,
        "term_pct": round(mapped_terms / len(store) * 100, 1) if store else None,
        "occurrence_pct": round(mapped_hits / total_hits * 100, 1) if total_hits else None,
        "by_group": dict(by_group.most_common()),
        "unmapped_top_scls": dict(unmapped_scls.most_common(25)),
        "rule_drift_terms": drift,
        "verdicts": verdicts,
    }
    print(f"[taxonomy:vocab] {path.name} · 수집 {doc.get('built')} · 거점 {doc.get('hubs')} · "
          f"가두 분류조합 {len(store):,}종 · 등장 {total_hits:,}회")
    print(f"[taxonomy:vocab] 어휘 기준 사상 {mapped_terms}/{len(store)}종 ({out['term_pct']}%) · "
          f"등장 기준 {mapped_hits:,}/{total_hits:,}회 ({out['occurrence_pct']}%)")
    print(f"[taxonomy:vocab] 그룹별 등장: {out['by_group']}")
    if drift:
        # 규칙을 고친 뒤 사이드카를 안 다시 만든 상태다. 값 자체는 재계산분이 맞다.
        print(f"[taxonomy:vocab] ⚠ 사이드카에 적힌 group 과 현재 규칙이 다른 조합 {drift}종 "
              f"— 규칙이 바뀐 것이다(위 수치는 현재 규칙으로 재계산한 값)")
    print("[taxonomy:vocab] 미검증 3규칙 판정")
    for label, v in verdicts.items():
        if v["confirmed"]:
            print(f"    ✅ {label} ← {', '.join(f'{k}({n:,})' for k, n in v['scls'].items())}")
        else:
            print(f"    ❌ {label} — 이 표본에 없다 ({v['why']})")
    print("[taxonomy:vocab] 미사상 소분류 상위")
    for k, n in unmapped_scls.most_common(25):
        print(f"    {k}: {n:,}")
    return out


def main(argv: list[str]) -> int:
    if "--gold" in argv:
        audit_gold()
        return 0
    if "--vocab" in argv:
        audit_vocab()
        return 0
    if "--audit" not in argv:
        print(__doc__)
        print("사용: python -m data.config.store_taxonomy --audit [거점...]   # Bronze 전수")
        print("      python -m data.config.store_taxonomy --gold             # 커밋된 Gold 중분류")
        print("      python -m data.config.store_taxonomy --vocab            # 커밋된 어휘 "
              "사이드카(소분류까지) — Bronze 불필요")
        return 0
    slugs = [a for a in argv if not a.startswith("-")]
    audit(slugs or None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
