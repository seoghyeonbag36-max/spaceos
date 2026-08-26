"""[Page/Posting] **집계구** 단위 생활인구 수집기 — 유닛 단위 `foot` 의 재료 (막힘 5).

## 왜 새 수집기인가

- `living_population.py`     구(區) 단위 25구 상대점수 — 시간 축 없음
- `living_population_hourly.py` **행정동** × 24시간 (OpenAPI `SPOP_LOCAL_RESD_DONG`)
- **이 파일**                 **집계구** × 24시간 — 행정동보다 한 단계 아래

집계구는 서울 19,038개로, 54거점 528유닛이 **326개 (거점,집계구) 쌍**으로 갈린다
(상권 기준 중앙 3개 → 집계구 중앙 6개, 2배 입도). 유닛 사이 서열을 만들 수 있는
가장 세밀한 공개 자료다.

## ⚠ OpenAPI 가 없다 — ZIP 이 유일한 경로다

행정동판과 달리 집계구판은 OpenAPI 서비스명 4종(`_TOT`·`_JIPGYE`·`_ADSTRD`·`_RESD`)이
전부 `ERROR-500` 이다(2026-08-25 프로브, docs/prep-sgis-application.md). 배포 단위는
**월별 ZIP**(`LOCAL_PEOPLE_YYYYMM.zip`, 2026-07 기준 **1.28GB**)이고 그 안에 **일별 CSV
31개**가 들어 있다.

**전량을 받지 않는다.** 응답을 스트리밍하면서 `zlib.decompressobj(-15)` 로 멤버를 하나씩
증분 해제하고, 필요한 날짜 수만큼 읽은 뒤 연결을 끊는다. 하루치가 40MB 안팎이라
7일이면 1.28GB 중 ~290MB 만 받는다.

## ⚠ 이 계열은 2026-07-31 로 생산이 끝났다

국가표준격자(250m) 전환 때문이다. 후속(OA-23019~22)은 이름만 250m 이고 행은 **자치구
단위**라 더 거칠다. 즉 집계구가 여전히 가장 세밀하고, 파일은 계속 내려받히지만
**갱신은 없다.** 여기서 나오는 `foot` 은 2017-01~2026-07 구간의 **대표값**이며,
산출물에 그렇게 밝혀야 한다.

## 어느 집계구를 남기나

배정표(`silver/*_jipgyegu.json`)에 있는 코드만 남긴다. 배정표가 없으면 실행을
거부한다 — 전량을 받아 놓고 나중에 못 붙이는 것이 최악이다(행정동판과 같은 원칙).

⚠ **2026-08-26 에 대상이 세 배로 넓어졌다.** 종전에는 유닛 배정표(집계구 293곳)만
봤는데, 그 keep-list 로는 Platform GNN 노드의 **43.5%** · Page 격자 셀의 **88.4%**
밖에 못 덮는다. 대상이 셋이므로 배정표도 셋이고 `target_codes()` 가 합집합을 쓴다
(→ **1,501곳**, 19,153 중 7.8%). 넓혀도 **내려받는 양은 그대로**다 — 필터는 해제
후에 걸리고 ZIP 스트리밍 구간은 안 바뀐다.

실행:
  python -m data.collectors.living_population_jipgyegu --month 202607 --days 7
  python -m data.collectors.living_population_jipgyegu --month 202604 --days 1
"""
from __future__ import annotations

import argparse
import json
import struct
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

from data.collectors.common import BRONZE, DATA_ROOT

_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
_INF_ID = "OA-14979"
_SILVER = DATA_ROOT / "silver" / "unit_jipgyegu.json"
_NODE_SILVER = DATA_ROOT / "silver" / "node_jipgyegu.json"
_CELL_SILVER = DATA_ROOT / "silver" / "cell_jipgyegu.json"
_OUT_DIR = BRONZE / "seoul"

# CSV 열 이름 — 2026-07 실측 (33열)
_C_DATE, _C_HOUR, _C_ADONG, _C_OA, _C_TOT = (
    "기준일ID", "시간대구분", "행정동코드", "집계구코드", "총생활인구수")


