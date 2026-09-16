"""API 응답시간 계측 — KPI② 를 재는 원천.

## 왜 필요한가

CLAUDE.md 는 오래 `API p95 <200ms` 를 성능 목표로 적어 왔는데, 2026-09-16 에 세어
보니 **저장소 전체에 측정 코드가 0줄**이었다(`core/security.py` 주석 한 줄이 목표를
언급할 뿐). 넘고 있는지 못 넘고 있는지가 아니라 **잰 적이 없는 것**이었다.

KPI 규칙 4 가 여기서 나왔다 — *계측기 없는 목표는 KPI 가 아니다*. 이 모듈이 그
0번 조건을 채운다. 값을 좋게 만드는 장치가 아니라 **값을 존재하게 하는 장치**다.

## 설계 — 셋 다 의도적으로 작다

- **메모리 링버퍼.** DB 도 외부 APM 도 쓰지 않는다. 분석 API 는 DB 를 안 타는
  경로가 많은데(`usage.record_access` 가 익명 요청에 DB 를 안 건드리는 것과 같은
  이유) 계측 때문에 매 요청 DB 를 때리면 재려던 지연을 계측기가 만들어낸다.
- **경로 템플릿으로 묶는다.** `/api/v1/buildings/{id}` 처럼 라우트 패턴을 키로 쓴다.
  실제 URL 을 키로 쓰면 카디널리티가 터져 링버퍼가 의미를 잃는다.
- **`/api/` 만 센다.** 정적 파일·프론트 서빙은 이 KPI 의 대상이 아니다.

## 읽을 때 반드시 아는 것 (한계)

1. **프로세스 로컬이다.** 재시작하면 0 이고, Cloud Run 이 인스턴스를 여럿 띄우면
   인스턴스마다 다른 표본이다. 즉 여기 p95 는 **전역 p95 가 아니라 이 인스턴스의
   표본 p95** 다. 응답이 `scope: "process"` 로 그걸 밝힌다.
2. **표본이 적으면 판정하지 않는다.** n=3 에서 나온 p95 는 최댓값과 다르지 않다.
   `MIN_SAMPLES` 미만이면 `verdict: "표본부족"` 으로 물러난다 — KPI 규칙 2
   (불확실성 없이 '달성'이라 적지 않는다)를 계측기 안에 박아 둔 것이다.
3. **서버 처리시간만 잰다.** 네트워크·클라이언트 렌더링은 안 들어간다. 사용자가
   체감하는 시간은 이보다 길다.
"""
from __future__ import annotations

import math
import threading
from collections import deque
from statistics import median

# 경로당 보관하는 최근 표본 수. 512 × 경로 200개 ≈ 10만 float 로 메모리는 무시할 수준.
WINDOW = 512
# 이 수 미만이면 p95 를 판정에 쓰지 않는다 — 표본이 적으면 p95 는 최댓값과 같아진다.
MIN_SAMPLES = 100
# 카디널리티 방어. 라우트 템플릿이라 정상 상태에서는 한참 못 미친다.
MAX_ROUTES = 200
# KPI② 목표. 바꾸려면 CLAUDE.md §KPI Priorities 와 함께 바꾼다.
TARGET_MS = 200.0

_lock = threading.Lock()
_samples: dict[str, deque[float]] = {}


def record(route: str, duration_ms: float) -> None:
    """요청 1건의 서버 처리시간(ms)을 남긴다. 실패해도 요청을 깨뜨리지 않는다."""
    with _lock:
        buf = _samples.get(route)
        if buf is None:
            if len(_samples) >= MAX_ROUTES:
                return          # 조용히 버린다 — 계측이 서비스를 해치지 않는다
            buf = _samples[route] = deque(maxlen=WINDOW)
        buf.append(float(duration_ms))


def reset() -> None:
    """테스트용. 운영 경로에서는 부르지 않는다."""
    with _lock:
        _samples.clear()


def _percentile(values: list[float], q: float) -> float:
    """최근접 순위법 — 순위 = ceil(q × n). 보간하지 않는다.

    보간하면 **표본에 없던 값**이 나온다. 표본이 작을수록 그 값이 실제 관측을 벗어나므로,
    없는 정밀도를 만드느니 관측된 값 하나를 그대로 돌려준다.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), math.ceil(q * len(ordered))))
    return ordered[rank - 1]


def _verdict(n: int, p95: float) -> str:
    if n < MIN_SAMPLES:
        return "표본부족"
    return "충족" if p95 < TARGET_MS else "미달"


def summary() -> dict:
    """경로별 + 전체 지연 요약. 읽기만 한다."""
    with _lock:
        snapshot = {route: list(buf) for route, buf in _samples.items()}

    routes = []
    for route, vals in snapshot.items():
        p95 = _percentile(vals, 0.95)
        routes.append({
            "route": route,
            "n": len(vals),
            "p50_ms": round(median(vals), 1),
            "p95_ms": round(p95, 1),
            "p99_ms": round(_percentile(vals, 0.99), 1),
            "max_ms": round(max(vals), 1),
            "verdict": _verdict(len(vals), p95),
        })
    routes.sort(key=lambda r: -r["p95_ms"])

    allv = [v for vals in snapshot.values() for v in vals]
    overall_p95 = _percentile(allv, 0.95)
    return {
        "target_ms": TARGET_MS,
        "min_samples": MIN_SAMPLES,
        "window_per_route": WINDOW,
        # 이 값이 전역이 아니라는 사실을 응답에 박아 둔다 — 떼면 오독된다.
        "scope": "process",
        "note": ("프로세스 로컬 표본이다. 재시작하면 0 이고 인스턴스가 여럿이면 "
                 "인스턴스마다 다르다 — 전역 p95 가 아니다. 서버 처리시간만 재며 "
                 "네트워크·렌더링은 포함하지 않는다."),
        "overall": {
            "n": len(allv),
            "p50_ms": round(median(allv), 1) if allv else 0.0,
            "p95_ms": round(overall_p95, 1),
            "verdict": _verdict(len(allv), overall_p95),
        },
        "routes": routes,
    }
