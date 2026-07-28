"""로드뷰 라벨 채점 — PoC exit 판정 (poc §5: status 정확도 70%+).

roadview_sample.csv 의 label_actual 이 채워지면 실행한다.

판정 규칙 (라벨 → 허용 예측 status):
  공실     → empty, high
  부분공실 → partial, high
  영업     → full, partial
  불명     → 채점 제외

출력: 전체 정확도, 공실 탐지 precision/recall, 혼동 행렬.

**기본은 현재 파이프라인 산출물(gold/garosugil/page_building_master.geojson)을 pnu 로
조인해 채점한다**(2026-07-28). 예전에는 CSV 에 박제된 `status_predicted` 열만 읽었는데,
그건 2026-07-19 시점 예측이라 이후 어떤 변경을 해도 점수가 움직이지 않았다 — 즉 회귀를
탐지할 수 없는 지표였다. 박제 열 기준 점수가 필요하면 --frozen 으로 볼 수 있다.

실행:
  python -m data.validation.score_labels             # 현행 파이프라인 채점
  python -m data.validation.score_labels --frozen    # CSV 박제 예측 채점(과거 비교용)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

# Windows 콘솔(cp949) 특수문자 출력 크래시 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_CSV = Path(__file__).resolve().parent / "roadview_sample.csv"
_MASTER = (Path(__file__).resolve().parents[1] / "gold" / "garosugil"
           / "page_building_master.geojson")

_ALLOWED = {
    "공실": {"empty", "high"},
    "부분공실": {"partial", "high"},
    "영업": {"full", "partial"},
}


def _live_status() -> dict[str, str]:
    """현행 산출물의 {pnu: status} — 라벨 CSV 의 id 앞 19자리와 조인한다."""
    if not _MASTER.exists():
        return {}
    fc = json.loads(_MASTER.read_text(encoding="utf-8"))
    return {f["properties"]["pnu"]: f["properties"]["status"] for f in fc["features"]}


def run(frozen: bool = False) -> None:
    rows = list(csv.DictReader(_CSV.open(encoding="utf-8-sig")))
    live = {} if frozen else _live_status()
    if not frozen and not live:
        print(f"[score] {_MASTER.name} 없음 — build_page_master 를 먼저 실행하세요")
        return

    def pred(r: dict) -> str | None:
        return r["status_predicted"] if frozen else live.get(r["id"].split("-")[0])

    labeled = [r for r in rows
               if r["label_actual"].strip() in _ALLOWED and pred(r) is not None]
    skipped = len(rows) - len(labeled)
    if not labeled:
        print("[score] label_actual 이 비어 있음 — roadview_sample.csv 를 먼저 채우세요")
        return

    correct = sum(1 for r in labeled if pred(r) in _ALLOWED[r["label_actual"].strip()])
    acc = round(correct / len(labeled) * 100, 1)

    # 공실 탐지(empty 예측)의 precision / recall
    pred_empty = [r for r in labeled if pred(r) == "empty"]
    actual_empty = [r for r in labeled if r["label_actual"].strip() == "공실"]
    tp = sum(1 for r in pred_empty if r["label_actual"].strip() == "공실")
    prec = round(tp / len(pred_empty) * 100, 1) if pred_empty else None
    rec = round(tp / len(actual_empty) * 100, 1) if actual_empty else None

    conf = Counter((r["label_actual"].strip(), pred(r)) for r in labeled)

    src = "CSV 박제(2026-07-19)" if frozen else "현행 page_building_master"
    print(f"[score] 채점 {len(labeled)}동 (불명/미매칭 제외 {skipped}) · 예측 출처: {src}")
    print(f"[score] status 정확도: {acc}%  → PoC exit 기준 70% {'통과 ✅' if acc >= 70 else '미달 ❌'}")
    print(f"[score] 공실(empty) precision {prec}% / recall {rec}%")
    print("[score] 혼동(실제라벨 → 예측):")
    for (actual, p), n in sorted(conf.items()):
        print(f"    {actual} → {p}: {n}")


if __name__ == "__main__":
    run(frozen="--frozen" in sys.argv[1:])
