"""[일회성 보정] 429로 강등된 건물을 로그에서 역추적해 rate_limited 로 표시.

배경(2026-07-26): building_vacancy 에 429 전용 처리가 들어가기 전 실행된 수집분은
레이트 리밋으로 대장을 못 받은 건물을 `no_ledger`(대장 원래 없음) 또는
`floor_approx`(전유부 유실 후 표제부 폴백)로 기록했다. 사실과 수집 실패가 구분되지
않아 재개 로직이 '완료'로 간주하고 영영 재시도하지 않는다.

다행히 실패 로그에 요청 URL 이 통째로 남아 지번(sigunguCd/bjdongCd/platGbCd/bun/ji)을
복원할 수 있다. 그 지번의 gold 행만 rate_limited 로 되돌리면 다음 building_vacancy
실행이 자동으로 재수집한다(_RETRY_METHODS).

대상 로그 라인(구/신 형식 모두):
  [HTTP 실패 3연속] getBrExposPubuseAreaInfo — 429 Client Error: ... for url: http://...
  [HTTP 실패 3연속 | 429 x12 · pace 0.75s] getBrTitleInfo — 429 Client Error: ...

안전장치: 수집 프로세스가 아직 돌고 있으면 거부한다. 체크포인트 저장이 이 스크립트의
수정분을 덮어쓰기 때문이다. --force 로 무시할 수 있으나 권장하지 않는다.

실행:
  python -m data.pipelines.repair_rate_limited --log data/logs/bldgvac-stdout.log
  python -m data.pipelines.repair_rate_limited --log ... --apply      # 실제 반영
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from data.collectors.common import GOLD

# 429 로 재시도가 소진된 라인 (구 형식 "[HTTP 실패 N연속]" / 신 형식 "... | 429 xN ...")
_FAIL_RE = re.compile(r"\[HTTP 실패 \d+연속[^\]]*\].*?429.*?for url:\s*(\S+)")
# 거점 전환 지점 — 이후의 실패 라인은 이 거점 소속
_HUB_RE = re.compile(r"\[bldg-vac:([a-z0-9-]+)\] 대장 대상")

_JIBUN_KEYS = ("sigunguCd", "bjdongCd", "platGbCd", "bun", "ji")

# 429 로 강등됐을 수 있는 method 만 되돌린다. expos_units 는 전유부를 실제로 받아낸
# 것이므로 같은 지번에 실패 라인이 있어도(다른 페이지·다른 호출) 건드리지 않는다.
_DOWNGRADED = {"no_ledger", "floor_approx", "non_commercial"}


def _key(d: dict) -> tuple:
    return tuple(str(d.get(k, "")) for k in _JIBUN_KEYS)


def parse_log(path: Path) -> dict[str, set[tuple]]:
    """로그 → {slug: {지번키, ...}}. 거점별로 429 소진된 지번을 모은다."""
    hits: dict[str, set[tuple]] = defaultdict(set)
    slug = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _HUB_RE.search(line)
        if m:
            slug = m.group(1)
            continue
        m = _FAIL_RE.search(line)
        if m and slug:
            qs = parse_qs(urlparse(m.group(1)).query)
            jibun = {k: (qs.get(k) or [""])[0] for k in _JIBUN_KEYS}
            if any(jibun.values()):
                hits[slug].add(_key(jibun))
    return hits


def _collector_running() -> tuple[bool, str]:
    """(차단해야 하나, 사유). **fail-closed** — 감지 자체가 실패하면 차단한다.

    처음엔 wmic 을 썼는데 Windows 11 에서 제거되어 조용히 '없음'을 반환했다(2026-07-26).
    감지 실패를 '안전'으로 해석하면 수집 중 보정이 통과해 체크포인트에 덮어써진다.
    """
    ps = ("Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" "
          "| Select-Object -ExpandProperty CommandLine")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return True, f"프로세스 감지 실패({exc}) — 안전을 위해 차단"
    if r.returncode != 0:
        return True, f"프로세스 감지 실패(exit {r.returncode}) — 안전을 위해 차단"
    for line in r.stdout.splitlines():
        if "building_vacancy" in line:
            return True, f"수집 프로세스 실행 중: {line.strip()[:110]}"
    return False, "수집 프로세스 없음"


def repair(slug: str, keys: set[tuple], apply: bool) -> dict:
    src = GOLD / slug / "building_vacancy.json"
    if not src.exists():
        return {"slug": slug, "skipped": "building_vacancy.json 없음"}
    rows = json.loads(src.read_text(encoding="utf-8"))

    before = Counter(r.get("capacity_method") for r in rows)
    touched, protected = [], Counter()
    for r in rows:
        if _key(r) not in keys:
            continue
        method = r.get("capacity_method")
        if method not in _DOWNGRADED:
            protected[method] += 1          # expos_units 등 — 실제로 받아낸 값은 보존
            continue
        touched.append({"bdMgtSn": r.get("bdMgtSn"), "lnoCd": r.get("lnoCd"),
                        "name": r.get("name"), "active": r.get("active"),
                        "was": method})
        r.update(capacity=None, capacity_method="rate_limited", occupancy=None,
                 vacancy_bldg=None, status="unknown")

    if apply and touched:
        src.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        (GOLD / slug / "rate_limited.json").write_text(json.dumps(
            {"slug": slug, "count": len(touched), "source": "repair_rate_limited(로그 역추적)",
             "note": "429로 대장을 못 받은 건물. 다음 building_vacancy 실행이 자동 재시도한다.",
             "buildings": touched}, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"slug": slug, "지번": len(keys), "복원": len(touched),
            "보존": dict(protected), "was": dict(Counter(t["was"] for t in touched)),
            "before": dict(before)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, help="수집 stdout 로그 경로")
    ap.add_argument("--apply", action="store_true", help="실제 반영 (기본은 dry-run)")
    ap.add_argument("--force", action="store_true", help="수집 프로세스 실행 중에도 강행")
    ap.add_argument("slugs", nargs="*", help="대상 거점 (기본: 로그에서 발견된 전부)")
    args = ap.parse_args()

    if args.apply and not args.force:
        blocked, why = _collector_running()
        if blocked:
            print(f"[repair] ⚠ 중단합니다 — {why}\n"
                  "         체크포인트 저장이 보정분을 덮어씁니다. 수집 종료 후 재실행하세요.\n"
                  "         (정말 강행하려면 --force)")
            return

    hits = parse_log(Path(args.log))
    if args.slugs:
        hits = {s: k for s, k in hits.items() if s in args.slugs}
    if not hits:
        print("[repair] 429 실패 라인 없음 — 보정할 것이 없습니다.")
        return

    mode = "APPLY" if args.apply else "DRY-RUN"
    for slug, keys in hits.items():
        r = repair(slug, keys, args.apply)
        if "skipped" in r:
            print(f"[repair:{slug}] 건너뜀 — {r['skipped']}")
            continue
        print(f"[repair:{slug}][{mode}] 429 지번 {r['지번']}개 → 복원 {r['복원']}동 "
              f"{r['was']} · 보존 {r['보존'] or '없음'}")
    if not args.apply:
        print("[repair] dry-run 이었습니다. 반영하려면 --apply 를 붙이세요.")


if __name__ == "__main__":
    main()
