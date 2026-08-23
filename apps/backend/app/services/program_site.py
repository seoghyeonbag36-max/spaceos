"""Program 입력 계약 ①층 — 자리(Site) (2026-08-23).

`docs/feature-program.md` §0-B 가 정의한 3층 입력 중 첫째 층이다.

    ① 자리(Site)      unit_id · lat/lng · area · floor · was(직전 업종) · 건물 공실률
    ② 상권(Market)    services/marketing._district_context — **이미 있다**
    ③ 창업계획(Venture) 기업 입력 — 미구현

## 왜 이 모듈이 필요했나

재료는 2026-08-22 에 54/54 거점(580유닛) 다 채워져 있었다. 그런데 **Program 이 그
파일을 읽지 않아서** 게이트가 33.3% 에 멈춰 있었다 — 수집 과제가 아니라 배선 과제다.
게다가 산출물이 `.gitignore` 로 추적 밖이라 배선해도 배포에서 비었을 것이다
(`calibration.json` 이 40거점에서 조용히 None 이던 것과 똑같은 실패 양식). 08-23 에
추적 예외를 넣고 이 모듈을 붙였다.

## 이 층이 리뷰를 대신한다

대상이 **공실에 창업할 기업**이라 방문자 리뷰가 존재할 수 없다. §0-B 설계원칙 1
("근거는 리뷰가 아니라 수치다")이 말하는 수치의 절반이 여기서 온다 — 면적·층·직전
업종·건물 공실률은 아직 아무도 장사하지 않은 자리에 대해서도 사실이다.

⚠ **이 층만으로는 §0-B 가 지적한 '방문 후기형 포스팅' 문제가 안 풀린다.** 그건 ③층
(창업계획)과 출력 분리까지 가야 닫힌다. 여기서 하는 일은 자리의 사실을 **읽을 수 있게**
만드는 것까지다.

표준 라이브러리만 쓴다 — 배포(Vercel 서버리스) 의존성이 fastapi/pydantic 뿐이다
(services/marketing._load_context_rows 가 파케이로 겪은 사고와 같은 이유).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"

# 슬러그 화이트리스트 — 경로 조작 방어. marketing._SLUG_RE 와 같은 규칙을 쓴다.
_SLUG_RE = re.compile(r"^[a-z0-9-]{1,40}$")

# 거점 id 별칭. marketing._DISTRICT_ALIAS 와 어긋나면 같은 요청이 층마다 다른 거점을
# 가리키므로, 늘릴 때는 양쪽을 같이 고친다.
_DISTRICT_ALIAS: dict[str, str] = {}

_cache: dict[str, dict | None] = {}


def _path(slug: str) -> Path:
    return _GOLD_DIR / slug / "vacant_units.json"


def _slug(district_id: str | None) -> str | None:
    s = _DISTRICT_ALIAS.get(district_id or "", district_id or "")
    return s if _SLUG_RE.match(s) else None


def clear_cache() -> None:
    """테스트·재적재용. 프로세스 전역 캐시를 비운다."""
    _cache.clear()


def _load(district_id: str | None) -> dict | None:
    """`gold/{거점}/vacant_units.json` 통째로. 없거나 깨졌으면 None.

    파일이 없는 것은 **정상 상태**다(거점에 공실이 없거나 아직 안 돌렸거나). 예외를
    올리지 않고 None 을 주어 호출부가 자리층 없이 진행하게 한다 — 다만 그 사실이
    응답에 드러나야 한다(`site_source`).
    """
    slug = _slug(district_id)
    if slug is None:
        return None
    if slug in _cache:
        return _cache[slug]
    path = _path(slug)
    data: dict | None = None
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("units"), list):
                data = loaded
        except (OSError, ValueError):
            data = None
    _cache[slug] = data
    return data


def units(district_id: str | None) -> list[dict]:
    """거점의 공실 유닛 목록. 없으면 빈 리스트."""
    d = _load(district_id)
    return list(d["units"]) if d else []


def unit(district_id: str | None, unit_id: str | None) -> dict | None:
    """유닛 하나. `unit_id` 가 없으면 **대표 유닛**(건물 공실률이 가장 높은 자리).

    대표를 첫 번째가 아니라 공실률 최고로 고르는 이유: 파일 순서는 대장 처리 순서라
    아무 뜻이 없는데, 첫 번째를 대표로 삼으면 그 무의미한 순서가 화면의 기본값이 된다.
    공실률이 높은 자리가 이 제품이 다루려는 자리에 가장 가깝다.
    """
    us = units(district_id)
    if not us:
        return None
    if unit_id:
        return next((u for u in us if u.get("id") == unit_id), None)
    return max(us, key=lambda u: (u.get("vacancy_rate") or 0.0, u.get("area") or 0))


def provenance(district_id: str | None) -> dict:
    """자리층의 출처·한계. 화면과 응답이 '무엇을 근거로 말하는지' 밝히는 자리.

    `note` 를 그대로 실어 보내는 것이 중요하다 — 면적이 호실당 평균이고 층이 1F
    가정이라는 사실이 빠지면, 그 위에 얹힌 투자비·매출이 실측처럼 읽힌다.
    """
    d = _load(district_id)
    if not d:
        return {"site_source": "unavailable", "site_note": None, "site_built_at": None}
    return {
        "site_source": d.get("source") or "gold/vacant_units",
        "site_note": d.get("note"),
        "site_built_at": d.get("built_at"),
    }


def site_context(district_id: str | None, unit_id: str | None = None) -> str | None:
    """LLM 입력용 자리층 텍스트 블록. 유닛을 못 찾으면 None.

    수치를 그대로 적고 해석은 붙이지 않는다 — "목이 좋다" 같은 판단을 여기서 적으면
    그게 생성물의 근거로 재인용되면서 출처 없는 주장이 된다. 판단은 ③층과 상권층의
    수치를 함께 본 뒤 생성 단계에서 나와야 한다.
    """
    u = unit(district_id, unit_id)
    if not u:
        return None
    bits: list[str] = [f"유닛 {u.get('id')}"]
    if u.get("area"):
        bits.append(f"전용면적 약 {u['area']}평(건물 상업면적 ÷ 호실 수)")
    if u.get("floor"):
        bits.append(f"{u['floor']}")
    if (was := (u.get("was") or "").strip()):
        bits.append(f"직전 업종 {was}")
    if u.get("bld_floors"):
        bits.append(f"건물 {u['bld_floors']}층")
    if (vr := u.get("vacancy_rate")) is not None:
        act, cap = u.get("active"), u.get("capacity")
        detail = f"({act}/{cap}호실 영업)" if cap else ""
        bits.append(f"건물 공실률 {vr:.0f}%{detail}")

    lines = ["[자리 — 아직 영업하지 않는 공실이다. 방문 후기·평점은 존재하지 않는다]",
             " · ".join(bits)]
    if u.get("n"):
        lines.append(f"소재: {u['n']}")
    if (note := provenance(district_id).get("site_note")):
        lines.append(f"※ 자리 데이터의 한계: {note}")
    return "\n".join(lines)
