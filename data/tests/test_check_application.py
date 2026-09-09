"""신청서 근거 검사기(`scripts/check_application.py`)가 실제로 위반을 잡는지.

실행: (레포 루트에서) python -m pytest -q data/tests/test_check_application.py

이 테스트가 필요한 이유: 검사기는 **통과 조건** 자체다. `docs/apply/AGENTS.md` 가
"이 명령이 exit 0 이면 머지한다"로 정의해 두었고, `.claude/skills/codex-handoff` 의
4항목 중 3번을 이 명령이 채운다. 그러니 검사기가 조용히 아무것도 안 잡게 되면
**신청서의 모든 가드가 동시에 사라지면서 아무 신호도 나지 않는다** — 통과는 계속
초록이고 위반만 안 잡힌다. 가드레일이 "켜져 있는데 아무것도 막지 않는" 상태이고,
이 저장소가 Program 트렌드 라벨에서 한 번 겪은 실패 양식이다.

`check_doc()` 은 claims 를 인자로 받으므로 실제 `docs/apply/claims.json` 없이 시험할 수
있다. 대장 내용이 바뀌어도 이 테스트는 안 깨진다 — 마지막 두 테스트만 실물을 본다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts import check_application as ca

ROOT = Path(__file__).resolve().parents[2]

# 검사 로직만 보는 최소 대장. 실물과 독립이다.
CLAIMS = {
    "allow": [
        {"id": "HUB", "value": "66거점", "aliases": ["66/66"],
         "condition": "건축물대장", "why": "한정 없이 쓰면 실측 정확도 주장이 된다",
         "source": "테스트"},
        {"id": "ACC", "value": "70.8%", "aliases": [],
         "condition": "", "why": "방향 정확도", "source": "테스트"},
        {"id": "POLY", "value": "52,642", "aliases": [],
         "condition": "동결", "why": "동결 입력 묶음 기준", "source": "테스트"},
    ],
    "forbid": [
        {"id": "F_REAL", "pattern": r"실측\s*공실률",
         "why": "미평가다", "instead": "건축물대장 기반 산출 공실률"},
    ],
    "ignore": [r"20\d\d", r"0\d{1,2}-\d{3,4}-\d{4}", r"\d{1,3}(,\d{3})*만원"],
}


def _doc(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "draft.md"
    p.write_text(text, encoding="utf-8")
    return p


def _kinds(res: dict) -> list[str]:
    return [v["kind"] for v in res["violations"]]


# ── 1. 금지 패턴 ────────────────────────────────────────────────

def test_forbidden_phrase_is_caught(tmp_path):
    res = ca.check_doc(_doc(tmp_path, "## 절\n우리는 실측 공실률을 낸다. 66거점 건축물대장.\n"),
                       CLAIMS, False)
    hits = [v for v in res["violations"] if v["kind"] == "금지"]
    assert len(hits) == 1
    assert hits[0]["id"] == "F_REAL"
    # 대안을 같이 준다 — 무엇이 틀렸는지만 알려주면 다음 사람이 같은 것을 또 쓴다.
    assert hits[0]["instead"]
    assert not res["ok"]


# ── 2. 미등재 수치 ──────────────────────────────────────────────

def test_unregistered_number_is_caught(tmp_path):
    res = ca.check_doc(_doc(tmp_path, "## 절\n정확도는 99.9% 이고 노드는 12,345 개다.\n"),
                       CLAIMS, False)
    found = {v["found"] for v in res["violations"] if v["kind"] == "미등재"}
    assert found == {"99.9%", "12,345"}


def test_registered_number_passes_with_whitespace_and_alias(tmp_path):
    """'70.8 %' 처럼 띄어 써도 등재값으로 본다 — 공백 차이로 오탐이 나면 아무도 안 쓴다."""
    res = ca.check_doc(_doc(tmp_path, "## 절\n방향 정확도 70.8 % · 커버리지 66/66(건축물대장).\n"),
                       CLAIMS, False)
    assert not [v for v in res["violations"] if v["kind"] == "미등재"]


def test_short_numbers_are_not_scanned(tmp_path):
    """배점 20점·절 번호까지 잡으면 오탐이 실제 위반을 덮는다."""
    res = ca.check_doc(_doc(tmp_path, "## 3. 절\n배점 20점, 항목 8개, 팀 5인.\n"), CLAIMS, False)
    assert not [v for v in res["violations"] if v["kind"] == "미등재"]


def test_ignore_patterns_are_not_flagged(tmp_path):
    """연도·전화번호·상금액은 우리 주장이 아니라 대회 사실이다."""
    res = ca.check_doc(
        _doc(tmp_path, "## 절\n2026-09-18 마감 · 문의 031-606-2562 · 상금 1,050만원.\n"),
        CLAIMS, False)
    assert not [v for v in res["violations"] if v["kind"] == "미등재"]


# ── 3. 조건 누락 ────────────────────────────────────────────────

def test_condition_missing_in_same_section_is_caught(tmp_path):
    res = ca.check_doc(_doc(tmp_path, "## 절\n서울 66거점을 서비스한다.\n"), CLAIMS, False)
    hits = [v for v in res["violations"] if v["kind"] == "조건누락"]
    assert len(hits) == 1 and hits[0]["id"] == "HUB"


def test_condition_in_same_section_passes(tmp_path):
    res = ca.check_doc(
        _doc(tmp_path, "## 절\n서울 66거점의 건축물대장 기반 산출값이다.\n"), CLAIMS, False)
    assert not [v for v in res["violations"] if v["kind"] == "조건누락"]


def test_condition_in_a_different_section_does_not_count(tmp_path):
    """다른 절에 한정 문구가 있어도 이 절의 문장은 여전히 한정 없이 읽힌다."""
    text = ("## 1\n건축물대장을 결합해 만들었다는 설명이 여기 있다.\n\n"
            "## 2\n서울 66거점을 서비스한다.\n")
    res = ca.check_doc(_doc(tmp_path, text), CLAIMS, False)
    hits = [v for v in res["violations"] if v["kind"] == "조건누락"]
    assert len(hits) == 1
    assert "## 2" in hits[0]["found"]


# ── 4. 주석·코드펜스 제외 ───────────────────────────────────────

def test_fill_markers_are_excluded_from_every_check(tmp_path):
    """FILL 마커는 지시문이라 금지어와 수치를 그대로 담는다.

    주석까지 세면 지시문이 위반으로 잡히고, 그러면 마커를 못 쓴다 — 마커를 못 쓰면
    판단을 미리 박아 두는 이 구조 전체가 성립하지 않는다.
    """
    text = ("## 절\n"
            "<!-- FILL(claims: HUB)\n"
            "     금지: '실측 공실률' 로 쓰지 않는다. 84.6% 는 옛 값이다. -->\n")
    res = ca.check_doc(_doc(tmp_path, text), CLAIMS, False)
    assert res["ok"], res["violations"]
    assert res["fill_remaining"] == 1


def test_code_fence_is_excluded(tmp_path):
    text = "## 절\n실제 본문은 66거점 건축물대장 기반이다.\n\n```\n실측 공실률 99.9%\n```\n"
    res = ca.check_doc(_doc(tmp_path, text), CLAIMS, False)
    assert res["ok"], res["violations"]


def test_line_numbers_survive_masking(tmp_path):
    """주석을 덮을 때 줄바꿈을 보존하지 않으면 위반 위치가 어긋나 못 찾는다."""
    text = "## 절\n<!-- 주석\n두 줄\n-->\n여기서 실측 공실률.\n"
    res = ca.check_doc(_doc(tmp_path, text), CLAIMS, False)
    hits = [v for v in res["violations"] if v["kind"] == "금지"]
    assert len(hits) == 1 and hits[0]["line"] == 5


# ── 5. 빈 절 · FILL 잔여 ────────────────────────────────────────

def test_empty_section_is_caught(tmp_path):
    """마커만 지우고 내용을 안 채운 자리."""
    text = "## 1\n" + "충분히 긴 본문이 여기 들어 있다. " * 3 + "\n\n## 2\n\n## 3\n끝.\n"
    res = ca.check_doc(_doc(tmp_path, text), CLAIMS, False)
    titles = {v["found"] for v in res["violations"] if v["kind"] == "빈절"}
    assert "## 2" in titles


def test_container_heading_is_not_an_empty_section(tmp_path):
    """하위 절을 담는 제목은 본문이 짧아도 정상이다 (2026-09-09 오탐 회귀 방지)."""
    text = "# 제목\n\n## 1\n" + "충분히 긴 본문이 여기 들어 있다. " * 3 + "\n"
    res = ca.check_doc(_doc(tmp_path, text), CLAIMS, False)
    assert not [v for v in res["violations"] if v["kind"] == "빈절"], res["violations"]


def test_section_still_holding_a_marker_is_not_empty(tmp_path):
    res = ca.check_doc(_doc(tmp_path, "## 1\n<!-- FILL: 아직 안 씀 -->\n"), CLAIMS, False)
    assert not [v for v in res["violations"] if v["kind"] == "빈절"]


def test_require_complete_flags_remaining_markers(tmp_path):
    doc = _doc(tmp_path, "## 1\n<!-- FILL: 아직 안 씀 -->\n")
    assert ca.check_doc(doc, CLAIMS, False)["ok"]
    strict = ca.check_doc(doc, CLAIMS, True)
    assert not strict["ok"]
    assert "미완" in _kinds(strict)


# ── 실물 ────────────────────────────────────────────────────────

def test_real_claims_file_is_usable():
    """대장의 정규식이 깨지면 검사기가 통째로 죽는다 — 원고보다 먼저 여기서 잡는다."""
    claims = json.loads(ca.CLAIMS.read_text(encoding="utf-8"))
    assert claims["allow"] and claims["forbid"]
    for a in claims["allow"]:
        assert a["value"] and a["why"] and a["source"], a
    for f in claims["forbid"]:
        re.compile(f["pattern"])          # 컴파일 실패 = 테스트 실패
        assert f["why"] and f["instead"], f
    for pat in claims.get("ignore", []):
        re.compile(pat)


def test_shipped_drafts_pass():
    """저장소에 실린 원고는 언제나 통과 상태여야 한다.

    `docs/apply/AGENTS.md` 가 '절 하나 = 커밋 하나' 로 단위를 정해 두었으므로,
    중간 상태로 커밋하더라도 그 커밋은 통과해야 한다. FILL 잔여는 여기서 안 본다 —
    미완은 위반이 아니고, 제출 직전에만 `--require-complete` 로 본다.
    """
    claims = json.loads(ca.CLAIMS.read_text(encoding="utf-8"))
    docs = sorted(p for p in ca.APPLY_DIR.rglob("*.md") if p.name not in ca.SKIP_NAMES)
    assert docs, "docs/apply/ 에 원고가 없다 — 검사 대상이 사라졌는지 확인할 것"
    bad = {}
    for d in docs:
        res = ca.check_doc(d, claims, False)
        if not res["ok"]:
            bad[res["doc"]] = res["violations"]
    assert not bad, json.dumps(bad, ensure_ascii=False, indent=2)


@pytest.mark.parametrize("name", ["AGENTS.md", "README.md", "claims.json"])
def test_rules_and_index_are_not_scanned_as_drafts(name):
    """규칙 문서는 금지어를 예시로 담는다 — 원고로 세면 규칙이 스스로를 위반한다."""
    assert name in ca.SKIP_NAMES
