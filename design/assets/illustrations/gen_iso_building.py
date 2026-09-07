#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""아이소메트릭 한국 도심 상가 건물 일러스트(SVG) 생성기.

사양
  - 4층 상가. 1F 영업 중(간판·조명·차양), 2~3F 공실(어두운 창 + 임대 현수막), 4F 정상 입주
  - 색: 배경면 #F4F7FB · 선 #1C2533 · 빈 층 강조 #0EA5B7 (design/tokens/tokens.json 의 bg/ink/brand.primary)
  - 평면적·미니멀, 그림자 없음, 캔버스 배경 투명, 텍스트·간판 글씨 없음, 정사각(800x800)

투영 = 정아이소메트릭(30도).
  sx = CX + (x - y) * cos30 * S
  sy = CY + (x + y) * 0.5 * S - z * S
  → 화면상 가까운 모서리는 (x=W, y=D). 보이는 면은 평면 y=D(우측면)·평면 x=W(좌측면)·윗면.
"""
from __future__ import annotations

import math
from pathlib import Path

K = math.cos(math.radians(30))

# ── 색 ────────────────────────────────────────────────────────────────
INK = "#1C2533"    # 선 · 어두운(공실) 창
BG = "#F4F7FB"     # 밝은 면
SHADE = "#E3EAF3"  # BG 파생 음영 톤 — 좌측면 구분용(아이소 면 분리에 필요한 유일한 파생색)
WHITE = "#FFFFFF"  # 가장 밝은 면(윗면) · 조명 켜진 유리
ACC = "#0EA5B7"    # 빈 층 강조

# ── 치수(world unit) ─────────────────────────────────────────────────
W, D = 7.5, 5.5          # 폭(x) · 깊이(y)
H1, HU = 3.1, 1.8        # 1층 층고 · 상층 층고
Z = [0.0, H1, H1 + HU, H1 + 2 * HU, H1 + 3 * HU]   # 층 경계 z: 0 / 3.1 / 4.9 / 6.7 / 8.5
H = Z[4]                 # 파라펫 상단
PAR = 0.32               # 파라펫 두께(윗면 인셋)
PO, PT = 0.62, 0.22      # 보도 슬래브 내밀기 · 두께
EMPTY_LO, EMPTY_HI = Z[1], Z[3]   # 공실 구간 2F~3F

ROOF_BOX = (0.9, 3.1, 0.9, 2.9, H, H + 0.95)       # 옥탑
ROOF_TANK = (4.3, 5.9, 1.1, 2.5, H, H + 0.72)      # 물탱크
ROOF_AC = [(1.25, 2.05, 3.6, 4.3, H, H + 0.36),    # 실외기 2대
           (2.65, 3.45, 3.6, 4.3, H, H + 0.36)]

CANVAS, PAD = 800.0, 52.0

# ── 스케일·중심 산출(실제 극점만 사용) ────────────────────────────────
_extreme = [
    (-PO, -PO, -PT), (W + PO, -PO, -PT), (-PO, D + PO, -PT), (W + PO, D + PO, -PT),
    (-PO, -PO, 0.0), (W + PO, -PO, 0.0), (-PO, D + PO, 0.0), (W + PO, D + PO, 0.0),
    (0, 0, H), (W, 0, H), (0, D, H), (W, D, H),
    (ROOF_BOX[0], ROOF_BOX[2], ROOF_BOX[5]), (ROOF_BOX[1], ROOF_BOX[2], ROOF_BOX[5]),
    (ROOF_BOX[0], ROOF_BOX[3], ROOF_BOX[5]), (ROOF_BOX[1], ROOF_BOX[3], ROOF_BOX[5]),
]
_xs = [(x - y) * K for x, y, _ in _extreme]
_ys = [(x + y) * 0.5 - z for x, y, z in _extreme]
S = min((CANVAS - 2 * PAD) / (max(_xs) - min(_xs)), (CANVAS - 2 * PAD) / (max(_ys) - min(_ys)))
CX = CANVAS / 2 - (max(_xs) + min(_xs)) / 2 * S
CY = CANVAS / 2 - (max(_ys) + min(_ys)) / 2 * S


def P(x: float, y: float, z: float) -> tuple[float, float]:
    return (CX + (x - y) * K * S, CY + ((x + y) * 0.5 - z) * S)


def _pts(p3: list[tuple[float, float, float]]) -> str:
    return " ".join(f"{sx:.1f},{sy:.1f}" for sx, sy in (P(*p) for p in p3))


out: list[str] = []


def poly(p3, fill="none", stroke=INK, sw=2.4, op=None, sop=None) -> None:
    a = f'<polygon points="{_pts(p3)}" fill="{fill}"'
    if op is not None:
        a += f' fill-opacity="{op}"'
    a += f' stroke="{stroke}"' if stroke else ' stroke="none"'
    if stroke:
        a += f' stroke-width="{sw}"'
        if sop is not None:
            a += f' stroke-opacity="{sop}"'
    out.append(a + "/>")


def seg(p, q, stroke=INK, sw=1.6, sop=None) -> None:
    (x1, y1), (x2, y2) = P(*p), P(*q)
    a = f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"'
    if sop is not None:
        a += f' stroke-opacity="{sop}"'
    out.append(a + "/>")


def fr(x0, x1, z0, z1, y=D, **kw) -> None:
    """우측면(평면 y=const) 위 사각형."""
    poly([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], **kw)


def fl(y0, y1, z0, z1, x=W, **kw) -> None:
    """좌측면(평면 x=const) 위 사각형."""
    poly([(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)], **kw)


def top(x0, x1, y0, y1, z, **kw) -> None:
    poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], **kw)


def box(x0, x1, y0, y1, z0, z1, sw=2.0) -> None:
    """윗면 + 보이는 두 면(우: y=y1 / 좌: x=x1)."""
    fr(x0, x1, z0, z1, y=y1, fill=BG, sw=sw)
    fl(y0, y1, z0, z1, x=x1, fill=SHADE, sw=sw)
    top(x0, x1, y0, y1, z1, fill=WHITE, sw=sw)


# ── 1. 보도 슬래브(그림자 대신 접지) ──────────────────────────────────
out.append("<!-- 보도 슬래브 -->")
fr(-PO, W + PO, -PT, 0, y=D + PO, fill=BG, sw=2.2)
fl(-PO, D + PO, -PT, 0, x=W + PO, fill=SHADE, sw=2.2)
top(-PO, W + PO, -PO, D + PO, 0, fill=WHITE, sw=2.4)

# ── 2. 건물 매스 ─────────────────────────────────────────────────────
out.append("<!-- 건물 매스 -->")
fr(0, W, 0, H, fill=BG, sw=2.8)                 # 우측(정면) 벽
fl(0, D, 0, H, fill=SHADE, sw=2.8)              # 좌측 벽
top(0, W, 0, D, H, fill=WHITE, sw=2.8)          # 파라펫 캡
top(PAR, W - PAR, PAR, D - PAR, H, fill=BG, sw=1.8)   # 옥상 데크

# ── 3. 공실 구간(2~3F) 강조 밴드 ─────────────────────────────────────
out.append("<!-- 공실(2~3F) 강조 밴드 -->")
fr(0, W, EMPTY_LO, EMPTY_HI, fill=ACC, op=0.10, stroke=None)
fl(0, D, EMPTY_LO, EMPTY_HI, fill=ACC, op=0.10, stroke=None)
for z, col, sw in ((Z[1], ACC, 2.6), (Z[2], INK, 1.5), (Z[3], ACC, 2.6)):
    seg((0, D, z), (W, D, z), stroke=col, sw=sw, sop=None if col == ACC else 0.45)
    seg((W, 0, z), (W, D, z), stroke=col, sw=sw, sop=None if col == ACC else 0.45)

# ── 4. 1F 영업 중 — 통유리 · 출입문 · 차양 · 간판 · 조명 ─────────────
out.append("<!-- 1F 영업 중 -->")
GX0, GX1, GZ0, GZ1 = 0.32, 7.18, 0.25, 2.15
fr(GX0, GX1, GZ0, GZ1, fill=WHITE, sw=2.2)                     # 통유리(조명 켜짐)
cols = [GX0 + (GX1 - GX0) * i / 5 for i in range(6)]
for cx_ in cols[1:-1]:
    seg((cx_, D, GZ0), (cx_, D, GZ1), sw=1.5, sop=0.55)        # 멀리언
fr(cols[3], cols[4], 0.0, GZ1, fill=WHITE, sw=2.2)             # 출입문
seg((cols[3] + 0.16, D, 0.0), (cols[3] + 0.16, D, GZ1), sw=1.5, sop=0.55)
seg((cols[4] - 0.22, D, 0.95), (cols[4] - 0.22, D, 1.25), sw=2.6)  # 손잡이

AW0, AW1, AZ0, AZ1, AY = 0.18, 7.32, 2.20, 2.32, 0.46          # 차양
out.append("<!-- 차양 -->")
poly([(AW0, D + AY, AZ0), (AW1, D + AY, AZ0), (AW1, D + AY, AZ1), (AW0, D + AY, AZ1)], fill=SHADE, sw=2.2)
poly([(AW0, D, AZ1), (AW1, D, AZ1), (AW1, D + AY, AZ1), (AW0, D + AY, AZ1)], fill=BG, sw=2.2)
poly([(AW1, D, AZ0), (AW1, D + AY, AZ0), (AW1, D + AY, AZ1), (AW1, D, AZ1)], fill=SHADE, sw=2.2)

out.append("<!-- 간판(글씨 없음) — 돌출 플레이트 + 조명 -->")
SX0, SX1, SZ0, SZ1, SY = 0.28, 7.22, 2.42, 2.98, 0.14
poly([(SX0, D, SZ1), (SX1, D, SZ1), (SX1, D + SY, SZ1), (SX0, D + SY, SZ1)], fill=BG, sw=2.0)
poly([(SX1, D, SZ0), (SX1, D + SY, SZ0), (SX1, D + SY, SZ1), (SX1, D, SZ1)], fill=SHADE, sw=2.0)
fr(SX0, SX1, SZ0, SZ1, y=D + SY, fill=WHITE, sw=2.6)           # 간판 — 빈 판(글씨 없음)
for lx in (1.45, 3.75, 6.05):                                  # 다운라이트 3개 + 빛줄기
    poly([(lx - 0.09, D, 3.09), (lx + 0.09, D, 3.09), (lx + 0.2, D, 2.99), (lx - 0.2, D, 2.99)],
         fill=INK, sw=1.4)
    for dx in (-0.42, 0.0, 0.42):
        seg((lx, D, 2.98), (lx + dx, D, 2.58), sw=1.4, sop=0.45)

# 좌측면 1F — 계단실 출입문 + 작은 창
fl(0.45, 3.05, 0.4, GZ1, fill=WHITE, sw=2.2)
seg((W, 1.75, 0.4), (W, 1.75, GZ1), sw=1.5, sop=0.55)
fl(3.62, 4.72, 0.0, GZ1, fill=WHITE, sw=2.2)
seg((W, 3.78, 0.0), (W, 3.78, GZ1), sw=1.5, sop=0.55)
seg((W, 4.5, 0.95), (W, 4.5, 1.25), sw=2.6)

# ── 5. 상층 창 — 2~3F 공실(어두움+강조) / 4F 입주(밝음) ──────────────
out.append("<!-- 상층 창 -->")
RW = [(0.50 + i * 1.74, 0.50 + i * 1.74 + 1.28) for i in range(4)]   # 우측면 4개
LW = [(0.50 + i * 1.675, 0.50 + i * 1.675 + 1.15) for i in range(3)]  # 좌측면 3개
for fi in (1, 2, 3):
    z0, z1 = Z[fi] + 0.38, Z[fi] + 1.30
    empty = fi in (1, 2)
    kw = dict(fill=INK, stroke=ACC, sw=2.2) if empty else dict(fill=WHITE, stroke=INK, sw=2.2)
    for x0, x1 in RW:
        fr(x0, x1, z0, z1, **kw)
        if not empty:
            seg(((x0 + x1) / 2, D, z0), ((x0 + x1) / 2, D, z1), sw=1.5, sop=0.55)
    for y0, y1 in LW:
        fl(y0, y1, z0, z1, **kw)
        if not empty:
            seg((W, (y0 + y1) / 2, z0), (W, (y0 + y1) / 2, z1), sw=1.5, sop=0.55)

# ── 6. 임대 현수막(글씨 없음) ────────────────────────────────────────
out.append("<!-- 임대 현수막 — 가로(정면) -->")
BY = D + 0.06
bx0, bx1, bz0, bz1 = 0.55, 5.30, 4.53, 5.15
for bx in (bx0, bx1):                                          # 결속 끈
    seg((bx, BY, bz1), (bx + (0.22 if bx == bx0 else -0.22), D, bz1 + 0.26), sw=1.5)
fr(bx0, bx1, bz0, bz1, y=BY, fill=ACC, sw=2.2)
fr(bx0 + 0.16, bx1 - 0.16, bz0 + 0.11, bz1 - 0.11, y=BY, fill="none", stroke=WHITE, sw=1.6)

out.append("<!-- 임대 현수막 — 세로(측면) -->")
BX = W + 0.06
vy0, vy1, vz0, vz1 = 1.62, 3.68, 4.52, 6.48
seg((BX, vy0, vz1), (BX, vy0 - 0.42, vz1 + 0.16), sw=1.6)      # 결속 끈
seg((BX, vy1, vz1), (BX, vy1 + 0.42, vz1 + 0.16), sw=1.6)
seg((BX, vy0 - 0.42, vz1 + 0.16), (BX, vy1 + 0.42, vz1 + 0.16), sw=1.4, sop=0.5)
fl(vy0, vy1, vz0, vz1, x=BX, fill=ACC, sw=2.2)
fl(vy0 + 0.15, vy1 - 0.15, vz0 + 0.13, vz1 - 0.13, x=BX, fill="none", stroke=WHITE, sw=1.6)

# ── 7. 옥상 설비(옥탑 · 물탱크 · 실외기) ─────────────────────────────
out.append("<!-- 옥상 설비 -->")
for b in sorted([ROOF_BOX, ROOF_TANK, *ROOF_AC], key=lambda b: b[0] + b[1] + b[2] + b[3]):
    box(*b, sw=2.0)
seg((ROOF_TANK[0] + 0.2, ROOF_TANK[3], ROOF_TANK[4] + 0.24), (ROOF_TANK[1] - 0.2, ROOF_TANK[3], ROOF_TANK[4] + 0.24), sw=1.5, sop=0.5)
for ac in ROOF_AC:                                             # 실외기 팬 격자
    seg((ac[0] + 0.18, ac[3], ac[4] + 0.12), (ac[1] - 0.18, ac[3], ac[4] + 0.12), sw=1.4, sop=0.5)
    seg((ac[0] + 0.18, ac[3], ac[4] + 0.24), (ac[1] - 0.18, ac[3], ac[4] + 0.24), sw=1.4, sop=0.5)

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS:.0f}" height="{CANVAS:.0f}" '
    f'viewBox="0 0 {CANVAS:.0f} {CANVAS:.0f}" fill="none">\n'
    '<g stroke-linejoin="round" stroke-linecap="round">\n'
    + "\n".join(out)
    + "\n</g>\n</svg>\n"
)

dst = Path(__file__).with_name("iso-commercial-building.svg")
dst.write_text(svg, encoding="utf-8")
print(f"wrote {dst}  ({len(svg)} bytes)  S={S:.2f} CX={CX:.1f} CY={CY:.1f}")
