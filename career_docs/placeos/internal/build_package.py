"""작성된 Markdown만 PDF와 제한된 ZIP으로 변환한다. 제품 데이터는 포함하지 않는다."""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import sys
import zipfile

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / ".build/deps"))
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
import pymupdf as fitz

DOCUMENTS = ["03_placeos_portfolio", "04_technical_brief", "05_application_draft",
             "05a_korea_mot_application", "05b_yonsei_anchor_worksheet",
             "05c_yonsei_uif_worksheet", "08_graduate_research_plan"]

PACKAGE_SPECS = {
    "placeos_career_review": DOCUMENTS[:-1],
    "placeos_korea_career_review": ["03_placeos_portfolio", "04_technical_brief", "05a_korea_mot_application"],
    "placeos_yonsei_anchor_review": ["05b_yonsei_anchor_worksheet"],
    "placeos_yonsei_uif_review": ["05c_yonsei_uif_worksheet"],
    "placeos_research_preparation": ["04_technical_brief", "08_graduate_research_plan"],
}

def inline(text: str) -> str:
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<link href="\2" color="#254f6e">\1</link>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    return re.sub(r"`([^`]+)`", r"\1", text)

def styles() -> dict:
    pdfmetrics.registerFont(TTFont("Korean", "C:/Windows/Fonts/malgun.ttf"))
    pdfmetrics.registerFont(TTFont("KoreanBold", "C:/Windows/Fonts/malgunbd.ttf"))
    pdfmetrics.registerFontFamily("Korean", normal="Korean", bold="KoreanBold", italic="Korean", boldItalic="KoreanBold")
    base = dict(fontName="Korean", fontSize=10, leading=16, wordWrap="CJK", alignment=TA_LEFT)
    return {
        "body": ParagraphStyle("body", **base, spaceAfter=9),
        "title": ParagraphStyle("title", fontName="KoreanBold", fontSize=23, leading=31, textColor=colors.black, spaceAfter=17, wordWrap="CJK"),
        "h2": ParagraphStyle("h2", fontName="KoreanBold", fontSize=13, leading=20, textColor=colors.HexColor("#7b2536"), spaceBefore=9, spaceAfter=7, keepWithNext=True, wordWrap="CJK"),
        "table": ParagraphStyle("table", fontName="Korean", fontSize=8.7, leading=13, wordWrap="CJK"),
        "code": ParagraphStyle("code", fontName="Korean", fontSize=9, leading=15, wordWrap="CJK", spaceAfter=9, backColor=colors.HexColor("#f4f5f7"), borderPadding=9),
    }

def build_pdf(name: str, st: dict) -> None:
    st = {k: v.clone(k + "_" + name) for k, v in st.items()}
    if name.startswith(("04", "05c", "08")):
        st["body"].fontSize = 9.5
        st["body"].leading = 15
        st["body"].spaceAfter = 7
        st["h2"].spaceBefore = 7
        st["h2"].spaceAfter = 6
        st["code"].leading = 13.5
        st["table"].fontSize = 8.5
        st["table"].leading = 12.5
    if name.startswith("08"):
        st["body"].leading = 14
        st["body"].spaceAfter = 5
        st["h2"].spaceBefore = 5
        st["h2"].spaceAfter = 4
    lines = (BASE / f"{name}.md").read_text(encoding="utf-8").splitlines()
    title = lines[0].lstrip("# ")
    story = []
    width = A4[0] - 100
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line == "<!-- PAGEBREAK -->":
            story.append(PageBreak())
        elif line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), st["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), st["h2"]))
        elif line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(inline(lines[i]))
                i += 1
            story.append(Paragraph("<br/>".join(block), st["code"]))
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", c) for c in cells):
                    rows.append([Paragraph(inline(c), st["table"]) for c in cells])
                i += 1
            i -= 1
            n = len(rows[0])
            weights = {3:[0.19,0.42,0.39], 4:[0.19,0.24,0.42,0.15]}.get(n, [1/n]*n)
            table = Table(rows, colWidths=[width*w for w in weights], repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0,0),(-1,0), colors.HexColor("#eceff2")),
                ("VALIGN", (0,0),(-1,-1),"TOP"),
                ("LEFTPADDING", (0,0),(-1,-1),7), ("RIGHTPADDING", (0,0),(-1,-1),7),
                ("TOPPADDING", (0,0),(-1,-1),6), ("BOTTOMPADDING", (0,0),(-1,-1),6),
                ("LINEBELOW", (0,0),(-1,0),0.7,colors.HexColor("#b6bec8")),
                ("LINEBELOW", (0,1),(-1,-1),0.3,colors.HexColor("#d8dce2")),
            ]))
            story.extend([table, Spacer(1,12)])
        else:
            block = [line]
            while i+1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(("#", "|", "```", "<!--", "- ")):
                i += 1
                block.append(lines[i].strip())
            story.append(Paragraph(inline(" ".join(block)), st["body"]))
        i += 1
    def page(canvas, doc):
        canvas.setTitle(title)
        canvas.setAuthor("")
        canvas.setSubject("검토용 초안 - 확인되지 않은 개인 정보와 공고 요건은 작성 필요로 표시")
        canvas.setFont("Korean", 8)
        canvas.setFillColor(colors.HexColor("#68707c"))
        canvas.drawString(50, A4[1]-32, "PlaceOS  |  연구 준비" if name.startswith("08") else "PlaceOS  |  채용 검토")
        canvas.drawString(50, 28, "검토용 초안 · 2026-09-25")
        canvas.drawRightString(A4[0]-50, 28, str(doc.page))
    doc = SimpleDocTemplate(str(BASE / "pdf" / f"{name}.pdf"), pagesize=A4,
                            leftMargin=50, rightMargin=50, topMargin=55, bottomMargin=50,
                            title=title, author="")
    doc.build(story, onFirstPage=page, onLaterPages=page)