def target_codes() -> set[str]:
    """배정표에 있는 집계구 코드만 — 없으면 실행을 거부한다.

    **세 표의 합집합**이다. 대상이 셋이기 때문이다:

    - `unit_jipgyegu`  공실 유닛 528호 → 집계구 **293**곳 (Posting `foot` 서열)
    - `node_jipgyegu`  점포 노드 40,388개 → 집계구 **1,155**곳 (Platform GNN 피처)
    - `cell_jipgyegu`  100m 격자 셀 3,699개 → 집계구 **1,303**곳 (Page 유동·밀도 레이어)

    노드·셀 표는 2026-08-26 프로브가 요구한 것이다: 노드 PIP 는 **100%** 성공하는데
    생활인구 프로필은 43.5% 만 있었고, 그 차이가 전부 여기 keep-list 가 좁아서
    생겼다(셀은 88.4%). ZIP 을 스트리밍하며 증분 해제하므로 **내려받는 양은 넓혀도
    그대로**이고(~290MB/7일), 늘어나는 저장은 1,501/19,153 = **7.8%** 다 — 원래의
    금지 사유("전량을 받아 놓고 나중에 못 붙인다")에 걸리지 않는다.

    노드·셀 표는 **없어도 된다** — 있으면 넓히고, 없으면 종전대로 유닛만 받는다.
    """
    if not _SILVER.exists():
        raise FileNotFoundError(
            f"{_SILVER} 없음 — `python -m data.pipelines.build_unit_jipgyegu` 를 먼저 실행할 것. "
            f"배정표 없이 전량을 받으면 60배를 저장하고도 유닛에 못 붙인다")
    doc = json.loads(_SILVER.read_text(encoding="utf-8"))
    codes = {v["oa_code"] for v in doc["units"].values()}
    for extra in (_NODE_SILVER, _CELL_SILVER):
        if extra.exists():
            codes |= set(json.loads(extra.read_text(encoding="utf-8")).get("oa_codes") or [])
    return codes


def _open_zip(month: str):
    body = urllib.parse.urlencode(
        {"infId": _INF_ID, "seqNo": "", "seq": month[2:], "infSeq": "1"}).encode()
    req = urllib.request.Request(_URL, data=body, headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"https://data.seoul.go.kr/dataList/{_INF_ID}/S/1/datasetView.do"})
    return urllib.request.urlopen(req, timeout=600)


def _members(resp, days: int):
    """ZIP 응답을 스트리밍하며 앞에서부터 `days` 개 멤버를 (이름, 텍스트조각) 으로 흘린다.

    전량 다운로드를 피하는 것이 요점이다. 멤버 하나가 끝나면 `unused_data` 에서
    다음 로컬헤더(`PK\x03\x04`)를 찾아 이어간다 — 스트리밍 ZIP 은 압축데이터 뒤에
    data descriptor 가 붙을 수 있어 시그니처로 찾는 편이 안전하다.
    """
    buf = b""
    done = 0
    total = 0
    while done < days:
        while len(buf) < 4096:
            c = resp.read(1 << 16)
            if not c:
                return
            total += len(c)
            buf += c
        if buf[:4] != b"PK\x03\x04":
            i = buf.find(b"PK\x03\x04")
            if i < 0:
                buf = buf[-4:]
                continue
            buf = buf[i:]
            continue
        n_name, n_extra = struct.unpack("<HH", buf[26:30])
        while len(buf) < 30 + n_name + n_extra:
            c = resp.read(1 << 16)
            if not c:
                return
            total += len(c)
            buf += c
        name = buf[30:30 + n_name].decode("cp437")
        buf = buf[30 + n_name + n_extra:]

        d = zlib.decompressobj(-15)
        tail = b""
        while True:
            if buf:
                out = d.decompress(buf)
                buf = b""
            else:
                c = resp.read(1 << 18)
                if not c:
                    return
                total += len(c)
                out = d.decompress(c)
            if out:
                tail += out
                # 줄 경계까지만 넘긴다
                cut = tail.rfind(b"\n")
                if cut >= 0:
                    yield name, tail[:cut + 1]
                    tail = tail[cut + 1:]
            if d.eof:
                if tail:
                    yield name, tail
                buf = d.unused_data
                done += 1
                print(f"  [{done}/{days}] {name} · 누적 {total/1e6:.0f}MB")
                break


