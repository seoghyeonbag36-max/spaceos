"""서빙이 읽는 Gold 산출물이 **저장소에 실제로 실려 나가는가**.

2026-08-25 에 `data/gold/platform_posting_store_area.json`(914B · 공정위 가맹사업
정보공개서 기반 평균 점포 면적 A)이 `.gitignore` 에 걸려 **추적되지 않고 있던 것**을
찾았다. 형제 세 파일(`platform_posting_revenue`·`platform_posting_cost_rates`·
`platform_posting_inputs`)은 전부 `!` 예외가 있는데 이것만 빠져 있었다.

새로 클론한 환경(CI · Vercel 배포)에는 파일이 없으므로 `posting_revenue` 가 임차료
**역산 폴백**으로 내려간다 — docs/feature-posting.md §0-I 가 *"한식집 7.1평은 실물이
아니었다"* 며 기각한 바로 그 모델이다. 로컬에는 파일이 있어 전 테스트가 통과하므로,
**개발 기계에서는 영원히 안 드러난다.**

이 저장소가 반복해 잡아 온 양식과 같다 — 게이트는 100% 인데 산출물이 제품에 안 닿고,
폴백이 그 사실을 덮는다. 다만 이번 자리는 코드가 아니라 `.gitignore` 였다.

`area_basis() == "ftc"` 단언(test_posting_revenue)이 CI 에서 결국 걸리기는 한다.
그러나 그때 드러나는 것은 "A 의 출처가 다르다"이지 "파일이 안 실렸다"가 아니라,
원인까지 가는 데 한참 걸린다. 여기서 **원인 자리에서** 막는다.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_GOLD = _ROOT / "data" / "gold"

# 백엔드 서비스가 실제로 여는 Gold 경로. 거점별 파일은 대표 한 곳(신사동 가로수길 —
# PoC 출발점)만 확인한다. 54거점 전수는 coverage 게이트가 따로 센다.
_SHIPPED = [
    "platform_posting_store_area.json",
    "platform_posting_revenue.json",
    "platform_posting_cost_rates.json",
    "platform_posting_inputs.json",
    "platform_industry_recommend.json",
    # 2026-09-05 추가 — services/industry_fit 이 읽는 층·용도별 업종 관측 분포.
    "platform_industry_floor_fit.json",
    "platform_vacancy_forecast.json",
    "platform_events.json",
    "platform_page_footfall.json",
    "page_footfall_hourly.json",
    # 2026-08-25 추가 — posting_inputs._unit_jipgyegu_flpop 이 읽는다.
    # 빠지면 foot 서열이 조용히 상권(입도 절반)으로 내려간다.
    "platform_unit_foot.json",
    "garosugil/vacant_units.json",
    # 2026-09-05 추가 — services/floor_vacancy 가 읽는 층 단위 매물 목록.
    # 빠지면 배포 환경에서 `/floor-vacancies` 가 전 거점 404 라, 화면은 층별 매물
    # 섹션을 통째로 안 그린다(= "이 거점엔 층 매물이 없다"처럼 멀쩡해 보인다).
    "garosugil/vacant_floor_units.json",
    "garosugil/page_building_master.geojson",
    "garosugil/calibration.json",
    "garosugil/program_content_context.csv",
]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(("git", "-C", str(_ROOT)) + args,
                          capture_output=True, text=True)


@pytest.mark.parametrize("rel", _SHIPPED)
def test_shipped_gold_file_is_tracked(rel: str):
    """서빙이 읽는 Gold 파일은 git 이 **추적**하고 있어야 한다.

    존재만 보면 안 된다 — 로컬에는 있고 저장소에는 없는 것이 정확히 이 결함이다.
    """
    path = _GOLD / rel
    assert path.exists(), f"{rel} 이 로컬에도 없다 — 파이프라인부터 돌릴 것"

    r = _git("ls-files", "--error-unmatch", f"data/gold/{rel}")
    if r.returncode != 0 and "not a git repository" in (r.stderr or "").lower():
        pytest.skip("git 저장소가 아니다(배포 아티팩트 등) — 추적 여부를 물을 수 없다")
    assert r.returncode == 0, (
        f"data/gold/{rel} 이 git 에 없다. 로컬에는 있으므로 이 기계에서는 전 테스트가 "
        f"통과하지만, 새로 클론한 환경(CI·Vercel)에서는 파일이 없어 서비스가 조용히 "
        f"폴백으로 내려간다. `.gitignore` 에 `!data/gold/{rel}` 예외를 추가할 것."
    )
