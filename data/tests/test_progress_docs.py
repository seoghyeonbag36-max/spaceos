"""PPPP 진행 문서가 구현 계약과 함께 움직이는지 검증한다(기준 갱신 2026-09-05)."""

import json
import re
import subprocess
import sys

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_canonical_progress_names_current_state_and_remaining_work() -> None:
    """정본은 완료된 작업을 다시 '다음 작업'으로 만들지 않아야 한다."""
    doc = _read("docs/placeos-vibe-build-sequence.md")

    # 날짜를 박아 두면 갱신할 때마다 이 줄이 먼저 낡는다 — 2026-09-16 에 실제로 그랬다.
    # 고정할 것은 "요약 절이 날짜를 달고 있다" 는 성질이고, 내용의 최신성은 아래
    # 부정 단언들이 지킨다.
    assert re.search(r"## 현재 위치 요약 \(20\d\d-\d\d-\d\d\)", doc), "요약 절에 날짜가 없다"
    # 2026-09-05: `area` 게이트를 관측 전용으로 강등하며 Posting 이 97.6 → 100% 가 됐다.
    # 이 가드가 옛 값을 고정하고 있으면 **가드 자신이 드리프트의 원인**이 된다 —
    # 실제로 그날 아래 세 번째 테스트는 100.0 을 고정하는데 이 줄은 97.6% 를 요구해
    # 두 단언이 서로 모순이었다. 정본에 옛 값이 남지 않았음을 대신 고정한다.
    assert "Posting" in doc
    assert "97.6%" not in doc and "99.7%" not in doc
    assert "Platform" in doc and "관측 전용" in doc
    # 2026-09-16 KPI 재정의로 Platform 은 100% 가 아니다. 정본이 옛 값을 들고 있으면
    # `pppp_status` 출력과 어긋난다 — 이 문서가 막으려는 바로 그 드리프트다.
    assert "네 트랙 전부 100%" not in doc
    assert "Platform 100 ·" not in doc and "· Platform 100" not in doc
    assert "finding-kpi-leak-2026-09-16.md" in doc, (
        "Platform 이 왜 내려갔는지 근거로 갈 수 있어야 한다")
    # 2026-09-17 Program 대상 재정의 — 상용 온보딩은 삭제됐다. 정본이 지금 계약을 말해야 한다.
    assert "검증 브리프" in doc
    assert "B2B 파일럿" in doc
    assert "다음 작업 (2026-08-20 기준)" not in doc


def test_feature_docs_name_source_contracts_targets_and_tests() -> None:
    """Posting·Program 기능 문서는 소스/대상 파일/통과 테스트를 명시해야 한다."""
    posting = _read("docs/feature-posting.md")
    program = _read("docs/feature-program.md")

    assert "finding-posting-unit-area-sources-2026-08-29.md" in posting
    assert "data/validation/posting_unit_area_sources.py" in posting
    assert "test_no_public_source_is_eligible_for_existing_private_units" in posting
    assert "test_partial_public_stock_cannot_promote_the_existing_area_contract" in posting

    # 2026-09-17: 상용 온보딩 계약(ProgramCommercialOnboardingRequest)은 대상 재정의로 삭제됐다.
    # 지금 문서가 이름 대야 하는 것은 검증 브리프 계약과 그것을 고정하는 테스트다.
    assert "ProgramBrief" in program and "ValidationSignal" in program
    assert "apps/backend/app/services/program_brief.py" in program
    assert "test_measuring_revisit_rate_is_not_a_claim" in program
    assert "test_rule_stub_carries_validation_signals" in program
    assert "npm run build" in program


