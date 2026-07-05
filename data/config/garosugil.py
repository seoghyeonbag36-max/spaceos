"""PoC 거점 상수 — 강남구 신사동 가로수길.

B단계 수집기(seoul_trdar/localdata/kakao_local/naver_blog)와 Gold 빌더가 공유한다.
좌표·코드는 probe_garosu_d1.py 와 동일 축. ※ 표시는 실행 전 재확인 항목.
"""
from __future__ import annotations

SLUG = "garosugil"          # bronze/silver/gold 하위 폴더명

# 코어 축 (probe_garosu_d1.py 와 동일)
CX = 127.0230               # 경도(lon)
CY = 37.5205                # 위도(lat)
RADIUS_M = 400              # 반경 수집 기본값

SIGUNGU_CD = "11680"        # 강남구 시군구코드
BJDONG_CD = "10700"         # 신사동 법정동코드 뒤 5자리 (1168010700)
ADSTRD_CD = "1168051000"    # 신사동 행정동코드 — 생활인구 ADSTRD_CODE_SE 필터 ※자릿수 재확인

# LOCALDATA 개방자치단체코드 (강남구) ※포털 '개방자치단체코드표'로 재확인
LOCALDATA_LOCAL_CODE = "3220000"

# 서울 상권분석서비스: 상권명(TRDAR_CD_NM)에 이 키워드가 포함되면 거점 상권으로 채택
TRDAR_NAME_KEYWORDS = ("가로수길", "신사역")

# Program 수집 키워드 (네이버 블로그 검색 + 데이터랩 트렌드)
BLOG_KEYWORDS = ("가로수길 맛집", "가로수길 카페", "가로수길 팝업")
TREND_KEYWORD_GROUPS = {          # 데이터랩은 그룹 최대 5개
    "가로수길": ["가로수길"],
    "신사동": ["신사동", "신사역"],
}