def render_and_check() -> dict:
    qa = {}
    renders = BASE / ".build/renders"
    renders.mkdir(parents=True, exist_ok=True)
    for name in DOCUMENTS:
        doc = fitz.open(BASE / "pdf" / f"{name}.pdf")
        pages = []
        for index, p in enumerate(doc):
            text = p.get_text()
            outside = []
            for b in p.get_text("blocks"):
                if b[0] < 35 or b[1] < 15 or b[2] > p.rect.width-35 or b[3] > p.rect.height-15:
                    outside.append([round(x,2) for x in b[:4]])
            png = renders / f"{name}-{index+1:02d}.png"
            p.get_pixmap(matrix=fitz.Matrix(1.3,1.3), alpha=False).save(png)
            pages.append({"page": index+1, "characters": len(text),
                          "replacement_character": "\ufffd" in text,
                          "outside_safe_bounds": outside})
        qa[name] = {"pages": len(doc), "checks": pages, "visual_review": "렌더링 후 확인 필요"}
    return qa

def make_zips() -> None:
    specs = PACKAGE_SPECS
    for name, docs in specs.items():
        career = "research" not in name
        notice = ("# 채용 개인 검토용 패키지\n\n추가자료 허용은 미확인입니다. 연세대 채용 전형은 AI 사용 금지 공지가 있어 "
                  "본인 작성표만 준비했고 AI 생성 문장의 제출을 권하지 않습니다. 앵커사업단 별도 이메일 채용의 적용 범위는 확인이 필요합니다. "
                  "고려대 초안은 공식 문항·분량 미확인입니다. [작성 필요]와 자격·접수 조건을 확인하십시오. "
                  "자동 제출하지 않았으며 원자료·인증정보·내부 근거표·공식 HWP는 포함하지 않았습니다.\n"
                  if career else
                  "# 별도 연구 준비 패키지\n\n채용 제출물과 별개입니다. 연구계획은 제안이며 입학·학위·학비 지원·근무시간 조정은 보장하지 않습니다. "
                  "현장 공실 정확도·추천의 사업효과는 검증하지 않았습니다. 원자료와 내부 근거표는 포함하지 않았습니다.\n")
        file_map = {f"{d}.md": BASE/f"{d}.md" for d in docs}
        file_map.update({f"pdf/{d}.pdf": BASE/"pdf"/f"{d}.pdf" for d in docs})
        manifest = [{"path": "00_README.md", "sha256": hashlib.sha256(notice.encode()).hexdigest()}]
        manifest.extend({"path": arc, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for arc,p in file_map.items())
        content = json.dumps(manifest, ensure_ascii=False, indent=2)
        path = BASE / "release" / f"{name}.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("00_README.md", notice)
            for arc, p in file_map.items():
                z.write(p, arc)
            z.writestr("manifest.json", content)
        (BASE / "release" / f"{name}.manifest.json").write_text(content, encoding="utf-8")

def main() -> None:
    (BASE/"pdf").mkdir(exist_ok=True)
    (BASE/"release").mkdir(exist_ok=True)
    st = styles()
    for name in DOCUMENTS:
        build_pdf(name, st)
    qa = render_and_check()
    (BASE / "internal/pdf_qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    make_zips()
    print(json.dumps({k:v["pages"] for k,v in qa.items()}, ensure_ascii=False))

if __name__ == "__main__":
    main()
