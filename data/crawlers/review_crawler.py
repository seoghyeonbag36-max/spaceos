"""상권 리뷰 크롤러 (골격).

네이버 플레이스/카카오맵/구글맵 리뷰를 반경 내 전수 수집하여
상권 감성 지수(Sentiment Score) 산출의 원천 데이터를 만든다.
동적 페이지는 Playwright, 정적 파싱은 BeautifulSoup 사용.
"""
from dataclasses import dataclass


@dataclass
class Review:
    place_name: str
    rating: float
    text: str
    visited_at: str | None = None


def crawl_reviews(lat: float, lng: float, radius_m: int = 300) -> list[Review]:
    """좌표 기준 반경 내 상점 리뷰 전수 수집 (TODO: Playwright 구현)."""
    raise NotImplementedError("Playwright 기반 크롤러 구현 예정")


if __name__ == "__main__":
    print("review_crawler 골격 — TODO: 라페스타 좌표로 수집 구현")
