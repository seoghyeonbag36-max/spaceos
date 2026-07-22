"""Platform 분기 갱신 파이프라인 — 수집→Gold→학습→검증을 한 번에 (분기 1회 실행).

새 분기 데이터 공표 시점(대략 분기 종료 + 2~3개월) 후 실행하면 forecast 가 갱신된다.
배포는 git push(main = Vercel 자동 배포)로 이어지며, 이 스크립트는 로컬 산출물까지만.

실행: python -m data.pipelines.refresh_platform            # 전체 (약 30~40분)
      python -m data.pipelines.refresh_platform --skip-collect  # 수집 생략(빌드·학습만)

주의: data/config/platform_districts.py 의 QUARTERS 에 새 분기를 추가한 뒤 실행할 것.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

# 출력을 파이프로 받을 때 Windows 기본 cp949 로는 로그의 '—'·이모지에서 죽는다.
# 자신과 하위 프로세스 모두 UTF-8 로 고정해 인코딩 크래시를 오탐(실패)으로 만들지 않는다.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass
_CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}

# (표시명, 모듈 argv, 실패 시 중단 여부) — 수집 단계는 실패해도 다음으로 진행(기존 bronze 재사용)
_STEPS: list[tuple[str, list[str], bool]] = [
    ("상권 시계열(stor/selng/relm)", ["data.collectors.seoul_trdar", "--platform13"], False),
    ("길단위인구", ["data.collectors.seoul_trdar", "--platform13-flpop"], False),
    ("상권변화지표", ["data.collectors.seoul_trdar", "--platform13-income-ix"], False),
    ("R-ONE 공실률·임대료", ["data.collectors.rone_rent"], False),
    ("점포(카카오)", ["data.collectors.kakao_local", "--platform13"], False),
    ("블로그 리뷰", ["data.collectors.naver_blog", "--platform13"], False),
    ("Gold 빌드(platform13 한정)", ["data.pipelines.build_gold", "--platform13"], True),
    ("GNN 엣지 빌드", ["data.pipelines.build_store_graph_edges", "--platform13"], True),
    ("LSTM 재학습 + forecast", ["ml.training.train_lstm"], True),
]

_COLLECT_STEPS = 6  # 앞 6단계가 수집


def run(skip_collect: bool = False) -> int:
    steps = _STEPS[_COLLECT_STEPS:] if skip_collect else _STEPS
    failed: list[str] = []
    for name, argv, critical in steps:
        print(f"\n━━ {name} ({argv[0]}) ━━")
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", *argv], env=_CHILD_ENV)
        dt = time.time() - t0
        if r.returncode != 0:
            failed.append(name)
            print(f"[refresh] {name} 실패 (exit {r.returncode}, {dt:.0f}s)")
            if critical:
                print("[refresh] 필수 단계 실패 — 중단")
                return 1
        else:
            print(f"[refresh] {name} 완료 ({dt:.0f}s)")

    print("\n━━ 마무리 ━━")
    if failed:
        print(f"[refresh] 실패 단계(비필수): {failed} — 기존 bronze 로 진행됨")
    print("[refresh] 완료. 다음 수순: cd apps/backend && pytest → git add/commit → git push(배포)")
    return 0


if __name__ == "__main__":
    sys.exit(run(skip_collect="--skip-collect" in sys.argv))