def collect_month(month: str, days: int, codes: set[str]) -> dict[str, int]:
    """월 ZIP 의 앞 `days` **개 멤버**를 받아 날짜별 bronze 파일로 떨군다.

    ⚠ 멤버 순서는 날짜 오름차순이 아니다(2026-04 첫 멤버 = 20260428).
    특정 날짜가 필요하면 그 날짜가 나올 때까지 받아야 하므로, 지금은
    "앞에서 N개"만 지원하고 받아진 날짜를 산출물 경로로 드러낸다.
    """
    written: dict[str, int] = {}
    header: list[str] | None = None
    idx: dict[str, int] = {}
    cur_name = None
    rows: list[dict] = []

    def flush(nm: str) -> None:
        if not nm or not rows:
            return
        ymd = "".join(ch for ch in nm if ch.isdigit())[-8:]
        d = _OUT_DIR / f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
        d.mkdir(parents=True, exist_ok=True)
        p = d / "living_population_jipgyegu.json"
        p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        written[ymd] = len(rows)
        print(f"      → {p.relative_to(DATA_ROOT)} ({len(rows)}행)")
        rows.clear()

    resp = _open_zip(month)
    try:
        pending = ""
        for name, chunk in _members(resp, days):
            if name != cur_name:
                flush(cur_name)
                cur_name, pending = name, ""
            text = pending + chunk.decode("cp949", "replace")
            lines = text.split("\n")
            pending = lines.pop()
            for ln in lines:
                ln = ln.strip().strip("\ufeff")
                if not ln:
                    continue
                f = [x.strip().strip('"').strip() for x in ln.split(",")]
                # 헤더 판정은 **열 이름 포함 여부**로 한다. 첫 칸 일치로 보면 깨진다 —
                # 월마다 선두 바이트가 다르다(2026-04 는 헤더 앞에 '?' 가 붙어 있고
                # 2026-07 은 없다). 파일별 잡티를 규칙으로 흡수한다.
                if any(_C_OA in c for c in f):
                    header = f
                    idx = {}
                    for key in (_C_DATE, _C_HOUR, _C_ADONG, _C_OA, _C_TOT):
                        idx[key] = next(i for i, c in enumerate(f) if key in c)
                    continue
                if not idx:
                    continue        # 헤더를 아직 못 봤다 — 선두 잡음 줄
                oa = f[idx[_C_OA]]
                if oa not in codes:
                    continue
                rows.append({"date": f[idx[_C_DATE]], "hour": int(f[idx[_C_HOUR]]),
                             "adong": f[idx[_C_ADONG]], "oa": oa,
                             "pop": float(f[idx[_C_TOT]]) if f[idx[_C_TOT]] not in ("", "*") else None})
        flush(cur_name)
    finally:
        resp.close()
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True, help="YYYYMM (예 202607)")
    ap.add_argument("--days", type=int, default=1,
                    help="ZIP 앞에서부터 **멤버 몇 개** (기본 1). ⚠ 멤버 순서는 "
                         "날짜순이 아니다 — 2026-04 의 첫 멤버는 20260428 이다. "
                         "받아진 날짜는 실행 로그와 파일 경로로 확인할 것")
    a = ap.parse_args()
    codes = target_codes()
    print(f"[집계구 생활인구] {a.month} 앞 {a.days}일 · 대상 집계구 {len(codes)}개")
    w = collect_month(a.month, a.days, codes)
    print(f"완료: {len(w)}일 · " + " ".join(f"{k}({v})" for k, v in sorted(w.items())))


if __name__ == "__main__":
    main()
