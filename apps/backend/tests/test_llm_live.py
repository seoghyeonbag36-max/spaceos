"""Program LLM 실호출 검증 — 폴백을 끄고 진짜 Claude API 를 친다.

## 왜 별도 파일인가

`test_posting_marketing.py` 는 `_call_llm` / `_call_district_llm` 을 통째로 목킹해서
LLM **응답의 매핑**만 검증한다. 그래서 실호출이 어떤 이유로 깨져도 — 모델 ID 오타,
파라미터 비호환, 구조화 출력 스키마 거부, 키 만료, 크레딧 소진 — 전부 `except` 에
잡혀 폴백으로 흐르고, 요청은 200, 스위트는 초록이었다. **폴백이 있는 코드에서
"테스트 통과"는 실호출이 된다는 증거가 아니다.**

여기서는 그 폴백을 끄고 API 계약 자체를 친다.

## 실행

기본 스위트에서는 건너뛴다(외부 호출 — 네트워크·크레딧을 쓰고 응답이 비결정적).
키를 채운 뒤 opt-in 환경변수를 주면 돈다:

    # PowerShell
    $env:SPACEOS_LIVE_LLM=1; py -3.11 -m pytest tests/test_llm_live.py -v

호출 4건, 건당 수 센트 수준이다.

## 단언의 성격

LLM 응답은 비결정적이라 내용을 고정할 수 없다. 그래서 **계약**만 단언한다 —
스키마가 채워졌는지, 프롬프트가 지시한 형식(건수·한국어·해시태그)을 따르는지,
`source` 가 폴백이 아닌지. 문구 자체는 검증 대상이 아니다.
"""
from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)
V1 = "/api/v1"

# 외부 API 를 치는 테스트라 명시적 opt-in 을 요구한다. 키만 있으면 도는 구조로 두면
# 평소 스위트가 조용히 크레딧을 쓴다.
_LIVE = os.getenv("SPACEOS_LIVE_LLM") == "1"

pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(not _LIVE, reason="실호출 테스트 — SPACEOS_LIVE_LLM=1 로 opt-in"),
    pytest.mark.skipif(not settings.llm_api_key, reason="LLM_API_KEY 미설정"),
]

_HANGUL = re.compile(r"[가-힣]")

_PROFILE = {
    "name": "가로수 로스터리",
    "category": "카페",
    "district_id": "garosugil",
    "address": "서울 강남구 신사동",
    "reviews": [
        "원두를 직접 볶는 곳. 산미 있는 싱글오리진이 좋았다",
        "좌석이 넓고 콘센트가 많아 작업하기 편하다",
        "디저트 중에 바스크 치즈케이크가 인상적",
    ],
}


def _assert_plan(plan, where: str) -> None:
    """채널 플랜 한 건의 계약 — 세 필드가 모두 실제로 채워져야 한다."""
    for field in ("channel", "content", "rationale"):
        value = getattr(plan, field, None) or (plan.get(field) if isinstance(plan, dict) else None)
        assert value and value.strip(), f"{where}: {field} 비어 있음"
        assert _HANGUL.search(value), f"{where}: {field} 가 한국어가 아님 — {value!r}"


def test_call_llm_live():
    """가게 단위 `_call_llm` 실호출 — 폴백 경로가 아예 없는 지점을 직접 친다.

    `generate_store_marketing` 을 거치지 않는 이유: 그 함수의 try/except 가
    어떤 실패든 삼켜 버린다. 여기서 실패하면 그대로 테스트 실패로 드러난다.
    """
    from app.services import marketing as mkt

    tone = mkt._extract_tone_keywords(_PROFILE)
    ctx = mkt._district_context(_PROFILE["district_id"])

    parsed = mkt._call_llm(_PROFILE, tone, ctx)

    # 구조화 출력이 실제로 파싱됐는가 (parsed_output is None 이면 _call_llm 이 raise 한다)
    assert parsed.tone_keywords, "tone_keywords 비어 있음"
    assert parsed.ha_check.strip(), "ha_check 비어 있음 — Humanistic Authority 자체 점검 누락"
    assert _HANGUL.search(parsed.ha_check), f"ha_check 가 한국어가 아님 — {parsed.ha_check!r}"

    # 시스템 프롬프트가 지시한 건수: 온라인 2~3건, 오프라인 2~3건.
    # 모델이 하나 더/덜 낼 수 있어 경계는 느슨하게 두되, 0건과 폭주는 잡는다.
    assert 1 <= len(parsed.online) <= 5, f"online {len(parsed.online)}건"
    assert 1 <= len(parsed.offline) <= 5, f"offline {len(parsed.offline)}건"

    for i, plan in enumerate(parsed.online):
        _assert_plan(plan, f"online[{i}]")
    for i, plan in enumerate(parsed.offline):
        _assert_plan(plan, f"offline[{i}]")


