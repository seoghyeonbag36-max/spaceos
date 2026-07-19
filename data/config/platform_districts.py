"""[Platform·LSTM] 13거점 ↔ 서울 상권분석서비스 상권코드(TRDAR_CD) 매핑.

2026-07-19 TbgisTrdarRelm 전량(1,650상권) 키워드 매칭 후 수작업 선별:
  - 거점 성격과 무관한 동명 상권 제외(예: 관악구 신사동, 성북구 홍대부중, 주거 골목상권)
  - 발달상권·관광특구·핵심 골목상권 위주 채택
  - hannam의 '용리단길'은 TRDAR 상권 미존재 → 한강진역·한남오거리로 대체 (TODO: 신용산 축 추가 검토)

거점 id 는 apps/backend/app/data/seoul_pages.py 의 DISTRICTS id 와 동일.
"""
from __future__ import annotations

SLUG = "platform13"  # bronze/gold 하위 폴더명 (garosugil PoC 산출물과 분리 보존)

# 거점 id → 채택 상권코드 목록 (코드: TbgisTrdarRelm.TRDAR_CD)
DISTRICT_TRDAR: dict[str, list[str]] = {
    "garosugil": ["3120186", "3120178"],                       # 가로수길 · 신사역
    "apgujeong-rodeo": ["3120202", "3120188"],                 # 압구정로데오역 · 압구정역
    "hongdae": ["3120103", "3120102", "3110564", "3130191", "3130190"],  # 홍대입구역·서교동·3번출구·걷고싶은거리·상점가
    "yeonnam": ["3110562", "3120104"],                         # 연트럴파크 · 연남동(홍대)
    "ikseon": ["3120009", "3130004"],                          # 종로3가역(익선동 포함) · 낙원시장
    "seochon": ["3120002", "3130001", "3110013"],              # 서촌(경복궁역) · 통인시장 · 체부동
    "myeongdong": ["3120028", "3120027", "3001492"],           # 명동거리 · 명동역 · 명동 관광특구
    "euljiro": ["3120031", "3120033", "3120029", "3120026"],   # 을지로3가·4가·2가·입구역
    "seongsu": ["3110131", "3120052", "3130071"],              # 성수동카페거리 · 성수역 · 골목형상점가
    "seoulsup": ["3110120", "3110126", "3120050", "3120051", "3110124", "3130070"],  # 서울숲·뚝섬 축
    "itaewon": ["3120046", "3001491", "3110086", "3110087", "3130061"],  # 이태원역·관광특구·북측·엔틱가구·시장
    "hannam": ["3110095", "3120047"],                          # 한강진역 3번 · 한남오거리
    "songridan": ["3111013", "3111014", "3111015", "3120232", "3120228"],  # 송리단길·송파나루·석촌호수
}

TRDAR_TO_DISTRICT: dict[str, str] = {
    code: did for did, codes in DISTRICT_TRDAR.items() for code in codes
}

ALL_TRDAR_CODES: tuple[str, ...] = tuple(TRDAR_TO_DISTRICT)

# 수집 분기 후보 — 상권분석서비스 현행 개편분(2021~). 빈 분기는 수집기에서 자동 스킵.
QUARTERS: tuple[str, ...] = tuple(
    f"{y}{q}" for y in range(2021, 2027) for q in range(1, 5)
    if not (y == 2026 and q > 2)
)