def test_status_and_index_link_to_the_new_evidence() -> None:
    """상태 계산기와 문서 인덱스에서도 신규 근거에 도달할 수 있어야 한다."""
    status = _read("scripts/pppp_status.py")
    index = _read("docs/README.md")

    assert "공식 공개 소스를 다시 탐색했지만 적격 후보는 0건" in status
    assert "검증 브리프·지표 계약" in status
    assert "finding-posting-unit-area-sources-2026-08-29.md" in index
    assert "기술 계약 통과와 KPI②" in index

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/pppp_status.py"), "--json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    scores = {track["name"]: track["pct"] for track in json.loads(result.stdout)["tracks"]}
    # 2026-09-04 Page 99.7 → 100.0. 수집으로 올린 것이 **아니다** — 그날 오전까지
    # 미달이던 doksan 83.5% 의 정체가 결손이 아니라 **분류 오류**였다: 잔여 13동은
    # 층별개요를 이미 받았고 지상 상업층이 0 으로 확정된 건물인데(재호출해도 안 바뀐다)
    # `floor_approx`(= 아직 못 쟀다)와 같은 라벨을 써서 커버리지가 "더 모으면 오른다"고
    # 거짓말하고 있었다. `no_com_floor` 로 갈라 지도·분모에서 빼자 66/66 이 됐다.
    # 게이트가 아니라 대상 정의가 바뀐 것이므로, **대표 공실률은 66거점 전부 불변**이다
    # (그 값은 원래 expos_units·floor_ouln 만 세었다). 근거: docs/feature-page.md §no-com-floor
    #
    # 2026-09-05 Posting 97.6 → 100.0. 이것도 수집으로 올린 것이 **아니다** — `area` 의
    # 0.5 가중을 걷어낸 결과다. 게이트 이름이 "수집 가능한 것"인데 수집 가능한 범위(건물
    # 단위 상업면적)는 66/66 으로 이미 다 얻었고, 남은 0.5 는 자료 부재가 아니라 **입도
    # 상한**이었다(건물 안 유닛 간 균등분할). 그 상한은 층 2회·집합건물·외부 소스 재탐색
    # 으로 세 방향에서 닫혔으므로 수집으로는 안 채워진다 — 계속 세면 "더 모으면 오른다"고
    # 거짓말하는 셈이라 `prem` 을 분모에서 뺀 08-24 결정과 같은 처리를 했다.
    # **값은 사라지지 않았다**: 관측 전용 게이트 "유닛 면적 입도"가 50% 를 계속 찍는다
    # (아래 단언이 그것을 지킨다). 근거: docs/feature-posting.md §0-M·§0-Q·§0-R·§0-S
    #
    # 2026-09-16 Platform 100.0 → 66.7. 이번에는 **내려간** 것이고, 수집이 후퇴해서가
    # 아니라 **세는 자가 틀렸던 것**이다: KPI 게이트가 "정확도 70%+" 라는 임계값이었는데
    # 같은 홀드아웃에서 무정보 규칙이 그 선을 이미 넘고 있었다(공실 예측 방향 '항상 하락'
    # 78.5% vs 모델 70.8% · 업종추천 거점 사전분포 Top-3 89.4% vs 게이트 70%). 임계값을
    # 베이스라인 대비 실력으로 갈아끼우자 방향 축이 실패로 드러났고, 학습 규약 게이트
    # (누수 차단본 재학습)가 하나 더 붙었다. → docs/finding-kpi-leak-2026-09-16.md
    #
    # **그래서 여기에 100.0 을 다시 박지 않는다.** 이 파일이 2026-09-05 에 배운 그대로다 —
    # 가드가 옛 값을 고정하면 가드 자신이 드리프트의 원인이 된다. 고정할 것은 숫자가
    # 아니라 **성질**이다: 세 트랙은 게이트 배선이 끝나 100 이고, Platform 은 실력
    # 게이트가 열려 있는 동안 100 미만이어야 한다(닫히면 자연히 오른다).
    assert scores["Page"] == 100.0
    assert scores["Posting"] == 100.0
    assert scores["Program"] == 100.0
    assert 0.0 < scores["Platform"] < 100.0, (
        "Platform 이 100 이면 실력 게이트가 사라졌거나 베이스라인 대조가 꺼진 것이다")

    # 상한을 평균에서 뺐다면 **관측으로는 반드시 남아야 한다.** 둘 다 빠지면 균등분할이
    # 실측처럼 인용된다 — 이 저장소가 반복해 당한 실패 양식(선언이 낡는 것)의 다른 얼굴이다.
    gates = {g["name"]: g for t in json.loads(result.stdout)["tracks"] for g in t["gates"]}
    ceiling = next(g for n, g in gates.items() if n.startswith("유닛 면적 입도"))
    assert ceiling["observe"] is True
    assert ceiling["value"] == 0.5

    # KPI 게이트는 **베이스라인 대조를 이름에 걸고** 있어야 한다. 이름이 임계값으로
    # 돌아가면(예: "Top-3 ≥70%") 무정보 규칙이 통과하는 자리로 되돌아간 것이다.
    skill = [n for n in gates if "실력" in n]
    assert len(skill) >= 3, f"실력 게이트가 줄었다: {skill}"
    assert not any("≥70%" in n for n in gates), (
        "임계값 게이트가 되돌아왔다 — 베이스라인이 그 선을 이미 넘는다")
    assert any(n.startswith("LSTM 학습 규약") for n in gates), (
        "학습 규약 게이트가 사라졌다 — 누수 차단본 재학습 여부를 못 본다")