def test_generate_store_marketing_live_no_fallback(capsys):
    """엔드포인트 실호출 — 폴백으로 새면 실패한다.

    `source != "llm"` 이면 LLM 경로가 죽고 규칙 기반 스텁이 응답한 것이다.
    서비스가 실패 사유를 stdout 에 print 하므로 그것을 단언 메시지에 실어
    "왜 폴백됐는지"까지 한 번에 보이게 한다.
    """
    r = client.post(f"{V1}/marketing/generate", json=_PROFILE)
    assert r.status_code == 200
    body = r.json()

    captured = capsys.readouterr().out
    assert body["source"] == "llm", (
        f"LLM 경로가 폴백으로 샜다 (source={body['source']}). 서비스 로그:\n{captured}"
    )

    assert body["store_name"] == _PROFILE["name"]
    # kind 는 서버가 부여한다 — LLM 출력에는 없는 필드라 매핑이 빠지면 여기서 걸린다
    assert all(p["kind"] == "online" for p in body["online"])
    assert all(p["kind"] == "offline" for p in body["offline"])


def test_call_district_llm_live():
    """상권 단위 `_call_district_llm` 실호출 — 실제 Gold 컨텍스트를 입력으로 쓴다."""
    from app.data.seoul_pages import DISTRICTS_BY_ID
    from app.services import marketing as mkt

    ctx = mkt._district_context("garosugil")
    if not ctx:
        pytest.skip("gold/garosugil/program_content_context 미적재 — 컨텍스트 없이는 무의미")

    d = DISTRICTS_BY_ID["garosugil"]
    parsed = mkt._call_district_llm(d["name"], d["sub"], ctx)

    assert parsed.ha_check.strip(), "ha_check 비어 있음"
    assert 1 <= len(parsed.online_contents) <= 6, f"{len(parsed.online_contents)}건"
    for line in parsed.online_contents:
        assert _HANGUL.search(line), f"한국어가 아님 — {line!r}"
        # 프롬프트가 지시한 형식: "{소재 문장} #{해시태그} #{해시태그}"
        assert line.count("#") >= 2, f"해시태그 2개 규칙 위반 — {line!r}"


def test_district_marketing_live_no_fallback(capsys):
    """상권 엔드포인트 실호출 — 시드 폴백으로 새면 실패한다.

    행사(events)는 LLM 이 만들지 않는다. 2026-08-01 부터 서울열린데이터광장 문화행사
    실데이터라 건수는 거점·시점에 따라 변한다 — 개수를 고정하는 대신 **출처**가
    실데이터인지를 단언한다(예전 `== 3` 은 시드 시절의 값이라 실데이터 전환 후 낡았다).
    """
    r = client.get(f"{V1}/marketing/garosugil")
    assert r.status_code == 200
    body = r.json()

    captured = capsys.readouterr().out
    assert body["source"] == "llm", (
        f"상권 콘텐츠가 시드로 샜다 (source={body['source']}). 서비스 로그:\n{captured}"
    )
    assert body["online_contents"], "online_contents 비어 있음"
    assert body.get("events_source") == "seoul-open-data", (
        f"행사가 시드로 샜다 (events_source={body.get('events_source')})"
    )
