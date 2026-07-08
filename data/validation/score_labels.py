"""로드뷰 라벨 채점 — PoC exit 판정 (poc §5: status 정확도 70%+).

roadview_sample.csv 의 label_actual 이 채워지면 실행한다.

판정 규칙 (라벨 → 허용 예측 status):
  공실     → empty, high
  부분공실 → partial, high
  영업     → full, partial
  불명     → 채점 제외

출력: 전체 정확도, 공실 탐지 precision/recall, 혼동 행렬.

실행: python -m data.validation.score_labels
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

# Windows 콘솔(cp949) 특수문자 출력 크래시 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_CSV = Path(__file__).resolve().parent / "roadview_sample.csv"

_ALLOWED = {
    "공실": {"empty", "high"},
    "부분공실": {"partial", "high"},
    "영업": {"full", "partial"},
}


def run() -> None:
    rows = list(csv.DictReader(_CSV.open(encoding="utf-8-sig")))
    labeled = [r for r in rows if r["label_actual"].strip() in _ALLOWED]
    skipped = len(rows) - len(labeled)
    if not labeled:
        print("[score] label_actual 이 비어 있음 — roadview_sample.csv 를 먼저 채우세요")
        return

    correct = sum(1 for r in labeled
                  if r["status_predicted"] in _ALLOWED[r["label_actual"].strip()])
    acc = round(correct / len(labeled) * 100, 1)

    # 공실 탐지(empty 예측)의 precision / recall
    pred_empty = [r for r in labeled if r["status_predicted"] == "empty"]
    actual_empty = [r for r in labeled if r["label_actual"].strip() == "공실"]
    tp = sum(1 for r in pred_empty if r["label_actual"].strip() == "공실")
    prec = round(tp / len(pred_empty) * 100, 1) if pred_empty else None
    rec = round(tp / len(actual_empty) * 100, 1) if actual_empty else None

    conf = Counter((r["label_actual"].strip(), r["status_predicted"]) for r in labeled)

    print(f"[score] 채점 {len(labeled)}동 (불명/미기입 제외 {skipped})")
    print(f"[score] status 정확도: {acc}%  → PoC exit 기준 70% {'통과 ✅' if acc >= 70 else '미달 ❌'}")
    print(f"[score] 공실(empty) precision {prec}% / recall {rec}%")
    print("[score] 혼동(실제라벨 → 예측):")
    for (actual, pred), n in sorted(conf.items()):
        print(f"    {actual} → {pred}: {n}")


if __name__ == "__main__":
    run()
