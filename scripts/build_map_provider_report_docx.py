# -*- coding: utf-8 -*-
"""지도 공급자 재검증 보고서(.docx) 생성기 — 네이버·카카오 → 구글 전환 타당성.

정본은 `docs/finding-map-provider-google-2026-09-15.md` 다. 이 스크립트는 그 문서를
읽는 사람(투자자·의사결정자)용으로 조판만 바꿔 낸다 — **수치를 여기서 새로 만들지 않는다.**

레이아웃·한글 폰트 임베딩 헬퍼는 `build_business_plan_docx.py` 를 그대로 재사용한다
(폰트명만 지정하면 뷰어에서 □ 로 깨지므로 subset → .odttf 난독화 → fontTable.xml 배선).

실행:
    python scripts/build_map_provider_report_docx.py [-o 출력경로] [--fonts 폰트캐시]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_business_plan_docx import (  # noqa: E402
    ACCENT,
    C,
    INK,
    J,
    L,
    MUTED,
    NAVY,
    NOTEFILL,
    RULE,
    Document,
    WD_BREAK,
    add_footer,
    body,
    bullets,
    caption,
    embed_fonts,
    fetch_fonts,
    h1,
    h2,
    make_table,
    note_box,
    para,
    para_border,
    run,
    setup,
    table_title,
    verify_embedding,
)


def cover(doc):
    p = para(doc, before=84, after=0, line=1.1)
    run(p, "PlaceOS", size=40, bold=True, color=NAVY, spacing=-20)
    p = para(doc, before=2, after=0, line=1.25)
    run(p, "물리적 상권의 디지털 트윈 플랫폼", size=14, color=MUTED)

    p = para(doc, before=24, after=0, line=1.2)
    para_border(p, ("top",), color=ACCENT, sz=18, space=14)
    run(p, "지도 공급자 재검증", size=24, bold=True, color=INK)
    p = para(doc, before=3, after=0, line=1.35)
    run(p, "네이버·카카오를 구글로 바꿀 것인가", size=13, bold=True, color=ACCENT)

    p = para(doc, before=20, after=0, line=1.5)
    run(p, "검증 12라운드 ", size=10.5, bold=True, color=MUTED)
    run(p, "— 코드 실측 5 · 외부 근거 7", size=10.5, color=INK)

    note_box(doc, [
        ("판정: 바꾸지 않는다.", True),
        ("기능(거리뷰 실사)·비용(무료 한도 1,000배)·약관(영구 적재 금지) 세 축에서 손실이고, "
         "M&A 정합성에서는 방향이 반대다. 다만 이 검증에서 현행 구조의 결함 1건이 따라 나왔다 — "
         "카카오 로컬 응답의 영구 저장이 약관에 저촉한다. 그건 구글 전환과 무관하게 지금 고친다.", False),
    ])

    rows = [
        ["축", "결론"],
        ["거리뷰 실사", "!구글 국내 촬영 2018~19 이후 정지 — 공실 지상검증이 무효화된다"],
        ["요금", "네이버 0.1원/건·월 1,000만건 무료 ↔ 구글 9.8원/건·월 1만건 무료"],
        ["약관", "구글은 Places 영구 저장·타사지도 혼용 금지 → 부분 전환도 봉쇄"],
        ["좌표", "구글은 한국 좌표 비표시 이행 중(2026-08-21~) — 제품의 1차 키다"],
        ["M&A", "인수 후보(네이버·카카오)의 방어 자산과 같은 계열에 있는 것이 프리미엄"],
        ["구글이 이기는 축", "GCP 청구 일원화 · 해외 확장 재사용성 — 둘 다 Exit 시계 밖"],
    ]
    make_table(doc, rows, [3.6, 12.6], sizes=[9.0, 9.0], aligns=[L, L], bold_first_col=True)

    p = para(doc, before=26, after=0, line=1.5)
    run(p, "2026년 9월 15일", size=9.5, color=MUTED)
    p = para(doc, before=0, after=0, line=1.5)
    run(p, "정본 — docs/finding-map-provider-google-2026-09-15.md", size=9.5, color=MUTED)

    p = para(doc, before=0, after=0)
    run(p, "").add_break(WD_BREAK.PAGE)


def sec_rounds(doc):
    h1(doc, "1", "검증을 어떻게 했나")
    body(doc, "문서나 기억이 아니라 호출부·약관·고시를 셌다. 라운드 12개 중 5개는 저장소 실측이고, "
              "7개는 외부 1차 근거(정부 발표·공식 요금표·서비스 약관)다.", line=1.55)

    rows = [
        ["R", "무엇을 검증했나", "방법", "결과"],
        ["V1", "네이버·카카오 호출부 전수", "grep 인벤토리 · naver.maps.* 심볼 집계", "15종 / 81회 / 6파일"],
        ["V2", "지도 렌더링에 카카오가 쓰이나", "프론트 소스 전수", "!0건 — 안 쓰인다"],
        ["V3", "지오코딩 실사용 여부", "naver_geo import 추적", "!0건 — 쟁점 아님"],
        ["V4", "거리뷰가 별도 상품인가", "저장소 실측 기록", "Dynamic Map 포함 · 추가 과금 없음"],
        ["V5", "마이그레이션 표면", "지도 접촉 파일 LOC", "소스 2,882 · 테스트 810 · 스텁 212"],
        ["V6", "구글 반출 규제 현황", "협의체 결정·후속 이행 추적", "조건부 허가 · 이행 중 · 논의 정체"],
        ["V7", "스트리트뷰 국내 실사 자산", "촬영 시점·갱신 이력", "!2018~19 촬영 후 정지"],
        ["V8", "요금", "NCP 단가 ↔ GMP SKU 단가", "단가 98배 · 무료량 1,000배 차"],
        ["V9", "약관", "GMP 캐시·타사지도 조항 / 카카오 저장 조항", "!양쪽 다 제약 — 구글이 더 엄격"],
        ["V10", "수집 전략 이식성", "total_count ↔ Places 페이지네이션", "60건 하드캡 · 총계 미제공"],
        ["V11", "시장·사업화", "MAU · 네카오 방어 전략", "네이버 2,626만 ↔ 구글 905만"],
        ["V12", "인프라 정합", "이미 GCP(Cloud Run·Firebase) 사용", "구글의 유일한 실질 이점"],
    ]
    make_table(doc, rows, [1.1, 4.9, 5.4, 4.8], sizes=[8.5, 8.5, 8.5, 8.5],
               aligns=[C, L, L, L])
    caption(doc, "표 1. 검증 라운드 — V2·V3·V9 는 착수 전 통념과 결과가 달랐다.")


def sec_layers(doc):
    h1(doc, "2", "먼저 용어를 가른다 — '지도 API' 는 한 덩어리가 아니다")
    body(doc, "전환 판단이 흐려지는 이유는 네 가지를 한 이름으로 부르기 때문이다. "
              "PlaceOS 에서 지도 관련 의존은 네 계층으로 갈라지고, 계층마다 답이 다르다.", line=1.55)

    rows = [
        ["계층", "지금 쓰는 것", "구글 대체", "판정"],
        ["① 베이스맵 렌더링", "네이버 Dynamic Map v3", "가능", "대체해도 얻는 것이 없다"],
        ["② 거리뷰 실사", "naver.maps.Panorama\n(+카카오 로드뷰 링크)", "!불가에 가깝다", "!촬영이 7~8년 전이다"],
        ["③ 지오코딩", "사실상 미사용", "가능", "쟁점이 아니다"],
        ["④ 로컬 데이터\n(POI·리뷰·트렌드)", "카카오 로컬 · 네이버 블로그\n· 데이터랩", "!불가", "약관·수집구조 양쪽"],
    ]
    make_table(doc, rows, [3.5, 4.9, 2.6, 5.2], sizes=[8.5, 8.5, 8.5, 8.5], aligns=[L, L, C, L])
    caption(doc, "표 2. ②·④ 가 PlaceOS 의 실체다. ① 만 보고 전환하면 바뀌는 것은 타일 그림 한 장이고, "
                 "잃는 것은 실사 채널과 수집 파이프라인이다.")

    h2(doc, "2.1", "실측으로 바로잡은 전제 — 카카오는 지도를 그리지 않는다")
    body(doc, "프론트엔드 전체에서 카카오 지도 SDK 호출은 0건이다. 카카오가 쓰이는 곳은 전부 데이터 쪽이다 — "
              "점포·카테고리 수집(kakao_local.py), 그래프 노드와 Program 컨텍스트(build_gold.py), "
              "가게 반자동 조회(store_lookup.py), 로드뷰 링크(검증 CSV).", line=1.55)
    note_box(doc, [
        ("따라서 이 질문은 두 개의 서로 다른 문제였다.", True),
        ("(가) 네이버로 그리는 지도를 구글로 바꿀 것인가 — 기술적으로 쉽고, 이득이 없다. "
         "(나) 카카오로 받는 점포 데이터를 구글로 바꿀 것인가 — 약관상 더 나쁘고, 수집 전수성이 떨어진다.", False),
    ], fill=NOTEFILL, border=NAVY)


def sec_code(doc):
    h1(doc, "3", "코드 실측 — 무엇이 어디에 얼마나 걸려 있나")
    rows = [
        ["측정 항목", "값"],
        ["naver.maps.* 심볼", "15종 / 81회 / 프론트 6파일"],
        ["가장 많이 쓰는 심볼", "LatLng 32 · Event.addListener 15 · Marker 7 · Point 6 · Polygon 5"],
        ["거리뷰·히트맵", "Panorama 4 · visualization.HeatMap 2"],
        ["지도 접촉 소스", "2,882 LOC (naverMap.ts 175 · MapShell · useMapMarkers · BuildingViewer 등)"],
        ["지도 관련 테스트", "810 LOC + 네이버 SDK 스텁 212 LOC"],
        ["지오코딩 실사용", "!0건 (naver_geo.py 를 import 하는 코드는 키 점검 스크립트뿐)"],
        ["카카오 지도 SDK", "!0건"],
    ]
    make_table(doc, rows, [4.2, 12.0], sizes=[9.0, 8.5], aligns=[L, L], bold_first_col=True)
    caption(doc, "표 3. 2026-09-15 저장소 실측.")

    body(doc, "좌표계·폴리곤은 지도 공급자와 무관하다는 점도 확인했다. 건물 폴리곤은 V-World, "
              "행정동 배정은 kNN(PNU 조인과 99.2% 일치), 층·호실은 건축HUB 대장이고 TM 계열 변환은 "
              "pyproj 로 자체 처리한다. 베이스맵을 바꿔도 이 산출물은 하나도 바뀌지 않는다 — "
              "반대로, 바꿔서 좋아지는 산출물도 없다.", line=1.55)


def sec_law(doc):
    h1(doc, "4", "규제 — 구글 반출은 '허가'됐지만 '정착'되지 않았다")
    rows = [
        ["시점", "사건"],
        ["2025-11-11", "협의체가 구글에 영상 보안처리 · 좌표 표시 제한 · 서버·사후관리 보완 요청"],
        ["2026-02-27", "!측량성과 국외반출 협의체, 1:5,000 국외반출 조건부 허가 의결 (18년 논쟁 종결)"],
        ["2026-04~05", "후속 논의 정체 — 정부·구글 교착, 산업계 우려 보도"],
        ["2026-08-10", "구글, 청와대·군 시설 등 블러 처리 시작"],
        ["2026-08-21", "!한국 IP 접속 시 대한민국 지도의 좌표 표시 비활성화 — 플러스 코드로만 표시"],
        ["2026-09-09", "구글, 한국 영역 좌표를 국내외 이용자 모두에게 비표시하겠다고 발표"],
    ]
    make_table(doc, rows, [2.6, 13.6], sizes=[8.5, 8.5], aligns=[C, L], bold_first_col=True)
    caption(doc, "표 4. 허가 조건 — 국내 제휴기업이 국내 서버에서 가공·정부 검토를 거친 데이터만 반출 · "
                 "보안사고 대응 프레임워크 · 긴급 대응용 '레드버튼' · 한국 지도 전담관 국내 상주 · "
                 "내비·길찾기에 필요한 제한된 데이터만(등고선 등 민감 항목 제외).")

    h2(doc, "4.1", "이게 우리에게 갖는 함의 — 좌표가 제품의 1차 키다")
    body(doc, "PlaceOS 는 좌표로 만들어진 제품이다. 마커·폴리곤·PIP 귀속·kNN 행정동 배정·거리뷰 방위각이 "
              "전부 위·경도 위에 선다. 그런데 구글이 정부 조건을 이행하는 방향이 '한국 좌표를 사용자에게 "
              "보이지 않게 한다' 다.", line=1.55)
    body(doc, "소비자용 지도 UI 의 좌표 표시와 Maps Platform API 응답은 별개일 수 있다 — 이건 확인하지 "
              "못했고, 확인 못 한 채로 남긴다(7장). 다만 결정에 필요한 건 확정이 아니라 방향이다. "
              "제품의 1차 키가 규제 이행의 대상이 된 공급자로, 그 이행이 진행 중인 시점에 옮겨 갈 이유가 없다.",
         line=1.55)


def sec_roadview(doc):
    h1(doc, "5", "거리뷰 — 여기서 결론이 갈린다")
    note_box(doc, [
        ("구글 스트리트뷰 국내 촬영은 2018~2019년 전국 수집 이후 갱신이 멈춰 있다.", True),
        ("2016년 반출 무산 뒤 구글의 국내 지도 사업 활동이 사실상 정지한 것과 같은 이력이다. "
         "2026-02 허가는 1:5,000 국가기본도 반출이지, 파노라마 재촬영 계획이 아니다.", False),
    ])

    rows = [
        ["쓰임", "어디에", "구글로 바꾸면"],
        ["공실 판정 지상검증",
         "roadview_capacity_{yeonnam,ikseon,myeongdong}.csv · roadview_sample.md — 30동 라벨링. "
         "건물 전체 호실 기준으로 간판·층별 안내판·창문·임대 현수막을 보고 판정한다",
         "!7~8년 전 사진으로 라벨링 = 채점 자체가 무효"],
        ["화면 실사", "BuildingViewer.tsx — 파노라마 + 촬영일(photodate) 표기", "2018년 사진에 '2018 촬영' 을 붙이는 화면이 된다"],
        ["골목 커버리지", "파노라마 없음은 pano_status 로 받아 폴백을 그린다", "골목 상권(익선·연남)에서 폴백 비율이 급등"],
        ["과금 구조", "Panorama 는 Dynamic Map 서브모듈 — 별도 상품·키·과금이 없다", "독립 SKU. Dynamic Street View 는 Pro 등급(월 5천 무료)"],
    ]
    make_table(doc, rows, [2.8, 7.4, 6.0], sizes=[8.5, 8.0, 8.5], aligns=[L, L, L], bold_first_col=True)
    caption(doc, "표 5. 거리뷰 축에서는 '더 낡은 사진을 돈 내고 쓰는' 교환이 된다.")


def sec_price(doc):
    h1(doc, "6", "요금 — 무료 한도가 1,000배, 단가가 약 98배")
    rows = [
        ["항목", "네이버 클라우드 Maps", "Google Maps Platform", "배수"],
        ["동적 지도 단가", "0.1원/건", "$7.00/1,000 ≈ 9.8원/건", "!≈98배"],
        ["동적 지도 무료", "월 1,000만 건(대표계정 1개)", "월 1만 건(Essentials)", "!1,000배"],
        ["정적 지도", "2원/건", "$2/1,000 ≈ 2.8원/건", "1.4배"],
        ["지오코딩", "0.5원/건", "$5/1,000 ≈ 7원/건", "14배"],
        ["거리뷰", "동적 지도에 포함(추가 과금 없음)", "독립 SKU · Static $5.6~7.0/1,000", "—"],
        ["과금 단위", "지도 로딩 시에만 증가(zoom·marker 미포함)", "map load 기준(유사)", "—"],
    ]
    make_table(doc, rows, [3.0, 5.6, 5.4, 2.2], sizes=[8.5, 8.5, 8.5, 8.5], aligns=[L, L, L, C],
               bold_first_col=True)
    caption(doc, "표 6. 환율 1,400원/USD 가정. 단가는 볼륨 구간에 따라 내려간다.")

    table_title(doc, "월 지도 로드 규모별 원가")
    rows = [
        ["월 지도 로드", "네이버", "구글"],
        ["1만 (지금 수준)", "0원", "0원 (무료 한도 내)"],
        ["5만 (파일럿 5~10건)", "0원", "!≈ 39만원/월"],
        ["100만 (B2B 확대)", "0원", "!≈ 970만원/월"],
    ]
    make_table(doc, rows, [5.4, 5.4, 5.4], sizes=[9.0, 9.0, 9.0], aligns=[L, C, C], bold_first_col=True)
    body(doc, "MVP 단계에서는 둘 다 0원이라 '비용은 쟁점 아님' 으로 보이기 쉽다. 그런데 B2B SaaS 는 "
              "고객이 늘면 지도 로드가 선형으로 늘고, 그 지점에서 구글은 월 수백만원대 고정비가 된다. "
              "DaaS 월 500만원 구독 모델에서 지도 원가가 수익의 두 자릿수 %를 먹는 구조는 만들지 않는다.",
         before=8, line=1.55)


def sec_terms(doc):
    h1(doc, "7", "약관 — 전환이 막히고, 현행 구조의 결함도 같이 드러났다")

    h2(doc, "7.1", "구글 — 데이터 레이크와 구조적으로 충돌한다")
    bullets(doc, [
        ("Places 콘텐츠 캐시·저장 금지. ", "예외는 place_id(무기한)와 좌표(최대 30일)뿐이다. "
                                     "이름·평점·리뷰·사진·전화번호는 실시간 요청·표시가 전제다."),
        ("파생 데이터셋 생성 금지. ", "\"export, extract, or otherwise scrape Google Maps Content "
                               "for use outside the Services\"."),
        ("타사 지도와 함께 쓰지 못한다. ", "'No use with a non-Google map' — Places 콘텐츠를 비구글 지도에 표시, "
                                  "스트리트뷰와 비구글 지도를 같은 화면에 표시, 구글 지도를 비구글 콘텐츠에 "
                                  "연결하는 것이 모두 금지다."),
    ], size=9.5)
    note_box(doc, [
        ("그래서 부분 전환이라는 중간 해가 없다.", True),
        ("PlaceOS 는 Bronze→Silver→Gold 영구 적재가 아키텍처 그 자체다(data/gold 291파일·106MB). "
         "구글 Places 를 수집원으로 쓰는 순간 이 구조가 약관과 정면으로 부딪친다. 그리고 마지막 조항이 "
         "'네이버 베이스맵 + 구글 스트리트뷰' 같은 하이브리드 절충안까지 봉쇄한다.", False),
    ])

    h2(doc, "7.2", "카카오 — 지금 우리가 저촉하고 있다 (이번 검증의 부산물)")
    body(doc, "카카오 로컬 API 는 응답 결과를 별도 저장하지 못하고 실시간 호출만 허용한다는 정책을 운영하고, "
              "장소명·위경도·place_url 을 서비스 DB 에 영구 저장하는 것은 약관 위반으로 안내된다. "
              "2026년 카카오 데브톡에는 '정책·약관 위반에 따른 API 차단 예정 조치' 공지와 캐싱 허용 범위 "
              "문의가 다수 올라와 있다 — 사문화된 조항이 아니라 집행되는 조항이다.", line=1.55)
    rows = [
        ["우리 코드의 실제 상태", "무엇을 하나"],
        ["data/collectors/kakao_local.py", "bronze/{거점}/kakao_places.json 파일로 적재(영구)"],
        ["data/pipelines/build_gold.py:244", "!node_id \"kakao:{id}\" · source \"kakao\" 로 Gold 노드 영구화"],
        ["build_gold.py:473,527", "program_content_context 입력"],
        ["ml/training/train_gnn.py", "그 노드로 GNN 학습"],
    ]
    make_table(doc, rows, [6.2, 10.0], sizes=[8.5, 8.5], aligns=[L, L], bold_first_col=True)
    body(doc, "이건 구글 전환과 무관하게 지금 정리해야 한다. 방향은 명확하다 — 영구 보관·재배포가 열린 "
              "공공데이터로 저장층을 옮기고(상가정보 API·지방행정 인허가. 이미 build_page_master.py 의 "
              "1차 소스다), 카카오는 응답을 저장하지 않는 실시간 조회·크로스체크에만 남긴다. "
              "구글로 옮겨도 이 문제는 해결되지 않고 더 엄격해진다(좌표 30일 캐시 상한).",
         before=8, line=1.55)


def sec_collect(doc):
    h1(doc, "8", "수집 전략이 이식되지 않는다")
    body(doc, "kakao_local.py 의 전수 수집은 응답 meta.total_count 가 노출 상한(45건)과 무관하게 실제 총계를 "
              "알려준다는 성질에 기대어 원을 재귀 분할한다 — 27거점 실측 23,850건(분할 전 노출 5,646건, 4.2배). "
              "분할 계수 산정이 total_count 없이는 성립하지 않는다.", line=1.55)
    body(doc, "구글 Places Nearby Search 는 페이지당 20건·최대 3페이지 = 60건 하드캡이고 총계를 주지 않는다 "
              "(게다가 next_page_token 이 즉시 유효하지 않아 2~5초 대기가 필요하다). 총계가 없으면 "
              "'몇 배 더 쪼개야 하는가' 를 알 수 없어 분할이 맹목적 격자 탐색이 되고, 호출 수는 늘면서 "
              "전수성은 보장되지 않는다. 수집기를 다시 설계해야 하고, 결과는 지금보다 나빠진다.", line=1.55)


def sec_biz(doc):
    h1(doc, "9", "사업화·M&A — 방향이 반대다")
    rows = [
        ["근거", "수치"],
        ["국내 지도앱 MAU (2024-11, 모바일인덱스)", "!네이버지도 2,626만 · 카카오맵 1,070만 · 구글지도 905만"],
        ["내비 이용 (최근 3년 신차 구입자 15,967명)", "티맵 74% · 카카오맵 12% · 네이버지도 7%"],
    ]
    make_table(doc, rows, [6.6, 9.6], sizes=[8.5, 8.5], aligns=[L, L], bold_first_col=True)

    h2(doc, "9.1", "데모 설득력")
    body(doc, "고객은 프랜차이즈 본사·자산운용사·지자체다. 네이버 지도 화면 위에 공실 히트맵을 얹으면 "
              "그들이 매일 쓰는 지도 위에서 이야기가 시작된다. 구글 지도로 바꾸면 '국내 상권 데이터인데 왜 "
              "구글?' 이라는 질문을 데모마다 받는다. 지자체 고객에서는 특히 불필요한 마찰이다.", line=1.55)

    h2(doc, "9.2", "M&A 정합성이 반대로 움직인다")
    body(doc, "목표는 18~24개월 내 네이버/카카오/직방 Exit 이다. 그런데 2026년 반출 허가 이후 인수 후보들의 "
              "대응 전략이 공개돼 있다 — 네이버는 '구글이 단기간에 따라잡을 수 없는 로컬 데이터(예약·블로그 "
              "리뷰)' 로 방어하고, 카카오는 초정밀 실시간 기능으로 차별화한다. 대한공간정보학회는 향후 10년 "
              "최대 197조원 손실을 경고했다.", line=1.55)
    note_box(doc, [
        ("PlaceOS 가 쌓는 것은 정확히 그 방어선의 재료다.", True),
        ("블로그 리뷰 감성, 건물 단위 공실, 업종 시너지 GNN. 인수 후보가 지키려는 자산과 같은 계열에 "
         "있는 것이 프리미엄이고, 구글 스택으로 옮기는 것은 그 정합성을 스스로 깎는 일이다. 실사에서 "
         "'우리 생태계로 이식 가능한가' 를 물을 때, 이미 네이버 지도·네이버페이·네이버 블로그·데이터랩으로 "
         "붙어 있는 제품이 답하기 쉽다.", False),
    ])

    h2(doc, "9.3", "반대 논거도 적는다")
    body(doc, "구글로 가면 얻는 것이 있다 — 해외 확장 시 동일 스택, 전 세계 20억 사용자 기반의 지도 품질, "
              "GCP 단일 청구(우리는 이미 Cloud Run·Firebase 를 쓴다). 다만 이 셋은 18~24개월 Exit 시계에 "
              "들어오지 않는다. 해외 확장은 로드맵에 없고(서울 66거점 → 고양·파주 보류), 지도 품질은 국내 "
              "골목 상권에서 오히려 열세다.", line=1.55)


def sec_score(doc):
    h1(doc, "10", "종합 채점 — 9 : 2")
    rows = [
        ["축", "네이버(+카카오 데이터)", "구글", "승"],
        ["베이스맵 렌더링", "충분(국내 상세·골목)", "허가 이행 중, 국내 상세 미정착", "네이버"],
        ["거리뷰 실사", "골목까지 · 촬영일 제공 · 추가 과금 없음", "2018~19 촬영 후 정지 · 독립 SKU", "!네이버"],
        ["POI 수집 전수성", "total_count 기반 재귀 분할", "60건 하드캡 · 총계 없음", "!네이버/카카오"],
        ["리뷰·트렌드 텍스트", "블로그 검색 · 데이터랩(일 25,000건 무료)", "대체 없음(리뷰 저장 금지)", "!네이버"],
        ["약관 정합(영구 적재)", "카카오 저촉 있음 — 조치 필요", "더 엄격(좌표 30일·파생셋·타사지도 금지)", "네이버"],
        ["요금", "0.1원/건 · 월 1,000만 무료", "9.8원/건 · 월 1만 무료", "!네이버"],
        ["좌표 사용 안정성", "규제 대상 아님", "좌표 표시 제한 이행 중", "!네이버"],
        ["국내 사용자 친숙도", "MAU 2,626만", "905만", "네이버"],
        ["M&A 정합", "인수 후보 생태계와 동일 계열", "인수 후보의 경쟁자 스택", "!네이버"],
        ["운영·청구 일원화", "NCP 별도 콘솔", "GCP 단일", "구글"],
        ["해외 확장 재사용성", "낮음", "높음", "구글"],
    ]
    make_table(doc, rows, [3.0, 5.4, 5.4, 2.4], sizes=[8.3, 8.3, 8.3, 8.3], aligns=[L, L, L, C],
               bold_first_col=True)
    caption(doc, "표 7. 구글이 이기는 두 축은 둘 다 18~24개월 Exit 시계 밖이다.")

    h2(doc, "10.1", "전환 난이도가 낮다는 사실은 근거가 되지 못한다")
    body(doc, "낮다고 먼저 인정한다. naver.maps.* 15종은 구글 Maps JS 에 거의 1:1 대응이 있고(Marker→"
              "AdvancedMarkerElement, HeatMap→visualization.HeatmapLayer, Panorama→StreetViewPanorama), "
              "의존이 lib/naverMap.ts 한 파일에 격리돼 있으며 SDK 스텁도 있다. 그런데 쉬우면 나중에도 쉽다. "
              "지금 옮기면 5~9장의 손실을 먼저 확정하고, 이득은 재평가 트리거가 설 때까지 오지 않는다. "
              "재작성 600~900 LOC + 테스트 1,022 LOC 교체 + 지상검증 재수행 불가 + 66거점 회귀로 2주 이상이다.",
         line=1.55)


def sec_trigger(doc):
    h1(doc, "11", "그럼 언제 다시 보나 — 재평가 트리거")
    body(doc, "하나라도 서면 이 문서를 다시 연다. 셋 이상이면 전환을 실제로 설계한다.", line=1.55)
    rows = [
        ["#", "트리거", "현재"],
        ["1", "구글이 국내 파노라마를 재촬영해 서울 거점 골목에서 촬영일 2년 이내 커버리지가 확인된다", "안 섰다"],
        ["2", "Maps Platform API 가 한국 좌표(lat/lng)를 정상 반환함이 실측으로 확정된다", "미확인"],
        ["3", "구글이 한국 Places 데이터의 영구 저장을 허용하는 별도 라이선스를 제공한다", "안 섰다"],
        ["4", "해외 진출이 로드맵에 들어온다(서울·경기 밖, 국외 도시)", "안 섰다"],
        ["5", "네이버·카카오가 요금·약관을 현저히 악화시킨다", "!절반 섰다"],
    ]
    make_table(doc, rows, [1.0, 12.4, 2.8], sizes=[8.5, 8.5, 8.5], aligns=[C, L, C])

    note_box(doc, [
        ("트리거 5는 이미 절반 서 있다 — 카카오 유료화.", True),
        ("2026-02-02~12-31 건당 10원은 80% 할인가이고 정상가는 건당 50원이다. 무료 쿼터도 2026-07-21 부터 "
         "개발자 계정의 첫 활성화 앱 1개에만 제공된다. 66거점 전수 재수집을 거점당 평균 883건(27거점 "
         "23,850건에서 외삽)으로 보면 약 58,000건 → 페이지 15건 + 분할 오버헤드 30% ≈ 5,000 호출/회차. "
         "건당 10원이면 5만원/회차, 정상가 50원이면 25만원/회차다(월 1회 기준 연 60만~300만원).", False),
        ("그런데 이 비용을 피하는 답도 구글이 아니라 7.2의 공공데이터 이전이다 — 같은 조치가 약관 리스크와 "
         "원가를 동시에 없앤다.", True),
    ])


def sec_open(doc):
    h1(doc, "12", "이 검증이 확정하지 못한 것")
    body(doc, "판정을 뒤집을 만한 것은 없지만, 확정과 추정을 섞지 않기 위해 남긴다.", line=1.55)
    rows = [
        ["미확정 항목", "상태와 확인 방법"],
        ["Maps Platform API 의 한국 좌표 반환 여부",
         "2026-08-21 이후 한국 IP 에서 소비자용 구글 지도의 좌표 표시가 비활성(플러스 코드만)인 것은 확인. "
         "Geocoding/Places API 응답 바디가 한국 좌표를 계속 주는지는 공개 문서에서 확인되지 않았다 → "
         "probe-first 1콜 실측 필요(키 발급 선행)"],
        ["Dynamic Street View 정확 단가", "Pro 등급·월 5,000건 무료·파노라마당 과금까지 확인. 구간별 단가는 공식 가격표 확인 필요"],
        ["Google Places 의 국내 소규모 점포 밀도", "카카오 로컬과의 정량 비교 자료를 찾지 못했다. 8장의 결론은 커버리지가 아니라 페이지네이션 구조에 근거한 것이다"],
        ["국내 엣지 지연(KPI 지도 로딩 3초)", "검증 환경이 국내가 아니고, egress 프록시가 네이버·카카오 엔드포인트를 차단해 응답 시간 비교 자체가 불가했다"],
    ]
    make_table(doc, rows, [4.6, 11.6], sizes=[8.5, 8.3], aligns=[L, L], bold_first_col=True)

    h1(doc, "13", "근거 출처")
    bullets(doc, [
        ("규제·제도 ", "국토교통부·정책브리핑 「구글社 1:5000 지도 반출 허가 결정」(2026-02-27) · "
                  "ZDNet 「18년 끌어온 구글 지도 반출 논쟁…'조건부 허가'로 마침표」 · "
                  "전자신문 「구글 지도 반출 허가 후 멈춘 후속 논의」(2026-05-28) · "
                  "YTN 사이언스 「구글 \"한국 지도 방위 좌표 뺀다\"…정부안 수용」(2026-09-09)"),
        ("요금·약관 ", "NAVER Cloud Platform Maps 상품·FAQ · Google Maps Platform Pricing · "
                  "Google Maps Platform Service Specific Terms(§3.2.3 · 'No use with a non-Google map') · "
                  "Places API Policies · 카카오 데브톡 「카카오맵 API 신규 기능 및 무료 쿼터 운영 방식 변경 "
                  "안내」(2026-07-21 시행) · 동 「정책 및 약관 위반에 따른 API 차단 예정 조치」"),
        ("시장 ", "모바일인덱스 MAU(2024-11) · 한국경제 「구글 지도 온다…고도화로 반격 나선 K-맵」 · "
               "딜사이트 「네이버, 로컬 데이터로 '지도업계' 수성」 · 뉴시스(2026-04-07)"),
        ("저장소 실측 ", "apps/frontend/src/** · docs/feature-posting.md §0-V · docs/feature-program.md §0 · "
                    "data/collectors/kakao_local.py · data/pipelines/build_gold.py · data/validation/roadview_* · "
                    "data/gold/*/coverage.json"),
    ], size=9.0)


def build_document(out_path: Path) -> Path:
    doc = Document()
    sec = setup(doc)
    add_footer(sec, "PlaceOS 지도 공급자 재검증 · 2026-09-15")
    cover(doc)
    sec_rounds(doc)
    sec_layers(doc)
    sec_code(doc)
    sec_law(doc)
    sec_roadview(doc)
    sec_price(doc)
    sec_terms(doc)
    sec_collect(doc)
    sec_biz(doc)
    sec_score(doc)
    sec_trigger(doc)
    sec_open(doc)
    doc.save(out_path)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="PlaceOS_지도공급자_재검증_2026-09-15.docx")
    ap.add_argument("--fonts", default=None, help="폰트 캐시 디렉터리(기본: 임시 디렉터리)")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        cache = Path(args.fonts).resolve() if args.fonts else work / "fonts"
        print("1) 문서 생성")
        build_document(out)
        print(f"   → {out.name} ({out.stat().st_size:,}B)")
        print("2) 한글 폰트 임베딩")
        embed_fonts(out, fetch_fonts(cache), work)
        print(f"   → {out.name} ({out.stat().st_size:,}B)")
        print("3) 검증")
        verify_embedding(out)
    print(f"\n완료: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
