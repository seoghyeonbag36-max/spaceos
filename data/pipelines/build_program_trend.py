"""[Program] 거점 검색 트렌드를 콘텐츠 컨텍스트에 합류 — gold/{거점}/program_content_context.

## 왜 필요한가 — 안전장치가 꺼져 있었다

`ha_guard._check_trend` 는 컨텍스트에 실린 방향 라벨(상승/하락/보합)로 "트렌드가 하락인데
유입이 늘고 있다"는 생성물을 잡아 **폐기**한다. 2026-08-01 실사고가 이 검사의 이유다 —
입력이 하락인데 생성 카피가 "신사동을 찾는 발걸음이 다시 늘고 있는 요즘"이라고 썼다.

그런데 라벨이 없으면 검사는 조용히 통과한다(`if not labels: return []`). trend 행이
garosugil 한 곳에만 있었으므로 **53거점에서 이 검사가 꺼져 있었다.** Program 의 대상이
공실 창업 기업으로 바뀌며 생성량이 늘 자리라, 켜는 것이 먼저다.

## 방향은 서버가 계산한다

원시 수치를 프롬프트에 그대로 실으면 LLM 이 해석을 틀린다(위 실사고). 그래서 이 파일은
**시계열만** 싣고, 방향 판정은 `services/marketing._trend_summary` 가 한다 —
최근 3개월 평균 vs 직전 3개월 평균, ±5% 안이면 보합, 6점 미만이면 방향을 만들지 않는다.

## garosugil 은 건드리지 않는다

전용 Bronze(키워드 2그룹: 가로수길·신사동)로 만들어진 PoC 산출물이고 이미 라벨이 있다.
저장소 규칙(덮어쓰기 금지)을 따르며, 그래서 garosugil 만 2그룹이고 나머지는 1그룹이다.

실행: python -m data.pipelines.build_program_trend
      python -m data.pipelines.build_program_trend --dry-run
"""
from __future__ import annotations

import csv
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLD = ROOT / "data" / "gold"
KIND = "trend"

# 전용 Bronze 로 만들어진 PoC 산출물 — 위 주석 참조.
PRESERVE = {"garosugil"}


def _load_bronze() -> dict[str, list[dict]]:
    from data.collectors.common import load_latest
    from data.config.platform_districts import SLUG as SLUG13

    raw = load_latest(SLUG13, "naver_datalab_hub_trend.json")
    if not raw:
        print("[trend] Bronze 없음 — python -m data.collectors.naver_datalab --hubs 먼저")
        return {}
    return raw.get("trends") or {}


def _drop_partial(points: list[dict]) -> list[dict]:
    """끝나지 않은 이번 달 버킷을 잘라낸다.

    수집기가 endDate 를 지난달 말일로 두므로 보통은 걸릴 것이 없다. 그래도 지운다 —
    이 저장소는 절단값을 그대로 실어 트렌드를 오독한 전례가 있고(2026-08-01),
    수집기를 누가 손대면 조용히 되살아나는 종류의 결함이다.
    """
    now = datetime.date.today()
    partial = f"{now.year:04d}-{now.month:02d}"
    return [p for p in points if not str(p.get("period", "")).startswith(partial)]


def _merge_csv(path: Path, new_rows: list[tuple[str, str, float]]) -> None:
    """기존 CSV 의 trend 행만 갈아끼운다(멱등). 다른 kind 는 보존한다."""
    kept: list[tuple[str, str, str]] = []
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("kind") or "").startswith(KIND):
                    continue
                kept.append((r["kind"], r["key"], r["value"]))

    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "key", "value"])
        w.writerows(kept)
        w.writerows(new_rows)


def run(dry: bool = False) -> None:
    from data.config.page_hubs import HUBS

    trends = _load_bronze()
    if not trends:
        return

    written = skipped = thin = 0
    for slug, points in sorted(trends.items()):
        if slug in PRESERVE:
            skipped += 1
            continue
        path = GOLD / slug / "program_content_context.csv"
        if not path.exists():
            skipped += 1
            continue

        pts = _drop_partial(points)
        if len(pts) < 6:
            # _trend_summary 가 6점 미만이면 방향을 만들지 않는다 — 근거 없는 방향을
            # 주느니 라벨을 빼는 게 낫다. 여기서도 같은 기준으로 아예 싣지 않는다.
            thin += 1
            continue

        name = HUBS[slug].name if slug in HUBS else slug
        rows = [(f"{KIND}:{name}", p["period"], round(float(p["ratio"]), 5)) for p in pts]
        if dry:
            v = [float(p["ratio"]) for p in pts][-6:]
            prior, recent = sum(v[:3]) / 3, sum(v[3:]) / 3
            ch = (recent - prior) / prior * 100 if prior > 0 else 0.0
            lab = "보합" if abs(ch) < 5 else ("상승" if ch > 0 else "하락")
            print(f"  {slug:<18} {name:<18} {lab} ({prior:.3f}→{recent:.3f}, {ch:+.1f}%)")
        else:
            _merge_csv(path, rows)
        written += 1

    head = "[trend:dry]" if dry else "[trend]"
    note = f" · 보존·미보유 {skipped}" if skipped else ""
    note += f" · 점 부족 {thin}" if thin else ""
    print(f"{head} {written}개 거점 {'미리보기' if dry else '갱신'}{note}")


if __name__ == "__main__":
    run(dry="--dry-run" in sys.argv)
