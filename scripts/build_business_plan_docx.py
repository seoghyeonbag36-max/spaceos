# -*- coding: utf-8 -*-
"""PlaceOS 사업 기획안(투자자용) .docx 생성기.

규칙
- 수치는 실측 산출물에서만 인용한다. 재지 않은 값은 "[측정 필요]" 로 남긴다.
- 한글 폰트는 **임베딩**한다. 폰트명만 지정하면 뷰어(Cowork 프리뷰 등)에서 □ 로 깨진다.
  → Noto Sans KR 을 문서에 쓰인 글자로 subset → ECMA-376 §17.8.1 난독화(.odttf) → fontTable.xml 배선.

실행:
    python scripts/build_business_plan_docx.py [-o 출력경로] [--fonts 폰트캐시디렉터리]
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

# ── 색 ─────────────────────────────────────────────────────────────────────
INK = "16202E"      # 본문
NAVY = "1B3A5C"     # 제목
MUTED = "5C6875"    # 보조 설명
ACCENT = "9C4221"   # 강조(격차·경고)
RULE = "C9D2DC"     # 괘선
HEADFILL = "EEF2F6" # 표 머리 배경
ZEBRA = "F7F9FB"    # 표 짝수행
NOTEFILL = "F4F1EA" # 인용/전제 박스

FONT = "Noto Sans KR"

FONT_URLS = {
    "regular": "https://fonts.gstatic.com/s/notosanskr/v39/"
               "PbyxFmXiEBPT4ITbgNA5Cgms3VYcOA-vvnIzzuoyeLQ.ttf",
    "bold": "https://fonts.gstatic.com/s/notosanskr/v39/"
            "PbyxFmXiEBPT4ITbgNA5Cgms3VYcOA-vvnIzzg01eLQ.ttf",
}


# ── OOXML 헬퍼 ─────────────────────────────────────────────────────────────
def _el(tag: str, **attrs) -> OxmlElement:
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(f"w:{k}"), str(v))
    return e


# CT_PPr 스키마 순서상 pBdr / shd 뒤에 오는 태그들. insert_element_before 로 위치를 맞춘다.
_AFTER_PBDR = (
    "w:shd", "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
    "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN", "w:bidi",
    "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind", "w:contextualSpacing",
    "w:mirrorIndents", "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment",
    "w:textboxTightWrap", "w:outlineLvl", "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr",
    "w:pPrChange",
)
_AFTER_SHD = _AFTER_PBDR[1:]


def para_border(p, edges=("bottom",), color=RULE, sz=6, space=6):
    """단락 테두리. 4면을 다 주면 OOXML 스키마가 깨지므로 top/bottom 위주로만 쓴다.

    한 단락에 두 번 불러도(위 테두리 → 아래 테두리) w:pBdr 은 하나만 유지한다.
    pPr 안에 pBdr 이 둘이면 스키마 위반이라 뷰어가 파일을 아예 열지 못한다.
    """
    pPr = p._p.get_or_add_pPr()
    pbdr = pPr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        pPr.insert_element_before(pbdr, *_AFTER_PBDR)
    want = dict.fromkeys(edges)
    have = {}
    for e in ("top", "left", "bottom", "right"):
        node = pbdr.find(qn(f"w:{e}"))
        if node is not None:
            have[e] = node
            pbdr.remove(node)
    for e in want:
        have[e] = _el(f"w:{e}", val="single", sz=sz, space=space, color=color)
    for e in ("top", "left", "bottom", "right"):          # CT_PBdr 순서대로 다시 넣는다
        if e in have:
            pbdr.append(have[e])


def para_shade(p, fill):
    pPr = p._p.get_or_add_pPr()
    shd = _el("w:shd", val="clear", color="auto", fill=fill)
    pPr.insert_element_before(shd, *_AFTER_SHD)


# CT_TcPr 순서상 w:shd 뒤에 오는 태그들
_AFTER_TC_SHD = ("w:noWrap", "w:tcMar", "w:textDirection", "w:tcFitText",
                 "w:vAlign", "w:hideMark")


def cell_shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    tcPr.insert_element_before(_el("w:shd", val="clear", color="auto", fill=fill),
                               *_AFTER_TC_SHD)


def cell_margins(cell, top=70, bottom=70, left=110, right=110):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for tag, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        mar.append(_el(f"w:{tag}", w=val, type="dxa"))
    tcPr.append(mar)


def keep_with_next(p):
    pPr = p._p.get_or_add_pPr()
    pPr.insert_element_before(_el("w:keepNext", val="1"),
                              "w:keepLines", "w:pageBreakBefore", "w:framePr",
                              "w:widowControl", "w:numPr", "w:suppressLineNumbers",
                              "w:pBdr", *_AFTER_PBDR)


# ── 문단/런 ────────────────────────────────────────────────────────────────
def run(p, text, *, size=10.5, bold=False, color=INK, italic=False, spacing=None):
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = RGBColor.from_string(color)
    r.font.name = FONT
    rPr = r._element.get_or_add_rPr()
    rf = rPr.get_or_add_rFonts()
    rf.set(qn("w:eastAsia"), FONT)
    rf.set(qn("w:cs"), FONT)
    if spacing is not None:  # 자간(twips*20 단위) — CT_RPr 순서상 w:sz 앞
        rPr.insert_element_before(_el("w:spacing", val=spacing),
                                  "w:w", "w:kern", "w:position", "w:sz", "w:szCs",
                                  "w:highlight", "w:u", "w:effect", "w:bdr", "w:shd",
                                  "w:fitText", "w:vertAlign", "w:rtl", "w:cs", "w:em",
                                  "w:lang", "w:eastAsianLayout", "w:specVanish", "w:oMath")
    return r


def para(doc_or_cell, *, before=0, after=0, line=1.45, align=None, indent=0, right=0):
    p = doc_or_cell.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if align is not None:
        pf.alignment = align
    if indent:
        pf.left_indent = Cm(indent)
    if right:
        pf.right_indent = Cm(right)
    return p


def body(doc, text, *, after=7, before=0, size=10.5, color=INK, indent=0, line=1.5):
    p = para(doc, before=before, after=after, line=line, indent=indent,
             align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    run(p, text, size=size, color=color)
    return p


def h1(doc, num, title):
    p = para(doc, before=20, after=2, line=1.15)
    run(p, f"{num}   ", size=17, bold=True, color=ACCENT)
    run(p, title, size=17, bold=True, color=NAVY)
    para_border(p, ("bottom",), color=NAVY, sz=10, space=6)
    keep_with_next(p)
    return p


def h2(doc, num, title):
    p = para(doc, before=13, after=4, line=1.2)
    run(p, f"{num}  ", size=11.5, bold=True, color=ACCENT)
    run(p, title, size=11.5, bold=True, color=NAVY)
    keep_with_next(p)
    return p


def caption(doc, text):
    p = para(doc, before=3, after=11, line=1.3)
    run(p, text, size=8.5, color=MUTED)
    return p


def table_title(doc, text):
    p = para(doc, before=9, after=3, line=1.2)
    run(p, text, size=9.5, bold=True, color=NAVY)
    keep_with_next(p)
    return p


def note_box(doc, lines, *, fill=NOTEFILL, border=ACCENT):
    """전제·경고용 박스. top/bottom 만 준다(4면 지정은 스키마 위반)."""
    first = None
    for i, (text, bold) in enumerate(lines):
        p = para(doc, before=(9 if i == 0 else 0), after=(9 if i == len(lines) - 1 else 3),
                 line=1.45, indent=0.32, right=0.32)
        run(p, text, size=9.5, bold=bold, color=INK)
        para_shade(p, fill)
        if i == 0:
            para_border(p, ("top",), color=border, sz=12, space=8)
            first = p
        if i == len(lines) - 1:
            para_border(p, ("bottom",), color=border, sz=12, space=8)
        keep_with_next(p) if i < len(lines) - 1 else None
    return first


def bullets(doc, items, *, marker="—", size=10.5, after=4, indent=0.5):
    for it in items:
        p = para(doc, after=after, line=1.45, indent=indent,
                 align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        p.paragraph_format.first_line_indent = Cm(-0.5)
        run(p, f"{marker}  ", size=size, bold=True, color=ACCENT)
        if isinstance(it, tuple):
            run(p, it[0], size=size, bold=True, color=NAVY)
            run(p, it[1], size=size, color=INK)
        else:
            run(p, it, size=size, color=INK)


# ── 표 ─────────────────────────────────────────────────────────────────────
def make_table(doc, rows, widths_cm, *, head=True, sizes=None, aligns=None,
               zebra=True, bold_first_col=False):
    n_col = len(widths_cm)
    t = doc.add_table(rows=len(rows), cols=n_col)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False

    tblPr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        borders.append(_el(f"w:{edge}", val="single", sz=4, space=0, color=RULE))
    tblPr.insert_element_before(borders, "w:shd", "w:tblLayout", "w:tblCellMar",
                                "w:tblLook", "w:tblCaption", "w:tblDescription")

    grid = t._tbl.find(qn("w:tblGrid"))
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths_cm):
        gc.set(qn("w:w"), str(int(w * 567)))

    for ri, row in enumerate(rows):
        is_head = head and ri == 0
        tr = t.rows[ri]
        trPr = tr._tr.get_or_add_trPr()
        if is_head:
            trPr.append(_el("w:tblHeader", val="true"))
        trPr.append(_el("w:cantSplit", val="true"))
        for ci, val in enumerate(row):
            cell = t.cell(ri, ci)
            cell.width = Cm(widths_cm[ci])
            cell_margins(cell)
            if is_head:
                cell_shade(cell, HEADFILL)
            elif zebra and ri % 2 == 0:
                cell_shade(cell, ZEBRA)
            cell.paragraphs[0]._p.getparent().remove(cell.paragraphs[0]._p)
            for li, line in enumerate(str(val).split("\n")):
                p = para(cell, before=0, after=0, line=1.32)
                if aligns:
                    p.paragraph_format.alignment = aligns[ci]
                size = (sizes[ci] if sizes else 9.0)
                bold = is_head or (bold_first_col and ci == 0)
                color = NAVY if is_head else INK
                if line.startswith("!"):     # ! 접두 = 강조
                    line, bold, color = line[1:], True, ACCENT
                run(p, line, size=size, bold=bold, color=color)
    return t


# ── 바닥글(쪽번호) ──────────────────────────────────────────────────────────
def add_footer(section, label):
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    para_border(p, ("top",), color=RULE, sz=4, space=8)
    run(p, f"{label}          ", size=8, color=MUTED)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), " PAGE ")
    fp = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rf = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), FONT)
    rPr.append(rf)
    rPr.append(_el("w:color", val=MUTED))
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), "16"); rPr.append(sz)
    fp.append(rPr)
    t = OxmlElement("w:t"); t.text = "1"; fp.append(t)
    fld.append(fp)
    p._p.append(fld)


# ── 문서 기본 스타일 ───────────────────────────────────────────────────────
def setup(doc):
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(10.5)
    st.font.color.rgb = RGBColor.from_string(INK)
    rPr = st.element.get_or_add_rPr()
    rf = rPr.get_or_add_rFonts()
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), FONT)

    # docDefaults 까지 한글 폰트로 못박는다(뷰어가 스타일을 못 읽어도 대체되지 않도록)
    docdef = doc.styles.element.find(qn("w:docDefaults"))
    if docdef is not None:
        rpr_def = docdef.find(qn("w:rPrDefault"))
        if rpr_def is not None:
            r = rpr_def.find(qn("w:rPr"))
            if r is None:
                r = OxmlElement("w:rPr"); rpr_def.append(r)
            old = r.find(qn("w:rFonts"))
            if old is not None:
                r.remove(old)
            nf = OxmlElement("w:rFonts")
            for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                nf.set(qn(a), FONT)
            r.insert(0, nf)

    zoom = doc.settings.element.find(qn("w:zoom"))
    if zoom is not None and zoom.get(qn("w:percent")) is None:
        zoom.set(qn("w:percent"), "100")

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(2.3), Cm(2.1)
    sec.left_margin, sec.right_margin = Cm(2.4), Cm(2.4)
    sec.footer_distance = Cm(1.2)
    return sec


# ══════════════════════════════════════════════════════════════════════════
#  본문
# ══════════════════════════════════════════════════════════════════════════
J = WD_ALIGN_PARAGRAPH.JUSTIFY
C = WD_ALIGN_PARAGRAPH.CENTER
R = WD_ALIGN_PARAGRAPH.RIGHT
L = WD_ALIGN_PARAGRAPH.LEFT


def cover(doc):
    p = para(doc, before=96, after=0, line=1.1)
    run(p, "PlaceOS", size=42, bold=True, color=NAVY, spacing=-20)
    p = para(doc, before=2, after=0, line=1.25)
    run(p, "물리적 상권의 디지털 트윈 플랫폼", size=15, color=MUTED)

    p = para(doc, before=26, after=0, line=1.15)
    para_border(p, ("top",), color=ACCENT, sz=18, space=14)
    run(p, "사업 기획안", size=25, bold=True, color=INK)
    p = para(doc, before=1, after=0, line=1.35)
    run(p, "독자 — 투자자", size=12, bold=True, color=ACCENT)

    p = para(doc, before=22, after=0, line=1.55)
    run(p, "가설 ", size=10, bold=True, color=MUTED)
    run(p, "Place ▶ Platform", size=12, bold=True, color=NAVY)
    run(p, "  ·  물리적 공간을 SNS·디지털 관점의 플랫폼으로 읽는다", size=10.5, color=INK)

    note_box(doc, [
        ("서울 66개 거점 전부를 건축물대장으로 실측했다. 664개 공실 유닛이 건물·층 단위로 서 있다. "
         "그리고 우리가 재는 공실률은 중대형 상가 표본이 재는 공실률보다 5.52~7.5%p 높다 — "
         "이 문서는 유리한 숫자가 아니라 그 격차의 이유부터 설명한다.", False),
    ], fill=NOTEFILL, border=ACCENT)

    rows = [
        ["항목", "값"],
        ["거점 커버리지", "서울 66거점 · 전부 Tier1(건축물대장 실측)"],
        ["공실 유닛 인벤토리", "66/66 거점 · 664유닛"],
        ["히트맵", "4레이어(공실·임대·유동·밀도) · 동일 100m 격자"],
        ["업종 추천", "Top-3 91.7% (거점 사전분포 89.3% · Top-1 lift 5.3%)"],
        ["비즈니스 모델", "DaaS 월 500만원 B2B 구독 · 6개월차 파일럿 5~10건"],
    ]
    make_table(doc, rows, [4.0, 12.2], sizes=[9.0, 9.0],
               aligns=[L, L], bold_first_col=True)

    p = para(doc, before=30, after=0, line=1.5)
    run(p, "2026년 9월", size=9.5, color=MUTED)
    p = para(doc, before=0, after=0, line=1.5)
    run(p, "작성 — sh.pac (창업자 · 디지털 트윈 AI/IT 개발)", size=9.5, color=MUTED)

    p = para(doc, before=0, after=0)
    run(p, "").add_break(WD_BREAK.PAGE)


def sec0(doc):
    h1(doc, "0", "이 문서가 쓰는 수, 쓰지 않는 수")
    body(doc,
         "먼저 규칙을 밝힌다. 본문의 모든 수치는 PlaceOS가 직접 만든 산출물에서 인용했다. "
         "업계 통용치, 시장 규모 추정, 비교 기업의 밸류에이션은 한 줄도 쓰지 않았다. "
         "그런 수는 이 문서에서 검증할 수 없고, 검증할 수 없는 수는 투자 판단을 돕는 대신 흐리기 때문이다.")
    body(doc,
         "아직 재지 않은 값은 빈칸으로 두지 않고 [측정 필요] 로 표기했다. 이 표기는 문서의 결함이 아니라 "
         "설계다. 어떤 칸이 비어 있는지가 곧 앞으로 6개월간 무엇을 측정할 것인지의 목록이며, "
         "5장의 비즈니스 모델과 6장의 로드맵은 그 칸들을 채우기 위한 계획으로 짜여 있다. "
         "부록 A에 전체 목록을 정리했다.")
    note_box(doc, [
        ("읽는 방법", True),
        ("굵은 수 = 실측값. [측정 필요] = 아직 재지 않은 값, 추정으로 채우지 않음. "
         "4장은 우리 수와 공표 지표(앵커)의 차이를 먼저 다룬다 — 이 문서에서 가장 먼저 읽어야 할 장이다.", False),
    ], fill="F1F5F9", border=NAVY)


def sec1(doc):
    h1(doc, "1", "문제")

    h2(doc, "1.1", "하나의 상권에 공실률이 여러 개 있다")
    body(doc,
         "상권 데이터 시장에서 '공실률'은 마치 단일한 숫자처럼 유통된다. 그러나 같은 지역, 같은 시점에 대해 "
         "재는 주체가 다르면 다른 수가 나온다. 우리가 건축물대장으로 전수 실측한 값과, 중대형 상가를 표본 "
         "조사하는 공표 지표(이하 앵커)를 나란히 놓으면 차이는 이렇게 벌어진다.")
    make_table(doc, [
        ["거점", "PlaceOS 대표공실", "앵커(중대형 표본)", "격차"],
        ["연남동", "12.5%", "5.0%", "!+7.5%p"],
        ["신촌·이대", "17.2%", "11.68%", "!+5.52%p"],
        ["홍대", "15.0%", "8.1%", "!+6.9%p"],
    ], [4.2, 4.4, 4.4, 3.2], sizes=[9.0, 9.0, 9.0, 9.0],
        aligns=[L, C, C, C], bold_first_col=True)
    caption(doc, "표 1. 3개 거점의 실측값과 앵커 지표. 앵커는 R-ONE 계열 중대형 상가 공실률. "
                 "세 거점 모두 우리 수가 높고, 폭은 +5.52%p ~ +7.5%p 안에 든다.")
    body(doc,
         "이 차이는 어느 한쪽이 틀려서 생기는 것이 아니다. 두 수는 서로 다른 모수를 세고 있다(4장에서 분해한다). "
         "문제는 차이가 있다는 사실 자체가 아니라, 그 차이가 어디서 오는지 아무도 설명해 주지 않은 채 숫자만 "
         "돌아다닌다는 점이다. 출점 담당자는 5.0% 를 보고 '연남동엔 빈 자리가 없다'고 판단한 뒤, 현장에 가서 "
         "이면도로 1층이 줄줄이 비어 있는 것을 본다. 데이터가 판단을 돕는 게 아니라 판단을 배신한다.")

    h2(doc, "1.2", "의사결정의 단위와 데이터의 단위가 어긋난다")
    body(doc,
         "프랜차이즈 출점팀의 실제 질문은 '연남동 공실률이 몇 %인가'가 아니다. "
         "'이 블록에서 지금 들어갈 수 있는 자리가 어느 건물 몇 층인가'다. "
         "자산운용사의 질문은 '보유 건물 3층이 왜 계속 안 나가는가, 주변 같은 층은 어떤가'다. "
         "지자체의 질문은 '이 골목의 빈 점포에 무엇을 넣어야 하는가'다.")
    body(doc,
         "세 질문 모두 건물·층·유닛 단위다. 그런데 시장에 유통되는 데이터는 상권 단위의 비율이다. "
         "비율은 건물을 지목하지 못한다. 단위가 어긋나 있으면 데이터가 아무리 정확해도 의사결정에 그대로 "
         "들어가지 못하고, 그 사이는 현장 답사와 중개인의 구전으로 메워진다.")

    h2(doc, "1.3", "그래서 읽기와 실행이 끊긴다")
    body(doc,
         "답사와 구전으로 메운 판단은 재현되지 않는다. 같은 회사가 6개월 뒤 같은 상권을 다시 볼 때 이전 판단의 "
         "근거는 남아 있지 않다. 입점 이후의 홍보 계획은 또 다른 팀이 처음부터 다시 만든다. "
         "상권을 읽고 · 자리를 고르고 · 넣고 · 돌리는 네 단계가 각각 다른 도구, 다른 근거, 다른 담당자로 끊겨 있다.")
    body(doc,
         "이 네 단계를 하나의 데이터 위에서 잇는 것이 PlaceOS의 설계 목표다. 그 구조가 3장의 PPPP 다.")
    bullets(doc, [
        ("[측정 필요] ", "출점 1건당 현장 실사에 드는 비용·기간, 그리고 그 실사 판단의 사후 적중률. "
                        "고객사 실적으로만 잴 수 있는 값이므로 파일럿에서 측정한다."),
    ], marker="·", size=9.5)


def sec2(doc):
    h1(doc, "2", "해법")

    h2(doc, "2.1", "단위를 내리고, 모수를 열었다")
    body(doc,
         "PlaceOS는 물리적 상권을 하나의 플랫폼으로 읽는 디지털 트윈이다. 가설은 'Place ▶ Platform' — "
         "상권을 지도 위의 면적이 아니라, 페이지(공간)를 올릴 수 있는 플랫폼으로 본다. "
         "이 관점을 데이터로 만들기 위해 두 가지를 바꿨다.")
    bullets(doc, [
        ("단위를 내렸다. ", "상권 평균 비율이 아니라 건물·층·유닛까지 내려간다. 지금 66개 거점 전부에서 "
                          "664개 공실 유닛이 개별 레코드로 서 있다. 비율이 아니라 목록이다."),
        ("모수를 열었다. ", "표본이 아니라 전수다. 건축물대장을 기준으로 거점 경계 안의 노출 건물을 전부 센다 — "
                          "연남동 1,133동, 신촌·이대 1,443동, 홍대 1,325동. 대로변 대형 건물만이 아니라 "
                          "이면도로의 저층 근린 건물까지 모수에 들어온다."),
    ])
    body(doc,
         "1.1의 격차는 이 두 번째 변화의 직접적인 결과다. 모수를 열었기 때문에 우리 수가 높다. "
         "그래서 우리는 그 격차를 감추지 않고, 4장에서 그것부터 설명한다.")

    h2(doc, "2.2", "지금 서 있는 것")
    make_table(doc, [
        ["산출물", "현재 상태", "무엇을 말하는가"],
        ["거점 커버리지", "서울 66거점 전부 Tier1", "66개 모두 건축물대장으로 실측. 추정으로 채운 거점 0개"],
        ["공실 유닛 인벤토리", "66/66 거점 · 664유닛", "'몇 %'가 아니라 '어느 건물 몇 층'의 목록"],
        ["히트맵", "4레이어 · 동일 100m 격자", "공실·임대·유동·밀도를 겹쳐 읽을 수 있는 상태"],
        ["업종 추천", "Top-3 91.7%", "거점 사전분포 89.3% 대비 Top-1 lift 5.3%"],
    ], [3.4, 4.2, 8.6], sizes=[9.0, 9.0, 9.0], aligns=[L, L, L], bold_first_col=True)
    caption(doc, "표 2. 2026년 9월 기준 실물 산출물. 진행률은 문서가 아니라 산출물로 센다(6.2 참조).")
    body(doc,
         "'Tier1' 은 이 문서에서 '건축물대장으로 실측했다'는 뜻이다. 66개 거점 중 일부만 실측하고 나머지를 "
         "추정으로 채운 것이 아니라, 전부가 같은 방법으로 잰 수다. 커버리지의 넓이보다 잰 방식의 균질함이 "
         "먼저다 — 방법이 섞이면 거점 간 비교가 성립하지 않는다.")
    body(doc,
         "4레이어가 같은 100m 격자 위에 선다는 점도 그냥 넘어갈 대목이 아니다. 공실·임대·유동·밀도를 각각 "
         "다른 해상도로 그리면 겹쳐 읽을 수 없다. 같은 격자에 올려야 '유동은 상위인데 공실이 몰린 셀' 같은 "
         "교차 조건으로 자리를 지목할 수 있다. 레이어 수가 아니라 정렬이 자산이다.")

    h2(doc, "2.3", "읽는 데서 멈추지 않는다")
    body(doc,
         "상권 분석 도구는 이미 여럿 있다. PlaceOS가 다른 지점은 읽기에서 끝나지 않는다는 것이다. "
         "상권을 읽고(Platform), 어디에 자리가 있는지 지목하고(Page), 어느 가격대로 넣을지 판단하고(Posting), "
         "넣은 다음 무엇으로 돌릴지(Program)까지 같은 데이터 위에서 잇는다. "
         "이 네 트랙이 PPPP 이며, 전통 마케팅 4P 와 1:1 로 대응한다.")


def sec3(doc):
    h1(doc, "3", "PPPP 프레임워크")
    body(doc,
         "PPPP 는 전통 4P(Place·Product·Price·Promotion)를 디지털 관점으로 하나씩 갈아끼운 구조다. "
         "네 트랙이 각각 4P 하나씩을 맡는다. 억지 대응이 아니라, 상권을 플랫폼으로 읽으면 4P 의 네 질문이 "
         "그대로 네 개의 다른 질문으로 번역된다는 뜻이다.")
    make_table(doc, [
        ["전통 4P", "PlaceOS", "묻는 질문", "구현"],
        ["Place", "Platform", "이 입지·상권은 어떤 플랫폼인가",
         "상권 AI 추천 엔진 — 업종 추천, 상권 정체성, 공실 예측"],
        ["Product", "Page", "이 platform 안에 어떤 page 가 만들어져야 하는가",
         "공실 히트맵 + 층별 매물 목록 + 네이버 거리뷰"],
        ["Price", "Posting", "어떤 가격대의 page 가 이 platform 에 posting 되어야 하는가",
         "입점 솔루션 — 임대료·회수기간 기준의 가격대 판단"],
        ["Promotion", "Program", "posting 한 page 를 어떤 홍보 program 으로 돌릴 것인가",
         "마케팅 자동화 — 온·오프라인 홍보 방법 제시"],
    ], [2.3, 2.3, 5.6, 6.0], sizes=[9.0, 9.0, 9.0, 9.0], aligns=[L, L, L, L])
    caption(doc, "표 3. 전통 4P 와 PPPP 의 1:1 대응.")

    p = para(doc, before=6, after=10, line=1.5, align=C)
    run(p, "어떤 플랫폼인가  →  어떤 page 를 놓을까  →  어느 가격대로 posting 할까  →  어떻게 program 을 돌릴까.",
        size=10.5, bold=True, color=NAVY)

    h2(doc, "3.1", "Platform — Place ▶ Platform")
    body(doc,
         "입지를 '위치'가 아니라 '성격'으로 읽는다. 같은 면적, 같은 임대료라도 어떤 플랫폼이냐에 따라 "
         "올릴 수 있는 페이지가 다르다. 이 트랙의 산출물이 업종 추천이며, 현재 Top-3 91.7% 다. "
         "이 수치를 어떻게 읽어야 하는지는 4.6에서 따로 다룬다 — 액면 그대로 자랑할 수 있는 수가 아니다.")

    h2(doc, "3.2", "Page — Product ▶ Page")
    body(doc,
         "제품이 아니라 페이지다. 플랫폼 안에 어떤 페이지가 만들어져야 하는가를 묻는다. "
         "공실 히트맵으로 빈 자리의 분포를 보고, 층별 매물 목록으로 그 자리를 개별 유닛까지 좁히고, "
         "거리뷰로 그 앞에 실제로 서 본다. 664개 공실 유닛은 곧 '지금 비어 있는 페이지 자리'의 목록이다. "
         "1.2에서 말한 단위 불일치를 정면으로 해소하는 트랙이 여기다.")

    h2(doc, "3.3", "Posting — Price ▶ Posting")
    body(doc,
         "'얼마에 팔 것인가'가 아니라 '어떤 가격대의 page 가 이 platform 에 올라가야 하는가'를 묻는다. "
         "임대료와 회수기간이 곧 가격대 판단이다. 고급화·가성비·기능중심의 시나리오별로 비용과 효용을 "
         "비교하고, 외부에서 만들어진 창업 코파일럿을 연동할 수 있도록 어댑터 구조로 설계했다. "
         "이 트랙의 정확도 검증은 실제 입점 이후의 성과와 대조해야 성립하므로 [측정 필요] 다.")

    h2(doc, "3.4", "Program — Promotion ▶ Program")
    body(doc,
         "대상이 분명하다. Platform(상권) 안의 빈 Page(공실 건물)에 Posting(입점)하는 기업이다. "
         "그 기업에게 온·오프라인 홍보 방법을 준다. 입점이 끝이 아니라 시작이라는 점, 그리고 홍보의 근거가 "
         "입점 판단에 쓴 것과 같은 상권 데이터라는 점이 이 트랙의 값어치다. "
         "앞의 세 트랙에서 쌓인 상권 데이터를 재사용하므로 한계비용이 낮다.")

    make_table(doc, [
        ["트랙", "지금 서 있는 것", "다음에 재야 할 것"],
        ["Platform", "업종 추천 Top-3 91.7% · Top-1 lift 5.3%", "[측정 필요] 실제 출점 후 생존과의 상관"],
        ["Page", "66/66 거점 · 664유닛 · 4레이어 히트맵", "[측정 필요] 인벤토리 갱신 주기와 신선도"],
        ["Posting", "3-Tier 비용-효용 구조 + 외부 코파일럿 어댑터", "[측정 필요] 회수기간 예측의 사후 오차"],
        ["Program", "온·오프라인 홍보안 생성 구조", "[측정 필요] 홍보안 채택률·성과"],
    ], [2.6, 7.0, 6.6], sizes=[9.0, 9.0, 9.0], aligns=[L, L, L], bold_first_col=True)
    caption(doc, "표 4. 트랙별 현재 상태. 오른쪽 열이 앞으로 6개월의 측정 대상이다.")


def sec4(doc):
    h1(doc, "4", "실측 근거")
    body(doc,
         "이 장은 유리한 순서로 쓰지 않았다. 우리 수와 공표 지표의 격차를 먼저 놓고, 그 격차가 왜 생기는지 "
         "분해한 다음, 나머지 산출물로 넘어간다. 투자자가 사는 것은 낮은 숫자가 아니라 재현 가능한 측정이라고 "
         "보기 때문이다.")

    h2(doc, "4.1", "3개 거점 실측")
    make_table(doc, [
        ["거점", "노출 동수\n(건축물대장 전수)", "PlaceOS\n대표공실", "앵커\n(중대형 표본)", "격차"],
        ["연남동", "1,133동", "12.5%", "5.0%", "!+7.5%p"],
        ["신촌·이대", "1,443동", "17.2%", "11.68%", "!+5.52%p"],
        ["홍대", "1,325동", "15.0%", "8.1%", "!+6.9%p"],
    ], [3.0, 3.9, 3.0, 3.3, 3.0], sizes=[9.0, 8.5, 9.0, 9.0, 9.0],
        aligns=[L, C, C, C, C], bold_first_col=True)
    caption(doc, "표 5. 서울 66거점 중 대표 3개 거점. 66개 전부가 같은 방식(건축물대장 실측)으로 잰 Tier1 이며, "
                 "여기 실린 3개는 그중 앵커 대조까지 마친 거점이다.")

    h2(doc, "4.2", "격차를 먼저 말한다")
    note_box(doc, [
        ("세 거점 모두 PlaceOS 값이 앵커보다 높다. 폭은 +5.52%p ~ +7.5%p 다. "
         "이 격차는 오차가 아니라 두 지표가 서로 다른 모수를 세고 있다는 사실의 크기다.", True),
    ])
    body(doc,
         "실측 데이터를 파는 회사가 공표 지표와 두 배 넘게 벌어지는 수를 내놓으면, 가장 먼저 나올 질문은 "
         "'그럼 둘 중 어느 쪽이 틀렸는가'다. 답은 '둘 다 틀리지 않았다' 이며, 그 이유를 설명할 수 없다면 "
         "우리 데이터는 팔 물건이 못 된다. 그래서 이 절이 4장의 첫머리에 있다.")

    h2(doc, "4.3", "전수 실측과 중대형 표본은 다른 수를 잰다")
    body(doc,
         "두 지표의 차이는 정확도의 차이가 아니라 모수의 차이다.")
    make_table(doc, [
        ["", "PlaceOS 대표공실", "앵커 지표"],
        ["모수", "거점 경계 안의 노출 건물 전수\n(연남동 1,133동 · 신촌·이대 1,443동 · 홍대 1,325동)",
         "중대형 상가 표본"],
        ["포함되는 것", "대로변 대형 건물 + 이면도로 저층 근린 건물 + 소규모 상가",
         "표본에 편입된 중대형 상가 중심"],
        ["기준 자료", "건축물대장(공부) 실측", "표본 조사"],
        ["강점", "누락 없이 다 센다. 건물·층 단위로 지목할 수 있다", "장기 시계열이 안정적으로 이어진다"],
        ["대가", "시계열이 짧다(수집 시작 시점부터)", "모수가 좁다. 좁은 쪽이 덜 잡힌다"],
    ], [2.7, 7.3, 6.2], sizes=[8.8, 8.8, 8.8], aligns=[L, L, L], bold_first_col=True)
    caption(doc, "표 6. 두 지표는 경쟁하는 추정치가 아니라, 서로 다른 대상을 재는 두 개의 자다.")
    body(doc,
         "공실은 상권 안에 균등하게 분포하지 않는다. 저층·소형·이면도로 쪽에 몰린다. "
         "모수를 중대형으로 좁히면 공실이 몰려 있는 쪽이 덜 잡히고, 전수로 열면 다 잡힌다. "
         "그래서 전수 실측은 구조적으로 더 높은 수가 나온다. +5.52 ~ +7.5%p 라는 폭은 오차의 크기가 아니라 "
         "'모수를 여는 일이 얼마나 큰 차이를 만드는가'의 크기다.")
    body(doc,
         "정의 차이도 하나 남아 있다. 대장 기반 실측은 물리적으로 비어 있는 유닛을 세고, 앵커 지표는 "
         "임대차 계약을 기준으로 한 공실을 센다. 두 정의가 완전히 같지는 않다. "
         "전체 격차 중 모수 차이가 설명하는 몫과 정의 차이가 설명하는 몫이 각각 몇 %p 인지는 "
         "[측정 필요] 다 — 파일럿 고객사의 계약 데이터를 받아 분해하는 것이 6장 로드맵의 항목으로 들어가 있다. "
         "지금 이 분해를 추정치로 채우면 이 문서 전체의 규칙이 깨진다.")

    h2(doc, "4.4", "격차가 계통적이라는 두 가지 근거")
    body(doc,
         "'모수 차이 때문'이라는 설명은 그 자체로는 변명이 될 수도 있다. 검증 가능한 근거 두 가지를 든다.")
    bullets(doc, [
        ("부호와 폭. ", "세 거점의 격차는 모두 같은 부호(+)이고, 폭은 +5.52%p · +6.9%p · +7.5%p 로 "
                      "2%p 남짓한 띠 안에 든다. 우리 수집이 무작위로 틀리고 있다면 부호가 섞이거나 폭이 훨씬 "
                      "넓게 흩어져야 한다. 한 방향, 좁은 폭은 계통 차이의 특징이다."),
        ("서열 보존. ", "PlaceOS 기준 순위는 신촌·이대(17.2%) > 홍대(15.0%) > 연남동(12.5%) 이고, "
                      "앵커 기준 순위도 신촌·이대(11.68%) > 홍대(8.1%) > 연남동(5.0%) 로 완전히 같다. "
                      "수준(level)은 다르지만 서열(order)은 일치한다. 우리 지표가 앵커와 다른 세계를 보고 있는 "
                      "것이 아니라, 같은 세계를 더 넓은 모수로 보고 있다는 뜻이다."),
    ])
    body(doc,
         "서열이 보존된다는 점은 상업적으로도 중요하다. 고객이 이미 앵커 지표에 익숙하다면, 우리 수는 그것을 "
         "부정하는 대신 같은 순위 위에 해상도를 더하는 것으로 받아들일 수 있다. "
         "격차를 감췄다면 이 논거 자체가 성립하지 않는다.")
    bullets(doc, [
        ("[측정 필요] ", "앵커 대조를 마친 거점을 3개에서 더 늘렸을 때에도 부호 일치와 서열 보존이 유지되는지. "
                        "거점 수가 늘수록 이 주장은 강해지거나 무너진다."),
    ], marker="·", size=9.5)

    h2(doc, "4.5", "인벤토리 · 히트맵 · 업종 추천")
    body(doc,
         "공실률은 우리 산출물의 일부일 뿐이다. 나머지 셋은 비율이 아니라 목록과 좌표로 서 있다.")
    make_table(doc, [
        ["산출물", "실측값", "왜 이 형태인가"],
        ["공실 유닛 인벤토리", "66/66 거점 · 664유닛",
         "비율은 건물을 지목하지 못한다. 유닛 목록이라야 '어느 건물 몇 층'에 답한다"],
        ["히트맵 4레이어", "공실·임대·유동·밀도\n동일 100m 격자",
         "같은 격자에 정렬해야 교차 조건으로 셀을 지목할 수 있다"],
        ["업종 추천", "Top-3 91.7%\n(사전분포 89.3%)",
         "자리를 찾은 다음의 질문 — 무엇을 넣을 것인가"],
    ], [3.2, 4.0, 9.0], sizes=[9.0, 9.0, 9.0], aligns=[L, C, L], bold_first_col=True)
    caption(doc, "표 7. 비율이 아닌 산출물들.")

    h2(doc, "4.6", "업종 추천 성능의 정직한 해석")
    body(doc,
         "Top-3 91.7% 는 그 자체로는 강한 수가 아니다. 같은 거점의 사전분포 — 그 거점에서 흔한 업종을 "
         "빈도순으로 그냥 찍었을 때 — 가 89.3% 이기 때문이다. 두 수의 산술 차이는 2.4%p 다. "
         "Top-3 만 떼어 91.7% 라고 제시하면 실제보다 크게 들린다.")
    body(doc,
         "모델의 기여가 실제로 드러나는 지점은 Top-1 이다. 사전분포 대비 Top-1 lift 5.3% — "
         "'가장 먼저 무엇을 넣을 것인가'라는, 실제로 돈이 걸리는 질문에서 사전분포보다 낫다. "
         "출점 의사결정은 Top-3 중 아무거나 고르는 일이 아니라 Top-1 을 고르는 일이므로, "
         "우리는 Top-1 을 개선 지표로 잡고 Top-3 은 참고값으로만 둔다.")
    note_box(doc, [
        ("이 절을 남겨 두는 이유", True),
        ("Top-3 91.7% 만 적고 사전분포 89.3% 를 적지 않는 자료를 만들 수도 있었다. 그러면 실사에서 "
         "그 한 줄이 나머지 모든 수의 신뢰도를 같이 깎는다. 4.2의 앵커 격차도, 이 절의 사전분포도 "
         "같은 이유로 본문에 있다.", False),
    ], fill="F1F5F9", border=NAVY)


def sec5(doc):
    h1(doc, "5", "비즈니스 모델")

    h2(doc, "5.1", "파는 것과 가격")
    body(doc,
         "DaaS(Data as a Service) — B2B 구독, 월 500만원. 파는 것은 리포트 한 건이 아니라 접근권이다. "
         "66거점 전수 인벤토리, 4레이어 히트맵, 업종 추천, 그리고 PPPP 네 트랙의 실행 산출물에 계속 접근한다.")
    body(doc,
         "왜 구독인가. 공실은 상태가 아니라 흐름이기 때문이다. 한 번 찍은 스냅샷은 곧 낡는다. "
         "고객이 사는 것은 '지금 비어 있는 자리 목록'이 아니라 '계속 갱신되는 인벤토리'다. "
         "664유닛이라는 수 자체보다, 그 수가 매번 다시 실측된 값이라는 점이 구독의 근거다. "
         "갱신 주기와 그때의 단위원가는 [측정 필요] 이며, 6장에서 그 측정을 계획에 넣었다.")

    h2(doc, "5.2", "고객군")
    make_table(doc, [
        ["고객", "사는 이유", "주로 쓰는 트랙"],
        ["프랜차이즈 본사", "출점 후보 스크리닝 — 답사 전에 후보를 건물·층 단위로 좁힌다",
         "Page → Platform"],
        ["자산운용사", "보유 자산의 공실 관리와 주변 비교 — 왜 안 나가는지, 무엇을 넣어야 하는지",
         "Page → Posting"],
        ["지자체", "상권 활성화와 빈 점포 매칭 — 어떤 상권인지 읽고 무엇으로 돌릴지",
         "Platform → Program"],
    ], [3.2, 9.3, 3.7], sizes=[9.0, 9.0, 9.0], aligns=[L, L, L], bold_first_col=True)
    caption(doc, "표 8. 세 고객군 모두 같은 데이터를 다른 트랙으로 쓴다. 트랙이 늘어날 때마다 "
                 "같은 데이터의 재판매 면적이 넓어지는 구조다.")

    h2(doc, "5.3", "6개월 파일럿의 산술")
    body(doc,
         "6개월차 목표는 B2B 파일럿 5~10건이다. 공표 가격을 그대로 곱한 산술은 다음과 같다.")
    make_table(doc, [
        ["시나리오", "계약 수", "월 구독료", "월 환산", "연 환산"],
        ["하한", "5건", "500만원", "2,500만원", "3.0억원"],
        ["상한", "10건", "500만원", "5,000만원", "6.0억원"],
    ], [3.0, 2.8, 3.2, 3.4, 3.8], sizes=[9.0, 9.0, 9.0, 9.0, 9.0],
        aligns=[L, C, C, C, C], bold_first_col=True)
    caption(doc, "표 9. 목표 계약 수 × 공표 가격의 단순 산술. 실제 매출은 계약 시점, 할인, 유지율에 따라 "
                 "달라지며 이 표는 그 변수를 반영하지 않았다.")
    body(doc,
         "이 표는 예측이 아니라 산술이다. 목표 계약 수와 공표 가격이라는 두 개의 주어진 값을 곱한 것 이상이 "
         "아니며, 그 사실을 표 아래에 그대로 적어 두었다. 6개월 뒤 이 표의 자리에는 실제 계약 데이터가 들어온다.")

    h2(doc, "5.4", "아직 재지 않은 칸")
    body(doc,
         "단위 경제성을 구성하는 값들은 아직 재지 않았다. 여기에 업계 평균이나 벤치마크를 넣지 않는다. "
         "파일럿 5~10건은 바로 이 칸들을 채우기 위한 설계다.")
    make_table(doc, [
        ["항목", "상태", "언제 재는가"],
        ["CAC(고객 획득 비용)", "[측정 필요]", "파일럿 영업 실적"],
        ["유료 전환율 / 이탈률", "[측정 필요]", "파일럿 종료 후 갱신 시점"],
        ["계약당 실단가(할인 후)", "[측정 필요]", "첫 계약 체결"],
        ["매출총이익률", "[측정 필요]", "데이터 수집 단위원가 확정 후"],
        ["거점 1개 유지 단위원가", "[측정 필요]", "인벤토리 갱신 주기 확립 후"],
    ], [5.2, 4.0, 7.0], sizes=[9.0, 9.0, 9.0], aligns=[L, L, L], bold_first_col=True)
    caption(doc, "표 10. 이 다섯 칸이 채워지기 전까지 이 사업의 단위 경제성은 주장할 수 없다. "
                 "주장하지 않는 쪽을 택했다.")


def sec6(doc):
    h1(doc, "6", "로드맵")
    body(doc,
         "로드맵의 단위는 기간이 아니라 통과 조건이다. '몇 개월에 무엇을 한다'가 아니라 "
         "'무엇이 산출물로 나와야 다음으로 넘어간다'로 적었다.")
    make_table(doc, [
        ["구간", "하는 일", "통과 조건(산출물)"],
        ["T0 — 현재\n2026.09", "서울 66거점 Tier1 실측 완료 · 664유닛 인벤토리 · "
                              "4레이어 히트맵 · 업종 추천 v1", "!완료"],
        ["T0 ~ 6개월", "B2B 파일럿 체결 및 운영", "계약 5~10건"],
        ["", "앵커 격차 분해 — 모수 차이 몫과 정의 차이 몫을 각각 %p 로 가른다",
         "3개 거점 이상에서 분해 수치 산출"],
        ["", "업종 추천 Top-1 개선(사전분포 대비 lift 를 지표로 둔다)",
         "[측정 필요] 목표 lift 는 파일럿 요구 수준 확인 후 확정"],
        ["", "인벤토리 갱신 주기 확립 — 664유닛을 사람 손 없이 다시 재는 상태",
         "[측정 필요] 갱신 1회 소요 시간·단위원가"],
        ["6개월 이후", "거점·도시 확장",
         "[측정 필요] 확장 대상과 목표 거점 수 — 어느 고객군이 먼저 붙는지 확인한 뒤 정한다"],
    ], [3.0, 7.2, 6.2], sizes=[8.8, 8.8, 8.8], aligns=[L, L, L], bold_first_col=True)
    caption(doc, "표 11. 확장 목표를 지금 숫자로 못 박지 않았다. 파일럿에서 어느 고객군이 먼저 붙는지에 따라 "
                 "확장 방향(거점 밀도 vs 도시 수)이 갈리기 때문이다.")

    h2(doc, "6.1", "왜 확장 숫자를 먼저 적지 않는가")
    body(doc,
         "'12개월 내 몇 개 도시'라는 문장은 쓰기 쉽고, 이 문서에서도 쓸 수 있었다. 쓰지 않은 이유는 "
         "확장의 방향이 아직 데이터로 정해지지 않았기 때문이다. 프랜차이즈 본사가 먼저 붙으면 "
         "출점 후보가 있는 도시로 넓게 가야 하고, 자산운용사가 먼저 붙으면 이미 자산이 몰린 지역의 거점 밀도를 "
         "높여야 한다. 두 방향은 수집 비용도 우선순위도 다르다. "
         "파일럿 5~10건의 진짜 산출물은 매출이 아니라 이 갈림길의 답이다.")

    h2(doc, "6.2", "진행률을 세는 방식")
    body(doc,
         "PlaceOS 는 진행률을 문서가 아니라 산출물로 센다. 거점 하나가 '완료'라는 말은 건축물대장 실측이 "
         "끝나고 앵커 대조까지 돌았다는 뜻이며, 그 판정은 사람의 보고가 아니라 저장소의 상태 스크립트가 낸다. "
         "표 11의 '통과 조건' 열이 그 판정 기준과 같은 것이다. "
         "이 방식이 66거점 전부를 같은 방법으로 실측된 상태로 유지시킨 장치이기도 하다.")


def sec7(doc):
    h1(doc, "7", "팀")

    h2(doc, "7.1", "현재 구성")
    body(doc,
         "창업자 sh.pac 1인 체제다. 디지털 트윈 AI/IT 개발자로서 데이터 수집 파이프라인, 공실 예측·업종 추천 "
         "모델, 백엔드 API, 지도·거리뷰 프론트엔드까지 하나의 저장소 안에서 직접 만든다. "
         "4장의 실측 산출물 — 66거점 Tier1, 664유닛 인벤토리, 4레이어 히트맵, 업종 추천 — 은 모두 이 체제에서 나왔다.")

    h2(doc, "7.2", "1인 체제가 66거점을 낸 방식")
    body(doc,
         "바이브 코딩 — 자연어로 쓴 명세를 AI 코딩 도구가 코드로 만들고, 사람이 검증하는 사이클이다. "
         "설계와 근거 판단은 사람이 하고, 명세가 확정된 실행은 에이전트가 맡는다. "
         "이 방식 덕분에 인력 규모와 산출물 규모가 통상적인 비례 관계를 따르지 않는다. "
         "동시에 이것이 다음 항의 공백을 설명하기도 한다 — 코드로 풀리는 일과 사람이 붙어야 하는 일이 나뉜다.")

    h2(doc, "7.3", "공백과 채용")
    make_table(doc, [
        ["공백", "왜 필요한가", "언제"],
        ["B2B 세일즈 · CS", "파일럿 5~10건은 코드로 붙지 않는다. 6장 로드맵의 첫 통과 조건이 "
                           "곧 이 자리의 존재 이유다", "즉시"],
        ["데이터 엔지니어링", "664유닛 인벤토리를 사람 손 없이 갱신되는 상태로 만드는 일. "
                            "구독 모델의 전제 조건이다", "갱신 주기 확립 시점"],
        ["부동산 도메인 자문", "4.3의 정의 차이 분해와 고객사 계약 데이터 해석에 도메인 판단이 필요하다",
         "파일럿 계약 데이터 수령 시점"],
    ], [3.4, 9.4, 3.4], sizes=[9.0, 9.0, 9.0], aligns=[L, L, L], bold_first_col=True)
    caption(doc, "표 12. 채용 규모·보상·지분은 [측정 필요] — 투자 조건 확정 후 산정한다.")

    h2(doc, "7.4", "이 문서를 쓴 방식에 대해")
    body(doc,
         "이 기획안에는 시장 규모도, 경쟁사 밸류에이션도, 3개년 매출 추정도 없다. 쓸 수 있었지만 쓰지 않았다. "
         "이 문서에 적힌 수는 전부 우리가 직접 잰 것이고, 재지 않은 것은 [측정 필요] 로 남겼다. "
         "부록 A 의 목록이 그 결과다.")
    body(doc,
         "팀이 하나뿐인 회사에서 투자자가 볼 수 있는 것은 결국 그 한 사람이 무엇을 어떻게 재는가다. "
         "4.2에서 우리에게 불리한 격차를 먼저 놓고, 4.6에서 91.7% 옆에 89.3% 를 나란히 적은 것이 "
         "그 답이 되기를 바란다.")


def appendix(doc):
    p = para(doc, before=0, after=0)
    run(p, "").add_break(WD_BREAK.PAGE)
    h1(doc, "부록 A", "수치 출처와 [측정 필요] 목록")

    table_title(doc, "A-1. 본문에 쓴 실측 수치")
    make_table(doc, [
        ["수치", "값", "쓰인 곳"],
        ["거점 커버리지", "서울 66거점 전부 Tier1(건축물대장 실측)", "2.2 · 4.1 · 5.1"],
        ["연남동", "노출 1,133동 · 대표공실 12.5% · 앵커 5.0% · 격차 +7.5%p", "1.1 · 4.1 · 4.4"],
        ["신촌·이대", "노출 1,443동 · 대표공실 17.2% · 앵커 11.68% · 격차 +5.52%p", "1.1 · 4.1 · 4.4"],
        ["홍대", "노출 1,325동 · 대표공실 15.0% · 앵커 8.1% · 격차 +6.9%p", "1.1 · 4.1 · 4.4"],
        ["공실 유닛 인벤토리", "66/66 거점 · 664유닛", "2.1 · 2.2 · 4.5 · 5.1"],
        ["히트맵", "4레이어(공실·임대·유동·밀도) · 동일 100m 격자", "2.2 · 4.5"],
        ["업종 추천", "Top-3 91.7% · 거점 사전분포 89.3% · Top-1 lift 5.3%", "3.1 · 4.5 · 4.6"],
        ["가격", "DaaS 월 500만원 B2B 구독", "5.1 · 5.3"],
        ["파일럿 목표", "6개월차 5~10건", "5.3 · 6장"],
    ], [3.4, 9.0, 3.8], sizes=[8.8, 8.8, 8.8], aligns=[L, L, L], bold_first_col=True)
    caption(doc, "본문의 2.4%p(=91.7−89.3), 2,500만원·5,000만원·3.0억·6.0억(=계약 수×500만원)은 "
                 "위 값들만으로 계산한 산술이며 새로 측정한 값이 아니다.")

    table_title(doc, "A-2. [측정 필요] 전체 목록")
    make_table(doc, [
        ["항목", "본문 위치", "측정 계기"],
        ["출점 1건당 실사 비용·기간, 실사 판단 적중률", "1.3", "파일럿 고객사 실적"],
        ["Posting 회수기간 예측의 사후 오차", "3.3", "실제 입점 후 성과 대조"],
        ["Program 홍보안 채택률·성과", "3.4", "파일럿 운영"],
        ["앵커 격차 중 정의 차이가 설명하는 몫(%p)", "4.3", "파일럿 계약 데이터 분해"],
        ["거점을 늘렸을 때 부호 일치·서열 보존 유지 여부", "4.4", "앵커 대조 거점 확대"],
        ["업종 추천과 실제 출점 후 생존의 상관", "3.1 · 4.6", "파일럿 이후 추적"],
        ["CAC · 유료 전환율 · 이탈률 · 실단가 · 매출총이익률", "5.4", "파일럿 영업 및 갱신"],
        ["인벤토리 갱신 주기 · 갱신 1회 단위원가", "5.1 · 6장", "갱신 자동화 완료 시"],
        ["확장 대상 지역과 목표 거점 수", "6장 · 6.1", "파일럿 고객군 확인 후"],
        ["채용 규모 · 보상 · 지분", "7.3", "투자 조건 확정 후"],
    ], [7.4, 3.0, 5.8], sizes=[8.8, 8.8, 8.8], aligns=[L, L, L], bold_first_col=True)

    p = para(doc, before=14, after=0, line=1.5)
    para_border(p, ("top",), color=RULE, sz=6, space=8)
    run(p, "이 목록이 짧아지는 속도가 곧 PlaceOS 의 진행 속도다.", size=9.5, bold=True, color=NAVY)


def build_document(out_path: Path) -> Path:
    doc = Document()
    sec = setup(doc)
    add_footer(sec, "PlaceOS 사업 기획안 · 투자자용")
    cover(doc)
    sec0(doc)
    sec1(doc)
    sec2(doc)
    sec3(doc)
    sec4(doc)
    sec5(doc)
    sec6(doc)
    sec7(doc)
    appendix(doc)
    doc.save(out_path)
    return out_path


# ══════════════════════════════════════════════════════════════════════════
#  한글 폰트 임베딩 (ECMA-376 Part1 §17.8 — 이게 없으면 뷰어에서 □ 로 깨진다)
# ══════════════════════════════════════════════════════════════════════════
CT_OBFUSCATED = "application/vnd.openxmlformats-officedocument.obfuscatedFont"
REL_FONT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def fetch_fonts(cache: Path) -> dict[str, Path]:
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    for style, url in FONT_URLS.items():
        dest = cache / f"NotoSansKR-{style}.ttf"
        if not dest.exists() or dest.stat().st_size < 100_000:
            print(f"  · 내려받는 중: {dest.name}")
            subprocess.run(["curl", "-sS", "-L", "-o", str(dest), url], check=True)
        out[style] = dest
    return out


def used_chars(docx_path: Path) -> set[str]:
    """문서에 실제로 쓰인 글자만 모은다(subset 대상)."""
    chars: set[str] = set()
    with zipfile.ZipFile(docx_path) as z:
        for name in z.namelist():
            if not name.endswith(".xml"):
                continue
            if not (name.startswith("word/") or name == "docProps/core.xml"):
                continue
            xml = z.read(name).decode("utf-8", "ignore")
            for m in re.finditer(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S):
                chars.update(m.group(1))
    return chars


def subset_font(src: Path, dest: Path, chars: set[str]) -> None:
    from fontTools import subset as ftsubset

    keep = set(chars)
    keep.update(" 0123456789.,%()[]-–—·/:;+~→▶'\"")
    keep.update("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    unicodes = sorted(ord(c) for c in keep if c.strip() or c == " ")

    opts = ftsubset.Options()
    opts.name_IDs = ["*"]
    opts.name_legacy = True
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.recalc_bounds = True
    opts.drop_tables = []
    opts.layout_features = ["*"]
    font = ftsubset.load_font(str(src), opts)
    subsetter = ftsubset.Subsetter(options=opts)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)
    ftsubset.save_font(font, str(dest), opts)
    font.close()


def obfuscate(data: bytes, guid: str) -> bytes:
    """ECMA-376 §17.8.1 — fontKey GUID 의 16바이트를 역순으로 만들어 앞 32바이트를 XOR."""
    h = guid.strip("{}").replace("-", "")
    key = bytes.fromhex(h)[::-1]
    out = bytearray(data)
    for i in range(32):
        out[i] ^= key[i % 16]
    return bytes(out)


def embed_fonts(docx_path: Path, fonts: dict[str, Path], workdir: Path) -> None:
    chars = used_chars(docx_path)
    print(f"  · 문서에 쓰인 고유 글자 {len(chars)}자 → subset")

    guids = {}
    payloads = {}
    for style, src in fonts.items():
        sub = workdir / f"subset-{style}.ttf"
        subset_font(src, sub, chars)
        guid = "{" + str(uuid.uuid4()).upper() + "}"
        guids[style] = guid
        payloads[style] = obfuscate(sub.read_bytes(), guid)
        print(f"  · {style}: {src.stat().st_size:,}B → subset {sub.stat().st_size:,}B → odttf")

    font_table = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:fonts xmlns:w="{W_NS}" xmlns:r="{R_NS}">'
        f'<w:font w:name="{FONT}">'
        '<w:panose1 w:val="020B0500000000000000"/>'
        '<w:charset w:val="81"/>'
        '<w:family w:val="swiss"/>'
        '<w:pitch w:val="variable"/>'
        '<w:sig w:usb0="800002A7" w:usb1="49DF7C10" w:usb2="00000012"'
        ' w:usb3="00000000" w:csb0="6017009F" w:csb1="00000000"/>'
        f'<w:embedRegular r:id="rIdFontR" w:fontKey="{guids["regular"]}" w:subsetted="1"/>'
        f'<w:embedBold r:id="rIdFontB" w:fontKey="{guids["bold"]}" w:subsetted="1"/>'
        '</w:font>'
        '</w:fonts>'
    ).encode("utf-8")

    font_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rIdFontR" Type="{REL_FONT}" Target="fonts/font_regular.odttf"/>'
        f'<Relationship Id="rIdFontB" Type="{REL_FONT}" Target="fonts/font_bold.odttf"/>'
        '</Relationships>'
    ).encode("utf-8")

    tmp_out = workdir / "embedded.docx"
    with zipfile.ZipFile(docx_path) as zin, \
         zipfile.ZipFile(tmp_out, "w", zipfile.ZIP_DEFLATED) as zout:
        names = zin.namelist()

        for name in names:
            data = zin.read(name)

            if name == "[Content_Types].xml":
                xml = data.decode("utf-8")
                if "odttf" not in xml:
                    xml = xml.replace(
                        "<Types ", "<Types ", 1)
                    ins = f'<Default Extension="odttf" ContentType="{CT_OBFUSCATED}"/>'
                    idx = xml.index(">", xml.index("<Types")) + 1
                    xml = xml[:idx] + ins + xml[idx:]
                data = xml.encode("utf-8")

            elif name == "word/settings.xml":
                xml = data.decode("utf-8")
                if "embedTrueTypeFonts" not in xml:
                    flags = "<w:embedTrueTypeFonts/><w:saveSubsetFonts/>"
                    # CT_Settings 순서상 zoom 뒤 · defaultTabStop 앞이면 안전하다.
                    anchor = None
                    for tag in ("<w:zoom", "<w:view", "<w:writeProtection"):
                        if tag in xml:
                            anchor = tag
                    if anchor:
                        i = xml.index(anchor)
                        j = xml.index(">", i) + 1
                        if xml[j - 2] != "/":            # 여는 태그면 닫는 태그까지 건너뛴다
                            close = "</" + anchor[1:].split(" ")[0] + ">"
                            j = xml.index(close, j) + len(close)
                        xml = xml[:j] + flags + xml[j:]
                    else:
                        i = xml.index(">", xml.index("<w:settings")) + 1
                        xml = xml[:i] + flags + xml[i:]
                data = xml.encode("utf-8")

            elif name == "word/fontTable.xml":
                data = font_table

            elif name == "word/_rels/fontTable.xml.rels":
                continue  # 아래에서 새로 쓴다

            zout.writestr(name, data)

        if "word/fontTable.xml" not in names:
            zout.writestr("word/fontTable.xml", font_table)
        zout.writestr("word/_rels/fontTable.xml.rels", font_rels)
        zout.writestr("word/fonts/font_regular.odttf", payloads["regular"])
        zout.writestr("word/fonts/font_bold.odttf", payloads["bold"])

    shutil.move(tmp_out, docx_path)


def verify_embedding(docx_path: Path) -> None:
    """임베딩이 실제로 들어갔는지 구조로 확인한다(렌더러에 의존하지 않는 검증)."""
    with zipfile.ZipFile(docx_path) as z:
        names = z.namelist()
        assert "word/fonts/font_regular.odttf" in names, "odttf 누락"
        assert "word/fonts/font_bold.odttf" in names, "bold odttf 누락"
        ct = z.read("[Content_Types].xml").decode()
        assert CT_OBFUSCATED in ct, "Content_Types 에 obfuscatedFont 없음"
        st = z.read("word/settings.xml").decode()
        assert "embedTrueTypeFonts" in st, "settings.xml 에 embedTrueTypeFonts 없음"
        ft = z.read("word/fontTable.xml").decode()
        assert "embedRegular" in ft and "embedBold" in ft, "fontTable 배선 없음"
        rels = z.read("word/_rels/fontTable.xml.rels").decode()
        assert "font_regular.odttf" in rels, "fontTable rels 누락"
        drels = z.read("word/_rels/document.xml.rels").decode()
        assert "fontTable.xml" in drels, "document.xml.rels 에 fontTable 관계 없음"

        # 난독 해제 시 유효한 TTF 인지(sfnt 매직 확인)
        key = re.search(r'w:embedRegular[^/]*w:fontKey="\{([0-9A-F-]+)\}"', ft).group(1)
        raw = obfuscate(z.read("word/fonts/font_regular.odttf"), key)
        magic = struct.unpack(">I", raw[:4])[0]
        assert magic in (0x00010000, 0x4F54544F, 0x74727565), f"복호 후 sfnt 아님: {magic:#x}"
    print("  ✅ 임베딩 구조 검증 통과 (odttf · fontTable · rels · settings · Content_Types)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="PlaceOS_사업기획안_투자자용.docx")
    ap.add_argument("--fonts", default=None, help="폰트 캐시 디렉터리(기본: 임시 디렉터리)")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        cache = Path(args.fonts).resolve() if args.fonts else work / "fonts"
        print("1) 문서 생성")
        build_document(out)
        print(f"   → {out.name} ({out.stat().st_size:,}B)")
        print("2) 한글 폰트 임베딩")
        embed_fonts(out, fetch_fonts(cache), work)
        print(f"   → {out.name} ({out.stat().st_size:,}B)")
        print("3) 검증")
        verify_embedding(out)
    print(f"\n완료: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
