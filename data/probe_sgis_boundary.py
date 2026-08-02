"""SGIS 자료신청분(집계구·행정동 경계) 도착 즉시 판정하는 점검기.

받은 shapefile 이 실제로 쓸 수 있는 물건인지 세 가지를 확인한다.
셋 중 하나라도 어긋나면 그 자리에서 멈춰야 한다 — 변환·배정을 다 해 놓고
나중에 발견하면 그때까지 만든 게 전부 버려진다.

  1. 좌표계(.prj)   — SGIS 는 보통 UTM-K(EPSG:5179). 상권 좌표계(5181)와 다르다
  2. 집계구 코드    — 서울 생활인구가 쓰는 2016 기준은 **13자리**다. 자릿수가 다르면 조인 불가
  3. 서울 범위      — 표본 폴리곤 중심이 실제 서울 안에 떨어지는지(투영 오판 감지)

geopandas 를 쓰지 않는다 — 폴리곤 읽기 + 투영이 전부라 GDAL 이 불필요하다.

실행:
    python -m data.probe_sgis_boundary <shp 경로 또는 폴더>
    python -m data.probe_sgis_boundary data/bronze/seoul/2026-08-02/jipgyegu_2016
"""
from __future__ import annotations

import sys
from pathlib import Path

import shapefile  # pyshp
from pyproj import CRS, Transformer

# 서울 대략 경계 — 투영이 틀리면 여기를 벗어난다
SEOUL_BBOX = (126.76, 37.42, 127.19, 37.70)  # lng_min, lat_min, lng_max, lat_max


def _find_shp(target: Path) -> list[Path]:
    if target.is_file() and target.suffix.lower() == ".shp":
        return [target]
    return sorted(target.rglob("*.shp"))


def _read_prj(shp: Path) -> tuple[CRS | None, str]:
    prj = shp.with_suffix(".prj")
    if not prj.exists():
        return None, "(.prj 없음 — 좌표계 판정 불가)"
    wkt = prj.read_text(encoding="utf-8", errors="replace").strip()
    try:
        crs = CRS.from_wkt(wkt)
        epsg = crs.to_epsg()
        return crs, f"{crs.name} (EPSG:{epsg})" if epsg else f"{crs.name} (EPSG 미지정)"
    except Exception as exc:
        return None, f"(.prj 해석 실패: {exc})"


def _centroid(shape) -> tuple[float, float]:
    pts = shape.points
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def probe(shp: Path) -> None:
    print(f"\n{'=' * 70}\n{shp}")

    # 동반 파일 — 하나라도 없으면 읽히지 않는다
    missing = [e for e in (".shx", ".dbf") if not shp.with_suffix(e).exists()]
    if missing:
        print(f"  [X] 동반 파일 누락: {missing} — ZIP 을 통째로 풀었는지 확인")
        return

    crs, crs_desc = _read_prj(shp)
    print(f"  좌표계: {crs_desc}")

    # 한글 속성은 cp949 가 보통. utf-8 로 실패하면 되돌린다
    for enc in ("utf-8", "cp949"):
        try:
            r = shapefile.Reader(str(shp), encoding=enc)
            fields = [f[0] for f in r.fields[1:]]
            recs = r.shapeRecords()
            break
        except Exception:
            continue
    else:
        print("  [X] 읽기 실패 (cp949 · utf-8 모두)")
        return

    print(f"  인코딩: {enc} | 피처: {len(recs):,}개 | 필드: {fields}")
    if not recs:
        print("  [X] 피처 0건")
        return

    rec0 = recs[0].record
    print(f"  샘플 속성: {dict(zip(fields, list(rec0)))}")

    # 집계구 코드 자릿수 — 2016 기준이면 13자리
    for fname, val in zip(fields, list(rec0)):
        s = str(val).strip()
        if s.isdigit() and len(s) >= 7:
            mark = "  <- 13자리(2016 집계구 기준과 일치)" if len(s) == 13 else ""
            print(f"  코드 후보 {fname}: {s} ({len(s)}자리){mark}")

    # 투영 검증 — 표본 중심이 서울 안에 떨어지는가
    if crs is None:
        print("  [!] 좌표계 불명이라 범위 검증 생략")
        return
    t = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    inside = 0
    sample = recs[:: max(1, len(recs) // 50)][:50]
    for sr in sample:
        if not sr.shape.points:
            continue
        x, y = _centroid(sr.shape)
        lng, lat = t.transform(x, y)
        if SEOUL_BBOX[0] <= lng <= SEOUL_BBOX[2] and SEOUL_BBOX[1] <= lat <= SEOUL_BBOX[3]:
            inside += 1
    x, y = _centroid(sample[0].shape)
    lng, lat = t.transform(x, y)
    print(f"  표본 첫 폴리곤 중심 -> lat={lat:.5f}, lng={lng:.5f}")
    print(f"  서울 범위 안: {inside}/{len(sample)}")
    if inside == 0:
        print("  [X] 전부 서울 밖 — 좌표계 오판이거나 전국분에서 서울을 못 찾은 것")
    elif inside < len(sample) * 0.5:
        print("  [!] 절반 미만 — 전국 자료일 가능성(서울만 잘라내야 함)")
    else:
        print("  [OK] 정상")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    target = Path(sys.argv[1])
    if not target.exists():
        raise SystemExit(f"경로 없음: {target}")
    shps = _find_shp(target)
    if not shps:
        raise SystemExit(f"shp 파일을 못 찾음: {target}")
    print(f"shp {len(shps)}개 발견")
    for shp in shps:
        probe(shp)


if __name__ == "__main__":
    main()
