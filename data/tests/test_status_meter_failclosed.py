"""진행률 계측기 자체의 fail-open 잠금 — 세는 모집단이 조용히 바뀌지 않게.

`scripts/pppp_status.py` 는 거점 목록(`data.config.page_hubs.ACTIVE_HUBS`)으로
분자·분모를 같은 집합에 맞춘다. 그 로드가 실패하면 `_scored_slugs()` 가 None 으로
물러나고 필터가 통째로 빠진다 — 그러면 서빙 66거점이 아니라 gold 디렉토리 73개
(서빙 66 + 경기 보류 7)를 세게 되는데, **값은 여전히 그럴듯하게 찍힌다.**

같은 계열의 사고가 이미 있었다: 2026-09-01 분모가 54 인 채 분자가 전 거점이라
Page 가 120.4% 로 나왔다. 그때는 100% 를 넘겨서 눈에 띄었지만, 필터가 빠지는
쪽은 100% 안에 머물러 **안 보인다.** 그래서 실패를 기록하고 배너로 띄운다.
"""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _fresh_module():
    sys.modules.pop("pppp_status", None)
    return importlib.import_module("pppp_status")


def test_hub_list_load_failure_is_recorded_not_swallowed(monkeypatch) -> None:
    m = _fresh_module()
    # sys.modules 에 None 을 넣으면 그 이름의 import 가 ImportError 로 떨어진다.
    monkeypatch.setitem(sys.modules, "data.config.page_hubs", None)
    assert m._scored_slugs() is None, "실패 시 None 으로 물러나는 계약은 유지된다"
    assert m._HUB_LOAD_ERROR, "실패가 아무 흔적도 남기지 않았다 — 이것이 fail-open 이다"
    assert "Error" in m._HUB_LOAD_ERROR or ":" in m._HUB_LOAD_ERROR


def test_banner_is_printed_when_the_population_is_unknown(monkeypatch, capsys) -> None:
    """배너는 **숫자보다 먼저** 나와야 한다 — 인용하기 전에 보이는 자리다."""
    m = _fresh_module()
    monkeypatch.setattr(m, "_HUB_LOAD_ERROR", "ImportError: 주입된 실패")
    m.main()
    out = capsys.readouterr().out
    assert "거점 목록" in out and "인용하면 안 된다" in out
    banner = out.index("인용하면 안 된다")
    assert banner < out.index("Page"), "배너가 트랙 수치 뒤에 나오면 못 막는다"


def test_successful_load_prints_no_banner(capsys) -> None:
    """정상 경로에서는 배너가 없어야 한다 (음성 대조)."""
    m = _fresh_module()
    m.main()
    out = capsys.readouterr().out
    assert "인용하면 안 된다" not in out


def test_gold_glob_filters_to_the_scored_population() -> None:
    """분자는 분모와 같은 집합이어야 한다 — 서빙 밖 거점이 섞이면 100% 를 넘는다."""
    m = _fresh_module()
    keep = m._scored_slugs()
    assert keep, "이 테스트는 거점 목록이 읽히는 환경에서만 의미가 있다"
    paths = m._gold_glob("*/coverage.json")
    assert paths, "coverage.json 산출물이 있어야 한다"
    assert all(p.parent.name in keep for p in paths)
    # 저장소에는 서빙 목록 밖 거점의 산출물도 있다 — 필터가 실제로 일하고 있어야 한다.
    everything = sorted((m.GOLD).glob("*/coverage.json"))
    assert len(paths) < len(everything), (
        f"필터가 아무것도 안 걸렀다 — 서빙 {len(paths)} vs 전체 {len(everything)}")
