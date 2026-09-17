# -*- coding: utf-8 -*-
"""기술지주회사·산학협력단·창업지원단 지원용 서류 3종 .docx 생성기.

만드는 것
  1) 이력서          — 1~2쪽. 신상·학력·경력은 **빈칸 템플릿**(지어내지 않는다)
  2) 경력기술서      — 역할 / 기간 / 사용 기술 / 정량 성과 4항목 고정
  3) 포트폴리오      — PlaceOS 실측 산출물 + 검증 방법론

규칙
- 수치는 `python scripts/pppp_status.py` · `scripts/kpi_baseline.py` 산출물에서만 인용한다.
  본인 신상(성명·학력·경력·자격)은 저장소에 없으므로 **[ ] 로 남긴다**. 추정해 채우지 않는다.
- 한글 폰트는 임베딩한다(폰트명만 지정하면 뷰어에서 □ 로 깨진다).
  → build_business_plan_docx 의 subset → ECMA-376 §17.8.1 난독화 → fontTable 배선을 그대로 쓴다.
- 이모지·기호는 쓰지 않는다. subset 대상에 없으면 빈칸으로 렌더된다.

실행:
    python scripts/build_job_application_docx.py [-d 출력디렉터리] [--fonts 폰트캐시]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_business_plan_docx as bp  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

J = WD_ALIGN_PARAGRAPH.JUSTIFY
C = WD_ALIGN_PARAGRAPH.CENTER
L = WD_ALIGN_PARAGRAPH.LEFT
R = WD_ALIGN_PARAGRAPH.RIGHT

BLANK = "[                              ]"
FILL = "[ 채울 것 ]"

# 저장소 실측값 (2026-09-16 기준 · pppp_status.py / kpi_baseline.py)
M = {
    "hubs": "66",
    "page": "100.0",
    "platform": "66.7",
    "posting": "100.0",
    "program": "100.0",
    "units": "664",
    "floor_units": "12,497",
    "floor_conf": "9,437",
    "floor_prob": "3,060",
    "loc": "58,921",
    "lstm_mae": "1.061",
    "lstm_base": "1.333",
    "lstm_skill": "+20.5",
    "lstm_dir": "70.8",
    "lstm_dir_base": "78.5",
    "lstm_dir_skill": "-7.7",
    "gnn_top3": "91.7",
    "gnn_prior": "89.3",
    "gnn_skill": "+2.32",
    "gnn_nodes": "47,442",
    "gnn_feat": "117",
    "roi_units": "528",
    "roi_fail": "0.8",
    "roi_win": "432",
    "bundle_before": "832",
    "bundle_after": "4",
}


# ══════════════════════════════════════════════════════════════════════════
#  공통 조각
# ══════════════════════════════════════════════════════════════════════════
def doc_title(doc, title, sub):
    p = bp.para(doc, before=0, after=1, line=1.1)
    bp.run(p, title, size=26, bold=True, color=bp.NAVY, spacing=-14)
    p = bp.para(doc, before=0, after=4, line=1.3)
    bp.run(p, sub, size=10, color=bp.MUTED)
    bp.para_border(p, ("bottom",), color=bp.NAVY, sz=12, space=9)


def label_row(doc, pairs):
    """이름: 값 형태의 얇은 2열 표."""
    bp.make_table(doc, pairs, [3.6, 12.2], head=False, sizes=[9.0, 9.0],
                  aligns=[L, L], zebra=False, bold_first_col=True)


def guide(doc, lines):
    bp.note_box(doc, [(t, b) for t, b in lines])


# ══════════════════════════════════════════════════════════════════════════
#  1) 이력서
# ══════════════════════════════════════════════════════════════════════════
def build_resume(out: Path) -> Path:
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, "이력서")

    doc_title(doc, "이 력 서", "Resume · 지원 분야: 기술사업화 / 창업지원 / 데이터 엔지니어링")

    bp.h2(doc, "01", "인적사항")
    label_row(doc, [
        ["성명 (한글 / 한자)", BLANK],
        ["생년월일", BLANK],
        ["주소", "[ 시 / 구 까지만 기재 — 상세주소는 최종합격 후 ]"],
        ["휴대전화", BLANK],
        ["이메일", "seoghyeonbag36@gmail.com"],
        ["포트폴리오", "https://placeos.web.app"],
        ["병역 / 보훈 / 장애", "[ 해당 시에만 기재 ]"],
    ])
    bp.caption(doc, "주민등록번호는 기재하지 않는다. 기관 채용은 최종합격 후 별도 서식으로 수집한다.")

    bp.h2(doc, "02", "지원 포지션 및 한 줄 요약")
    label_row(doc, [
        ["지원 기관", FILL],
        ["지원 부문", "[ 공고에 적힌 부문명을 그대로 옮길 것 ]"],
        ["공고번호", FILL],
    ])
    bp.body(doc,
            "오프라인 상권을 데이터로 재구성하는 SaaS 두 종(PlaceOS · Co.I)을 기획부터 배포까지 "
            "단독으로 수행했습니다. 데이터 수집 파이프라인, 예측 모델, API, 프론트엔드, 클라우드 배포까지 "
            "한 사람이 전 구간을 담당했고, 두 서비스 모두 데모가 아니라 운영 중입니다.",
            before=6)

    bp.h2(doc, "03", "핵심 역량")
    bp.bullets(doc, [
        ("데이터 파이프라인 설계 · ",
         "공공 API(건축물대장 · 상권분석 · R-ONE · KOSIS)를 Bronze/Silver/Gold 3계층으로 "
         f"정규화해 서울 {M['hubs']}개 거점의 건물 단위 공실 인벤토리를 구축했습니다."),
        ("예측 모델 개발 · ",
         "시계열 공실 예측(LSTM)과 업종 추천(GNN)을 학습·서빙까지 연결했습니다. "
         "성능은 임계값이 아니라 무정보 베이스라인 대비 개선폭으로 관리합니다."),
        ("제품화 · ",
         "FastAPI + React + PostGIS 스택을 GitHub Actions - Cloud Run 파이프라인에 올려 "
         "테스트 통과 시에만 배포되도록 구성했습니다."),
        ("검증 설계 · ",
         "자기 지표의 결함을 스스로 찾아내 지표 체계 전체를 재정의한 경험이 있습니다. "
         "상세는 경력기술서 4장."),
    ])

    bp.h2(doc, "04", "주요 프로젝트")
    bp.make_table(doc, [
        ["프로젝트", "기간", "역할", "내용"],
        ["PlaceOS",
         "2026.05 ~\n현재",
         "기획 · 개발\n(단독)",
         "오프라인 상권 디지털 트윈 플랫폼.\n건물 단위 공실 인벤토리 + 공실 예측 + 업종 추천"],
        ["Co.I",
         FILL,
         "기획 · 개발\n(단독)",
         "창업 코파일럿 AI.\n" + FILL],
    ], [3.0, 2.2, 2.4, 8.2], sizes=[9.0, 8.5, 8.5, 9.0],
        aligns=[L, C, C, L], bold_first_col=True)
    bp.caption(doc, "상세 내역은 별첨 경력기술서 · 포트폴리오 참조.")

    bp.h2(doc, "05", "보유 기술")
    bp.make_table(doc, [
        ["구분", "내용"],
        ["Backend", "Python 3.11, FastAPI, PostgreSQL / PostGIS, Redis, Celery, Alembic"],
        ["ML", "PyTorch, PyTorch Geometric (GNN), LSTM, MLflow, LangChain"],
        ["Frontend", "React, TypeScript, Vite, 네이버 지도 API (지도 · 거리뷰)"],
        ["Data", "Airflow, Selenium / Playwright, Bronze / Silver / Gold 3계층 설계"],
        ["Infra", "Docker, GitHub Actions, Google Cloud Run, Firebase Hosting"],
        ["공공데이터", "건축HUB 건축물대장, 서울시 상권분석, R-ONE 부동산통계, KOSIS, 공정위 정보공개서"],
    ], [3.0, 12.8], sizes=[9.0, 9.0], aligns=[L, L], bold_first_col=True)

    bp.h2(doc, "06", "학력")
    bp.make_table(doc, [
        ["기간", "학교 / 전공", "학위", "비고"],
        [BLANK, BLANK, FILL, FILL],
        [BLANK, BLANK, FILL, FILL],
    ], [3.6, 6.4, 2.6, 3.2], sizes=[8.5, 9.0, 8.5, 8.5], aligns=[C, L, C, L])
    bp.caption(doc, "최종 학력부터 역순으로 기재한다.")

    bp.h2(doc, "07", "경력")
    bp.make_table(doc, [
        ["기간", "기관 / 부서", "직위", "담당 업무"],
        [BLANK, BLANK, FILL, FILL],
        [BLANK, BLANK, FILL, FILL],
    ], [3.6, 5.0, 2.2, 5.0], sizes=[8.5, 9.0, 8.5, 8.5], aligns=[C, L, C, L])
    bp.caption(doc, "경력이 없으면 행을 지우고 '해당 없음'으로 적는다. 빈 표를 남기지 않는다.")

    bp.h2(doc, "08", "자격 · 교육 · 수상")
    bp.make_table(doc, [
        ["취득일", "명칭", "발급 기관"],
        [BLANK, BLANK, BLANK],
        [BLANK, BLANK, BLANK],
    ], [3.2, 7.4, 5.2], sizes=[8.5, 9.0, 9.0], aligns=[C, L, L])
    bp.caption(doc, "기술사업화 직무는 특허 출원 · 등록 실적을 이 표 최상단에 둔다.")

    guide(doc, [
        ("작성 안내", True),
        ("1. 공고에 지정 양식(hwp / xlsx)이 있으면 이 문서를 쓰지 말고 그 양식에 옮겨 적는다. "
         "기관 채용은 자유 양식을 반려한다.", False),
        ("2. [ ] 로 남긴 칸은 저장소 자료로 확인할 수 없어 비워 둔 곳이다. 직접 채운다.", False),
        ("3. 첫 메일에는 주민등록번호 · 상세주소 · 졸업증명서 · 희망연봉 · 대학원 진학 계획을 넣지 않는다.", False),
        ("4. 파일명은 공고가 지정한 규칙을 그대로 따른다. 지정이 없으면 "
         "'[부문]성명_이력서.pdf' 로 변환해 제출한다.", False),
    ])

    doc.save(out)
    return out


# ══════════════════════════════════════════════════════════════════════════
#  2) 경력기술서
# ══════════════════════════════════════════════════════════════════════════
def proj_head(doc, num, title, rows):
    bp.h2(doc, num, title)
    bp.make_table(doc, rows, [3.0, 12.8], head=False, sizes=[9.0, 9.0],
                  aligns=[L, L], zebra=False, bold_first_col=True)


def build_experience(out: Path) -> Path:
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, "경력기술서")

    doc_title(doc, "경 력 기 술 서",
              "Statement of Experience · 성명: " + BLANK)

    bp.h1(doc, "1", "요약")
    bp.body(doc,
            "오프라인 상권을 데이터로 재구성하는 SaaS 두 종을 기획부터 배포까지 단독으로 수행했습니다. "
            "수집 파이프라인, 예측 모델, API, 화면, 배포까지 전 구간을 담당했으며, 두 서비스 모두 "
            "운영 중입니다. 아래 정량 성과는 모두 저장소의 산출물 계측 스크립트에서 산출한 값이며, "
            "미달 항목도 그대로 기재했습니다.")
    bp.make_table(doc, [
        ["항목", "값", "산출 근거"],
        ["대상 상권", f"서울 {M['hubs']}개 거점", "건축물대장 실측 (Tier1)"],
        ["공실 인벤토리", f"{M['units']}유닛 (층 단위 {M['floor_units']}개)",
         f"확정 {M['floor_conf']} / 추정 {M['floor_prob']}"],
        ["코드 규모", f"{M['loc']} 라인 (Python · TypeScript)", "git ls-files 기준"],
        ["트랙 진행률",
         f"Page {M['page']}% · Posting {M['posting']}% ·\nProgram {M['program']}% · Platform {M['platform']}%",
         "scripts/pppp_status.py"],
    ], [3.4, 6.2, 6.2], sizes=[9.0, 9.0, 8.5], aligns=[L, L, L], bold_first_col=True)

    # ── PlaceOS ─────────────────────────────────────────────────────────
    bp.h1(doc, "2", "PlaceOS — 오프라인 상권 디지털 트윈 플랫폼")
    proj_head(doc, "2.1", "프로젝트 개요", [
        ["기간", "2026.05 ~ 현재 (진행 중)"],
        ["역할", "기획 · 아키텍처 설계 · 전 구간 개발 · 배포 (단독)"],
        ["사용 기술",
         "Python 3.11, FastAPI, PostgreSQL / PostGIS, Redis, Celery / "
         "PyTorch, PyTorch Geometric, MLflow / React, TypeScript, Vite, 네이버 지도 API / "
         "Docker, GitHub Actions, Google Cloud Run, Firebase Hosting"],
        ["운영 주소", "https://placeos.web.app"],
        ["문제 정의",
         "상권 정보가 '어느 동네가 뜨는가' 수준의 행정동 통계에 머물러, "
         "'어느 건물 몇 층이 비었고 거기에 무엇이 들어가야 하는가'를 답하지 못한다."],
        ["해결 접근",
         "건축물대장을 실측 원천으로 삼아 건물 - 층 - 유닛 단위 공실 인벤토리를 세우고, "
         "그 위에 공실 예측 · 업종 추천 · 입점 ROI · 마케팅 생성 네 트랙을 얹었다."],
    ])

    bp.h2(doc, "2.2", "Platform — 상권 AI 추천 엔진")
    bp.bullets(doc, [
        ("담당 · ", "LSTM 공실 예측 모델과 GNN 업종 추천 모델의 데이터셋 구성, 학습, 서빙 연동."),
        ("규모 · ", f"GNN 그래프 노드 {M['gnn_nodes']}개 · 피처 {M['gnn_feat']}열."),
        ("성과 (공실 예측) · ",
         f"MAE {M['lstm_mae']} — 직전 분기값을 그대로 내미는 지속성 베이스라인 "
         f"{M['lstm_base']} 대비 {M['lstm_skill']}% 개선."),
        ("성과 (업종 추천) · ",
         f"Top-3 정확도 {M['gnn_top3']}% — 거점 사전분포 베이스라인 {M['gnn_prior']}% 대비 "
         f"{M['gnn_skill']}%p 개선."),
        ("미달 항목 (그대로 기재) · ",
         f"공실 예측의 방향 정확도는 {M['lstm_dir']}% 로, 무정보 상수 베이스라인 "
         f"{M['lstm_dir_base']}% 에 {M['lstm_dir_skill']}%p 미달합니다. n=65 의 신뢰구간이 "
         "넓어 우열을 가를 수 없는 표본이며, 제품이 파는 값은 방향 이분법이 아니라 "
         "공실 압력의 크기이므로 오차 축을 주 지표로 둡니다."),
    ])

    bp.h2(doc, "2.3", "Page — 공실 히트맵 · 층별 매물 · 거리뷰")
    bp.bullets(doc, [
        ("담당 · ", "건축HUB 건축물대장 수집기, 주소 정규화, 층별 공실 판정 파이프라인, 지도 화면."),
        ("성과 · ",
         f"{M['hubs']}개 거점 전부를 건축물대장 실측(Tier1)으로 올렸고, 대표 집계 커버리지 100%, "
         "R-ONE 앵커 대조 체계를 갖췄습니다."),
        ("최적화 · ",
         f"3D 렌더링이 실측 형상이 아니라 층 상태를 색으로 표현할 뿐임을 확인하고 2D 층 스택 + "
         f"거리뷰로 대체해 번들을 {M['bundle_before']}KB에서 {M['bundle_after']}KB로 줄였습니다."),
    ])

    bp.h2(doc, "2.4", "Posting — 입점 의사결정 · ROI 시뮬레이션")
    bp.bullets(doc, [
        ("담당 · ", "3-Tier 비용-효용 모델, 매출 추정 앵커링, 외부 코파일럿 연동 어댑터 설계."),
        ("성과 · ",
         f"실 인벤토리 {M['roi_units']}유닛 기준 회수불가 {M['roi_fail']}%, "
         f"기능중심 티어 {M['roi_win']}승. 공정위 가맹사업 정보공개서와 KOSIS를 교차 검증해 "
         "평당매출을 업계 통상 대역 안으로 맞췄습니다."),
        ("발견한 결함 · ",
         "임대료를 1층 기준으로 계산하던 초기 모델이 실제 상업층 분포와 맞지 않아 "
         "임대료를 중앙값 기준 45% 과대계상하고 있었습니다. 층별 면적 비중으로 가중 평균해 "
         "바로잡았고, 두 모델이 참값을 사이에 두는 상한 - 하한 관계임을 테스트로 고정했습니다."),
    ])

    bp.h2(doc, "2.5", "Program — 마케팅 자동화")
    bp.bullets(doc, [
        ("담당 · ", "LLM 생성 엔진, 생성물 사실성 검증 가드(ha_guard), 상용 입력 온보딩 계약."),
        ("성과 · ",
         "아직 개업하지 않은 가게에 '방문 후기형 포스팅'을 제안하는 등의 사실 오류를 "
         "타입과 서버 검증으로 차단했습니다. 예산 항목을 정수 퍼센트 타입으로 강제해 "
         "허구의 절대 금액이 구조적으로 들어갈 수 없게 했습니다."),
        ("개인정보 처리 · ",
         "조직 인증, 처리 · 권리 · 외부 모델 처리 동의를 요청 스키마가 강제하며, "
         "원문은 저장하지 않고 감사 메타데이터만 남깁니다."),
    ])

    # ── Co.I ────────────────────────────────────────────────────────────
    bp.h1(doc, "3", "Co.I — 창업 코파일럿 AI")
    proj_head(doc, "3.1", "프로젝트 개요", [
        ["기간", BLANK],
        ["역할", "기획 · 개발 (단독)"],
        ["사용 기술", FILL],
        ["운영 주소 / 저장소", FILL],
        ["문제 정의", FILL],
        ["해결 접근", FILL],
    ])
    guide(doc, [
        ("Co.I 장 작성 안내", True),
        ("이 장은 저장소에 자료가 없어 비워 두었습니다. 아래 네 항목을 채우면 2장과 같은 밀도가 됩니다.", False),
        ("1. 무엇을 자동화했는가 — 창업자가 원래 며칠 걸리던 어떤 판단을 몇 분으로 줄였는가.", False),
        ("2. 무엇을 근거로 답하는가 — 검색인가, 내부 데이터인가, 생성인가. 환각을 무엇으로 막는가.", False),
        ("3. 정량 지표 — 응답 시간, 처리한 질의 수, 정답률 또는 사용자 평가. 없으면 지금 재 둔다.", False),
        ("4. PlaceOS 와의 관계 — PlaceOS 는 Posting 트랙에서 외부 코파일럿 어댑터 계약을 "
         "이미 발행해 두었으므로, Co.I 를 그 자리에 붙이는 구조로 설명하면 두 프로젝트가 "
         "하나의 이야기가 됩니다.", False),
    ])

    # ── 문제해결 사례 ────────────────────────────────────────────────────
    bp.h1(doc, "4", "문제 해결 사례")
    bp.h2(doc, "4.1", "자사 지표의 결함을 스스로 찾아 지표 체계를 재정의")
    bp.make_table(doc, [
        ["구분", "내용"],
        ["상황", "AI 정확도 70% 이상을 목표로 두고, 두 모델 모두 그 선을 넘겼다고 보고하고 있었다."],
        ["과제",
         "같은 홀드아웃에서 입력을 전혀 보지 않는 규칙이 이미 그 선을 넘는지 확인했다."],
        ["행동",
         f"무정보 베이스라인을 계산했다. 공실 예측 방향은 '항상 하락' 상수가 {M['lstm_dir_base']}% "
         f"(모델 {M['lstm_dir']}%), 업종 추천 Top-3 은 거점 사전분포가 {M['gnn_prior']}% 였다. "
         "즉 임계값을 넘겼다는 사실에 정보가 없었고, 그 달성 표기가 진행률 문서와 외부 원고까지 "
         "퍼져 있었다."],
        ["결과",
         "!임계값 단독 판정을 폐기하고 베이스라인 대비 실력으로 전 지표를 재정의했다. "
         "네 규칙(임계값 단독 금지 / 불확실성 동반 / 선택과 보고 분리 / 계측기 없는 목표는 "
         "지표가 아님)을 세우고, 미달이면 종료코드 1을 내는 검사 스크립트로 못박았다."],
    ], [2.4, 13.4], sizes=[9.0, 9.0], aligns=[C, L], bold_first_col=True)

    bp.h2(doc, "4.2", "계측기 없는 목표를 먼저 계측 가능하게 만들기")
    bp.make_table(doc, [
        ["구분", "내용"],
        ["상황", "API 응답 p95 200ms 미만, 지도 로딩 3초 미만을 성능 목표로 걸어 두고 있었다."],
        ["과제", "그 목표를 재는 코드가 저장소에 한 줄도 없다는 것을 확인했다."],
        ["행동",
         "지연 계측 미들웨어와 클라이언트 타이밍 수집 경로를 만들고 관리자 조회 창구를 냈다. "
         "표본이 기준 미만이면 계측기가 스스로 판정을 보류하도록 했고, 클라이언트 자가보고 값은 "
         "저장 키 접두사로 서버 실측과 구분했다."],
        ["결과",
         "!배선 완료와 목표 달성을 문서에서 분리했다. 재지 않은 것을 달성으로 적지 않는 것이 "
         "이 프로젝트의 기본 규칙이 되었다."],
    ], [2.4, 13.4], sizes=[9.0, 9.0], aligns=[C, L], bold_first_col=True)

    bp.h2(doc, "4.3", "수집이 아니라 배선이 병목임을 반복 확인")
    bp.body(doc,
            "'데이터가 없어서 못 한다'고 문서에 적혀 있던 항목 다섯 건을 실제로 확인한 결과, "
            "네 건이 이미 저장소 안에 재료가 있는데 서빙 코드가 읽지 않고 있던 경우였습니다. "
            "유동인구 좌표, 공실 유닛 인벤토리, 층별 점유 정보, 임대료 기준선이 모두 그랬습니다. "
            "이후로는 문서의 서술을 믿지 않고 1회 실측으로 확인한 뒤 그 결과를 별도 문서로 "
            "남기는 절차를 두었습니다.", before=4)

    bp.h1(doc, "5", "일하는 방식")
    bp.bullets(doc, [
        ("측정 우선 · ", "재지 않은 값은 달성으로 적지 않습니다. 미달 항목은 미달로 남깁니다."),
        ("낡은 서술 추적 · ",
         "같은 산출물 안에서 두 곳이 다른 말을 하는 것을 주된 실패 양식으로 보고, "
         "폐기한 결정도 지우지 않고 경위를 남깁니다."),
        ("테스트로 고정 · ",
         "합의한 전제는 문장이 아니라 테스트와 타입으로 고정합니다. "
         "예: 예산 항목을 정수 퍼센트 타입으로 두어 절대 금액이 들어갈 수 없게 했습니다."),
        ("도구 · ", "Cursor · Claude Code 를 활용한 AI 보조 개발. 생성된 코드는 머지 전 실행 검증."),
    ])

    doc.save(out)
    return out


# ══════════════════════════════════════════════════════════════════════════
#  3) 포트폴리오
# ══════════════════════════════════════════════════════════════════════════
def build_portfolio(out: Path) -> Path:
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, "포트폴리오")

    # 표지
    p = bp.para(doc, before=110, after=0, line=1.1)
    bp.run(p, "PlaceOS", size=44, bold=True, color=bp.NAVY, spacing=-22)
    p = bp.para(doc, before=2, after=0, line=1.3)
    bp.run(p, "오프라인 상권의 디지털 트윈 플랫폼", size=13, color=bp.INK)
    p = bp.para(doc, before=1, after=0, line=1.3)
    bp.run(p, "Co.I  —  창업 코파일럿 AI", size=13, color=bp.INK)
    p = bp.para(doc, before=14, after=0, line=1.3)
    bp.para_border(p, ("top",), color=bp.NAVY, sz=10, space=10)
    bp.run(p, "포트폴리오", size=10.5, bold=True, color=bp.ACCENT)
    p = bp.para(doc, before=1, after=0, line=1.45)
    bp.run(p, "성명 " + BLANK, size=9.5, color=bp.MUTED)
    p = bp.para(doc, before=0, after=0, line=1.45)
    bp.run(p, "seoghyeonbag36@gmail.com  ·  https://placeos.web.app", size=9.5, color=bp.MUTED)
    p = bp.para(doc, before=0, after=0, line=1.45)
    bp.run(p, "2026. 09.", size=9.5, color=bp.MUTED)

    p = bp.para(doc, before=0, after=0)
    from docx.enum.text import WD_BREAK
    bp.run(p, "").add_break(WD_BREAK.PAGE)

    # 01
    bp.h1(doc, "01", "한 장 요약")
    bp.body(doc,
            "물리적 상권을 SNS · 디지털 관점의 플랫폼으로 읽는 가설에서 출발했습니다. "
            "기존 상권 정보가 행정동 단위 통계에 머물러 '어느 건물 몇 층이 비었는가'를 답하지 "
            "못한다는 점이 문제였습니다. PlaceOS 는 건축물대장을 실측 원천으로 삼아 건물 - 층 - 유닛 "
            "단위 공실 인벤토리를 세우고, 그 위에 네 가지 질문을 차례로 답하는 구조입니다.")
    bp.make_table(doc, [
        ["트랙", "답하는 질문", "구현", "진행률"],
        ["Platform", "이 입지는 어떤 플랫폼인가",
         "공실 예측(LSTM) · 업종 추천(GNN)", f"{M['platform']}%"],
        ["Page", "어디에 자리가 비어 있는가",
         "공실 히트맵 · 층별 매물 · 거리뷰", f"{M['page']}%"],
        ["Posting", "어느 가격대로 들어가야 하는가",
         "3-Tier 비용-효용 · ROI 시뮬레이션", f"{M['posting']}%"],
        ["Program", "어떻게 알릴 것인가",
         "마케팅 생성 · 사실성 검증 가드", f"{M['program']}%"],
    ], [2.6, 5.0, 5.8, 2.4], sizes=[9.0, 9.0, 9.0, 9.0],
        aligns=[L, L, L, C], bold_first_col=True)
    bp.caption(doc, "진행률은 문서가 아니라 산출물을 세어 계산한다 (scripts/pppp_status.py).")

    # 02
    bp.h1(doc, "02", "실측 산출물")
    bp.body(doc,
            "아래 수치는 모두 저장소의 계측 스크립트가 산출물을 직접 세어 낸 값입니다. "
            "선언이나 문서 서술이 아닙니다.")
    bp.make_table(doc, [
        ["항목", "값", "비고"],
        ["대상 거점", f"서울 {M['hubs']}개 상권", "전부 건축물대장 실측 (Tier1)"],
        ["공실 유닛", f"{M['units']}유닛", "건물 단위 인벤토리"],
        ["층 단위 공실", f"{M['floor_units']}개",
         f"확정 {M['floor_conf']} / 추정 {M['floor_prob']}"],
        ["히트맵 레이어", "4종", "공실 · 임대료 · 유동 · 밀도 (동일 100m 격자)"],
        ["시간 축", "24시간", "생활인구 행정동 · 평일 20일 / 주말 8일 표본"],
        ["GNN 그래프", f"노드 {M['gnn_nodes']} · 피처 {M['gnn_feat']}", "업종 간 시너지 · 잠식"],
        ["ROI 표본", f"{M['roi_units']}유닛", f"회수불가 {M['roi_fail']}%"],
        ["코드 규모", f"{M['loc']} 라인", "Python · TypeScript"],
    ], [3.2, 4.4, 8.2], sizes=[9.0, 9.0, 8.5], aligns=[L, L, L], bold_first_col=True)

    # 03
    bp.h1(doc, "03", "기술 아키텍처")
    bp.make_table(doc, [
        ["계층", "구성"],
        ["수집", "건축HUB 건축물대장 · 서울시 상권분석 · R-ONE 부동산통계 · KOSIS · 공정위 정보공개서\n"
                 "Airflow DAG + Selenium / Playwright 크롤러, 일일 쿼터 관리 런북"],
        ["저장", "Bronze (원본) → Silver (정제 · 주소 정규화) → Gold (분석용 집계)\n"
                 "PostgreSQL / PostGIS + Redis"],
        ["모델", "LSTM 공실 예측 · GNN(PyTorch Geometric) 업종 추천 · MLflow 실험 추적"],
        ["서빙", "FastAPI (/api/v1/ 규약) · Celery 비동기 · 지연 계측 미들웨어"],
        ["화면", "React + TypeScript + Vite · 네이버 지도(지도 · 거리뷰) · CSS 변수 토큰 단일 체계"],
        ["배포", "GitHub Actions (테스트 → 빌드 → 배포 → 검증) → Cloud Run + Firebase Hosting"],
    ], [2.4, 13.4], sizes=[9.0, 8.5], aligns=[L, L], bold_first_col=True)

    # 04
    bp.h1(doc, "04", "검증 방법론")
    bp.body(doc,
            "이 프로젝트에서 가장 설명하고 싶은 부분입니다. 2026년 9월, 자사 지표가 "
            "모델 성능을 전혀 보증하지 못한다는 사실을 스스로 확인하고 지표 체계를 전면 "
            "재정의했습니다. 그 전까지의 기준은 'AI 정확도 70% 이상' 한 줄이었습니다.")
    bp.make_table(doc, [
        ["축", "무정보 베이스라인", "모델", "실력"],
        ["공실 예측 · 오차 (MAE)", f"지속성 {M['lstm_base']}", M['lstm_mae'], f"{M['lstm_skill']}%"],
        ["공실 예측 · 방향", f"'항상 하락' {M['lstm_dir_base']}%", f"{M['lstm_dir']}%",
         f"!{M['lstm_dir_skill']}%p"],
        ["업종 추천 · Top-3", f"거점 사전분포 {M['gnn_prior']}%", f"{M['gnn_top3']}%",
         f"{M['gnn_skill']}%p"],
    ], [4.6, 4.6, 3.2, 3.4], sizes=[9.0, 9.0, 9.0, 9.0], aligns=[L, L, C, C],
        bold_first_col=True)
    bp.caption(doc,
               "방향 축은 미달입니다. 감추지 않고 그대로 싣습니다. "
               "제품이 파는 값은 방향 이분법이 아니라 공실 압력의 크기이므로 오차 축을 주 지표로 둡니다.")

    bp.h2(doc, "4.1", "적용한 네 규칙")
    bp.bullets(doc, [
        ("임계값 단독 금지 · ",
         "같은 표본의 무정보 베이스라인과의 차이로 판정한다. 임계값은 발명하지 않고 "
         "베이스라인에서 유도한다."),
        ("불확실성 동반 · ",
         "표본 수와 신뢰구간 없이 달성이라 적지 않는다. 구간이 목표를 품으면 구분 불가이지 "
         "달성이 아니다."),
        ("선택과 보고의 분리 · ", "고르는 데 쓴 표본으로 성능을 보고하지 않는다."),
        ("계측기 없는 목표는 지표가 아니다 · ",
         "계측 배선이 0번 조건이다. 배선이 섰다는 것과 목표를 넘겼다는 것은 다르다."),
    ])

    # 05
    bp.h1(doc, "05", "Co.I — 창업 코파일럿 AI")
    bp.make_table(doc, [
        ["항목", "내용"],
        ["한 줄 정의", FILL],
        ["해결하는 문제", FILL],
        ["기술 구성", FILL],
        ["정량 지표", FILL],
        ["PlaceOS 와의 연결", "PlaceOS Posting 트랙이 외부 코파일럿 연동 계약을 이미 발행해 두었으므로,\n"
                              "Co.I 를 그 자리에 연결하는 구조로 설명한다."],
    ], [3.2, 12.6], sizes=[9.0, 9.0], aligns=[L, L], bold_first_col=True)
    guide(doc, [
        ("이 장을 반드시 채울 것", True),
        ("Co.I 는 박사 과정의 주제이자 면접에서 가장 많이 질문받을 항목입니다. "
         "위 다섯 칸을 비운 채 제출하면 '만들다 만 두 번째 프로젝트'로 읽힙니다.", False),
        ("정량 지표가 아직 없다면, 제출 전에 응답 시간과 처리 질의 수만이라도 측정해 두십시오. "
         "측정하지 않은 값을 적는 것보다는 '현재 측정 중'이 낫습니다.", False),
    ])

    # 06
    bp.h1(doc, "06", "링크 및 연락처")
    bp.make_table(doc, [
        ["구분", "주소"],
        ["PlaceOS 운영", "https://placeos.web.app"],
        ["Co.I", FILL],
        ["저장소", FILL],
        ["이메일", "seoghyeonbag36@gmail.com"],
        ["연락처", BLANK],
    ], [3.2, 12.6], sizes=[9.0, 9.0], aligns=[L, L], bold_first_col=True)

    doc.save(out)
    return out


# ══════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════
#  4) 인재풀 등록 프로필 (공고가 없을 때 — 1~2쪽)
# ══════════════════════════════════════════════════════════════════════════
def build_talent_profile(out: Path) -> Path:
    """공고 없이 보내는 인재풀 등록용. 심사 통과가 아니라 기억에 남는 것이 목적이라
    이력서보다 짧고, 대신 '무엇을 줄 수 있는가'와 '보관 동의'를 명시한다."""
    doc = Document()
    sec = bp.setup(doc)
    bp.add_footer(sec, "인재풀 등록 프로필")

    doc_title(doc, "인재풀 등록 프로필",
              "Talent Pool Profile · 채용 공고 없이 제출하는 사전 등록용 요약본")

    # 1. 신원 · 희망 조건
    bp.h2(doc, "01", "기본 정보 및 희망 조건")
    bp.make_table(doc, [
        ["성명", BLANK, "희망 직무", "기술사업화 / 창업보육 / 데이터 엔지니어링"],
        ["연락처", BLANK, "고용 형태", "정규직 · 계약직 모두 가능"],
        ["이메일", "seoghyeonbag36@gmail.com", "근무 가능 시점", FILL],
        ["포트폴리오", "https://placeos.web.app", "근무 희망 지역", "서울 전역"],
    ], [2.2, 5.4, 2.8, 5.4], head=False, sizes=[8.5, 9.0, 8.5, 9.0],
        aligns=[L, L, L, L], zebra=False, bold_first_col=True)

    # 2. 한 줄 요약
    bp.h2(doc, "02", "한 줄 요약")
    bp.body(doc,
            "오프라인 상권을 데이터로 재구성하는 SaaS 두 종(PlaceOS · Co.I)을 기획부터 배포까지 "
            "단독으로 만들어 운영 중입니다. 창업자 당사자이면서 동시에 수집 파이프라인부터 "
            "모델, API, 배포까지 전 구간을 다루는 개발자입니다. 창업기업의 사업계획서에 적힌 "
            "기술이 실제로 구현 가능한지를 직접 판단할 수 있다는 점이 제 차별점입니다.",
            before=2)

    # 3. 기여 가능 직무
    bp.h2(doc, "03", "기여할 수 있는 직무")
    bp.make_table(doc, [
        ["직무", "무엇을 할 수 있는가"],
        ["기술사업화 (TLO)",
         "기술 실사 · 사업화 가능성 판단. 공공 API와 특허 정보를 직접 수집 · 정규화해 "
         "근거 자료를 만들 수 있습니다."],
        ["창업보육 · 창업지원",
         "입주기업 기술 검토, 사업계획서의 기술 항목 검증, 데모데이 자료 구조화. "
         "창업 당사자로서 보육 프로그램을 받는 쪽의 입장을 압니다."],
        ["데이터 · AI",
         "Bronze / Silver / Gold 3계층 파이프라인 설계, 시계열 · 그래프 모델 학습과 서빙, "
         "FastAPI 기반 API 구축 및 클라우드 배포."],
    ], [3.2, 12.6], sizes=[9.0, 9.0], aligns=[L, L], bold_first_col=True)

    # 4. 대표 실적
    bp.h2(doc, "04", "대표 실적 (모두 계측 산출물 기준)")
    bp.make_table(doc, [
        ["프로젝트", "핵심 성과"],
        ["PlaceOS\n(운영 중)",
         f"서울 {M['hubs']}개 상권을 건축물대장으로 실측해 건물 단위 공실 인벤토리 구축 "
         f"({M['units']}유닛 · 층 단위 {M['floor_units']}개)\n"
         f"공실 예측 MAE {M['lstm_mae']} — 지속성 베이스라인 대비 {M['lstm_skill']}% 개선\n"
         f"업종 추천 Top-3 {M['gnn_top3']}% — 거점 사전분포 대비 {M['gnn_skill']}%p 개선\n"
         f"코드 {M['loc']} 라인 · GitHub Actions - Cloud Run 자동 배포"],
        ["Co.I", FILL],
    ], [3.0, 12.8], sizes=[9.0, 8.5], aligns=[C, L], bold_first_col=True)
    bp.caption(doc,
               f"미달 항목도 함께 밝힙니다. 공실 예측의 방향 정확도는 {M['lstm_dir']}% 로 "
               f"무정보 상수 베이스라인 {M['lstm_dir_base']}% 에 {M['lstm_dir_skill']}%p 미달입니다. "
               "재지 않은 값을 달성으로 적지 않는 것이 이 프로젝트의 기본 규칙입니다.")

    # 5. 기술
    bp.h2(doc, "05", "보유 기술")
    bp.make_table(doc, [
        ["구분", "내용"],
        ["Backend · Data",
         "Python, FastAPI, PostgreSQL / PostGIS, Redis, Celery, Airflow, Selenium / Playwright"],
        ["ML", "PyTorch, PyTorch Geometric (GNN), LSTM, MLflow"],
        ["Frontend · Infra",
         "React, TypeScript, Vite, 네이버 지도 API / Docker, GitHub Actions, Cloud Run"],
        ["공공데이터",
         "건축HUB 건축물대장, 서울시 상권분석, R-ONE 부동산통계, KOSIS, 공정위 정보공개서"],
    ], [3.2, 12.6], sizes=[9.0, 8.5], aligns=[L, L], bold_first_col=True)

    # 6. 학력 · 경력
    bp.h2(doc, "06", "학력 · 경력 요약")
    bp.make_table(doc, [
        ["구분", "기간", "내용"],
        ["학력", BLANK, BLANK],
        ["경력", BLANK, BLANK],
        ["자격", BLANK, BLANK],
    ], [2.2, 4.0, 9.6], sizes=[9.0, 8.5, 9.0], aligns=[C, C, L], bold_first_col=True)
    bp.caption(doc, "상세 경력기술서와 포트폴리오는 요청 시 즉시 제출 가능합니다.")

    # 7. 제안
    bp.h2(doc, "07", "제안드릴 수 있는 것")
    bp.body(doc,
            "채용 여부와 무관하게, 귀 기관의 보육 · 입주 기업 중 오프라인 점포나 공간을 기반으로 "
            "하는 팀이 있다면 PlaceOS의 상권 분석 리포트를 무상으로 제공해 드릴 수 있습니다. "
            "대상 상권의 건물 단위 공실 현황, 업종 구성, 유동 특성을 정리한 자료이며, "
            "필요하시면 샘플을 먼저 보내 드리겠습니다.", before=2)

    # 8. 보관 동의
    bp.h2(doc, "08", "개인정보 보관 및 활용 동의")
    guide(doc, [
        ("본인은 채용 목적의 인재풀 등록을 위해 아래와 같이 개인정보 보관 및 활용에 동의합니다.", True),
        ("수집 항목: 성명, 연락처, 이메일, 학력, 경력, 자격 사항", False),
        ("이용 목적: 향후 채용 공고 발생 시 지원 안내 및 서류 검토", False),
        ("보관 기간: 등록일로부터 1년. 기간 경과 시 파기하여 주시기 바랍니다.", False),
        ("철회 방법: 위 이메일로 요청 시 즉시 파기 (동의 철회로 불이익 없음)", False),
        ("", False),
        ("등록일 " + BLANK + "          성명 " + BLANK + "  (서명)", False),
    ])
    bp.caption(doc,
               "기관 채용 담당자는 동의 없는 개인정보를 보관할 수 없습니다. "
               "이 문구가 없으면 등록 요청 자체를 거절해야 하는 경우가 있으므로 반드시 넣습니다.")

    doc.save(out)
    return out


BUILDERS = [
    ("PlaceOS_지원서류_1_이력서.docx", build_resume),
    ("PlaceOS_지원서류_2_경력기술서.docx", build_experience),
    ("PlaceOS_지원서류_3_포트폴리오.docx", build_portfolio),
    ("PlaceOS_지원서류_4_인재풀등록프로필.docx", build_talent_profile),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--dir", default=".", help="출력 디렉터리")
    ap.add_argument("--fonts", default=None, help="폰트 캐시 디렉터리")
    args = ap.parse_args()

    outdir = Path(args.dir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        cache = Path(args.fonts).resolve() if args.fonts else work / "fonts"
        fonts = bp.fetch_fonts(cache)
        for i, (name, fn) in enumerate(BUILDERS, 1):
            out = outdir / name
            print(f"{i}) {name}")
            fn(out)
            print(f"   생성 {out.stat().st_size:,}B")
            sub = work / f"embed{i}"
            sub.mkdir(exist_ok=True)
            bp.embed_fonts(out, fonts, sub)
            bp.verify_embedding(out)
            print(f"   완료 {out.stat().st_size:,}B")
    print(f"\n출력 디렉터리: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
