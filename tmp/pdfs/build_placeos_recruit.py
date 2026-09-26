from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
import fitz

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf/PlaceOS_채용용_연구요약.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun', normal='Malgun', bold='MalgunBold')
W, H = 595.28, 841.89
INK, MUTED, TEAL, BG = map(HexColor, ['#18272D', '#5E6868', '#176B63', '#F1EFE8'])
PAPER, RULE = map(HexColor, ['#FCFBF7', '#D8D4C8'])
c = canvas.Canvas(str(OUT), pagesize=(W, H))
c.setTitle('PlaceOS 채용용 연구 요약')
c.setAuthor('박석현')

def text(s, x, y, width=499, size=11, color=INK, bold=False):
    style = ParagraphStyle('body', fontName='MalgunBold' if bold else 'Malgun', fontSize=size,
                           leading=size*1.62, textColor=color, wordWrap='CJK')
    p = Paragraph(s, style)
    _, height = p.wrap(width, 1000)
    p.drawOn(c, x, H-y-height)
    return y+height

def box(x, y, w, h, fill=BG):
    c.setFillColor(fill)
    c.roundRect(x, H-y-h, w, h, 2, fill=1, stroke=0)

def start(n, label, title, subtitle):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(TEAL)
    c.rect(0, 0, 13, H, fill=1, stroke=0)
    text('PlaceOS  /  RESEARCH NOTE', 48, 31, size=8.5, color=TEAL, bold=True)
    text(label, 48, 67, size=9.5, color=MUTED)
    text(title, 48, 94, size=23, bold=True)
    text(subtitle, 48, 142, size=10.2, color=MUTED)
    c.setStrokeColor(RULE)
    c.line(48, 53, W-48, 53)
    text('연구 초안 기반 · 논문 수정 2026.09.20 · 요약 편집 2026.09.26', 48, 801, size=8, color=MUTED)
    text(f'{n} / 5', W-81, 801, width=40, size=8, color=MUTED)

def note(s, y=748):
    text(s, 48, y, size=8.2, color=MUTED)

start(1, '01  문제 정의와 PPPP', '상권 데이터에서 창업 검증까지',
      '공간 탐색, 입점 조건 비교, 실행 계획을 연결하는 디지털 트윈 SaaS 프로젝트')
text('하나의 화면보다, 연결된 판단 과정', 48, 204, size=15, bold=True)
text('상권을 고르는 일은 간단해 보이지만 실제로는 상권, 건물, 점포, 임대료 자료를 오가며 판단해야 한다. 자료마다 기준 시점과 관측 단위가 다르고, 계산된 공실과 실제 임대 가능 호실이 같은 뜻도 아니다. PlaceOS는 이 차이를 숨기지 않고, 입지 탐색에서 사업 가설 검증까지 하나의 흐름으로 묶었다.', 48, 239)
rows = [
 ('Place → Platform', '어떤 상권인가', '상권 맥락과 업종 후보를 검토한다. GNN 분류 결과는 거점 기준선과 함께 해석한다.'),
 ('Product → Page', '어떤 공간을 선택할까', '지도·공실 히트맵·층별 목록·거리뷰로 후보를 탐색하고, 행정자료의 파생값과 현장 관측을 구분한다.'),
 ('Price → Posting', '어떤 조건으로 입점할까', '임대료·면적·권리금 입력을 바탕으로 비용과 회수기간 시나리오를 비교한다.'),
 ('Promotion → Program', '어떤 검증 활동을 할까', '창업 브리프를 온라인·오프라인 활동과 측정 지표, 목표선, 기각 조건으로 구체화한다.'),
]
for i, (name, q, desc) in enumerate(rows):
    y = 333+i*85
    box(48,y,499,75)
    text(name,62,y+10,170,size=11,color=TEAL,bold=True)
    text(q,62,y+34,170,size=10,bold=True)
    text(desc,238,y+12,292,size=10)
text('박석현  ·  제품 기획  |  AI 도구를 활용한 개발·연구 기록',48,693,size=11,bold=True)
note('구조: 저장소 PPPP 정의. 연구 내용: Platform·Page·Posting·Program 원고.\n학술지 게재 실적이나 실제 창업 성과를 주장하는 문서가 아니다.')
c.showPage()

start(2, '02  시스템 아키텍처', '데이터와 모델을 제품으로 연결',
      '원천 수집 → 공간·통계 가공 → 분석 산출물 → API → 의사결정 화면')
layers = [
 ('입력', '공공 행정·통계 및 민간 API', '건축물대장 · 상가정보 · 인허가 · 상권분석 · R-ONE · 생활인구 · 검색 트렌드'),
 ('가공', 'Bronze · Silver · Gold', '원본 보존 → 공간 키·속성 결합 → 공실 후보·수요 신호·서빙 산출물'),
 ('분석', 'GNN · LSTM · 비용 시나리오 · LLM', '업종 분류와 시계열 분석, 입력 가정별 비용 계산, 브리프 기반 검증 계획 생성'),
 ('서빙', 'FastAPI  /  Python', 'Gold·모델 결과 로딩 → 서비스 계산 → 출처·경고를 포함한 API 응답'),
 ('화면', 'React · TypeScript · Vite', '지도·건물 상세 · 입점 시나리오 · ProgramStudio'),
]
for i,(tag,title,desc) in enumerate(layers):
    y=201+i*89
    box(48,y,499,74)
    text(tag,62,y+22,51,size=11,color=TEAL,bold=True)
    text(title,125,y+9,404,size=12,bold=True)
    text(desc,125,y+34,400,size=9.5)
    if i<4:
        c.setStrokeColor(TEAL)
        c.line(298,H-y-76,298,H-y-86)
        c.line(294,H-y-82,298,H-y-86)
        c.line(302,H-y-82,298,H-y-86)
text('값만큼 중요한 것은 그 값의 출처다',48,666,size=14,bold=True)
text('API는 vacancy_source, inputs_source, basis를 함께 내보내 파생값과 사용자 입력을 구분한다. Program이 규칙을 어기면 대체안을 내고, 확인할 수 없는 내용은 경고와 함께 전달한다.',48,698,size=10.5)
note('계층은 설계 구조다. 자료 명세에는 일부 Bronze→Gold 직접 경로와 Gold→Gold 파생도 기록돼 있다.\n근거: 데이터 명세표, README, 논문 시스템 설계 및 PROGRAM-E01–E04.',758)
c.showPage()

start(3, '03  실제 데이터 출처와 검증', '출처와 검증 범위를 함께 관리',
      '원천이 제공하는 정보와 PlaceOS가 계산한 값을 분리해 해석한다')
data = [
 ('건축HUB · 소상공인 상가정보 · 서울 인허가', '건물·층·점포와 영업 상태를 결합해 수용량과 공실 대리값을 계산했다. 다만 이 값을 현장의 실제 공실이나 임대 가능 호실로 보지는 않았다.'),
 ('서울 상권분석 · 한국부동산원 R-ONE', '상권·분기 통계와 지역 임대료·공실률을 사용한다. 추정매출은 점포 장부 매출이 아니며, 지역 앵커는 호실 정답이 아니다.'),
 ('서울 생활인구 · Naver DataLab 및 검색 자료', '집계구·행정동 생활인구와 검색 관심을 공간 신호·생성 맥락에 반영한다. 셀 직접 계수나 점포 방문·매출로 해석하지 않는다.'),
 ('사용자 계약 입력 · 시드 및 계산 계수', '권리금과 창업 브리프는 사용자 입력이다. 미입력 전제, 파생 면적과 수기 계수 폴백을 관측값으로 표시하지 않는다.'),
]
for i,(title,desc) in enumerate(data):
    y=199+i*90
    text(title,48,y,size=12,bold=True,color=TEAL)
    text(desc,48,y+27,size=10.5)
text('어디까지 믿을 수 있는지 확인한 방법',48,573,size=15,bold=True)
for y,title,desc in [
 (611,'입력 식별','자료 목록·파일 해시·관측 단위·시점·분모로 실험 조건을 고정한다.'),
 (650,'계산 대조','고정 입력 반복, 셀 재합산, Gold→서빙 응답 비교와 순서 민감도를 나누어 검사한다.'),
 (689,'주장 검증','모델 기준선·동일 노드 쌍대 비교·계약 테스트를 사용하고, 기각과 미검증을 함께 기록한다.')]:
    text(title,48,y,85,size=10.5,bold=True)
    text(desc,140,y,407,size=10.5)
note('근거: data-specification.md; PAGE-D01–D12; PLATFORM-E01–E06; POSTING-E05; PROGRAM-E02–E06.\n원천 시점 정렬과 독립 현장 정답이 없어 현실 정확도는 별도 미검증으로 남긴다.',754)
c.showPage()

start(4, '04  주요 연구 결과', '통과한 검사와 남은 한계',
      '논문에 보존된 결과를 요약했으며, 이 PDF에서 실험을 다시 실행하지는 않았다')
box(48,194,499,162)
text('Platform  |  기준선과 함께 읽는 분류 성능',62,207,size=12,bold=True)
for y,label,val,col in [(244,'GNN Top-3',91.7,TEAL),(281,'거점 기준선 Top-3',89.4,HexColor('#94AAB5'))]:
    text(label,62,y,158,size=10)
    c.setFillColor(HexColor('#DCE6EA')); c.rect(228,H-y-19,230,14,fill=1,stroke=0)
    c.setFillColor(col); c.rect(228,H-y-19,230*val/100,14,fill=1,stroke=0)
    text(f'{val}%',474,y,60,size=11,bold=True)
text('조건 A · 2026.09.05 역사적 서빙본 66거점 · 47,442노드 · 현재 서빙 81거점',62,318,size=9,color=MUTED)
text('기존 업종 복원 결과이며 창업 성공률이 아니다. 현재 모델 성능과 구분한다.',48,367,size=10)
cards=[
 (405,'Page  |  동결본 66/66 재현 일치','조건 D · 2026.09.06 동결 자료(현재 서빙 81거점). 고정 입력을 반복하고 Gold와 서빙 응답을 대조했을 때 66거점 모두 일치했다. 다만 순서를 198회 바꾸는 검사에서는 65거점의 격자 소속 또는 분자·분모가 달라졌다.'),
 (514,'Posting  |  면적 계산과 현실 관측의 구분','2026.09.06 프로브의 664유닛 중 단일층 후보 30개에서 면적 계산 차이는 모두 0평이었다. 이는 두 계산의 일치이며 실제 호실 면적 정확도의 입증은 아니다.'),
 (623,'Program  |  계약 테스트 54 passed','2026.09.19 기록. 위반 시 대체안, 경고 시 출력 유지 등 고정 사례·목킹 계약 검사를 통과했다. 실제 LLM 사실성 위반율과 광고·창업 효과는 미측정이다.'),
]
for y,title,desc in cards:
    box(48,y,499,96)
    text(title,62,y+10,470,size=12,bold=True,color=TEAL)
    text(desc,62,y+38,470,size=10)
note('각 결과는 서로 다른 모집단·태스크다. 통합 성능으로 합산하지 않는다.\n근거: P1 조건 A; PAGE-D04·D05·D09; POSTING-E02; PROGRAM-E05.',751)
c.showPage()

start(5, '05  본인 기여도와 논문 원문', '기획과 개발을 연구 기록으로 정리',
      '프로젝트 역할과 구현 근거를 구분하고, 상세 판단은 원문으로 연결한다')
text('박석현  |  제품 기획',48,199,size=15,bold=True)
text('PlaceOS의 문제 정의와 PPPP 구조, 검증 기준을 설계했다.',48,237,size=12,bold=True)
text('개발은 Claude Code로 진행했고, 논문 초안을 정리할 때는 Codex를 활용했다. 제 역할은 제품 방향과 판단 기준을 세우는 일이었다. 이 문서는 모든 코드와 원고를 단독으로 수작업했다는 실적이 아니라, AI 도구를 활용해 프로젝트를 설계하고 검증한 과정을 보여준다.',48,298,size=10.5)
box(48,358,499,102)
text('프로젝트에서 설명할 수 있는 역량',62,370,size=12,bold=True,color=TEAL)
text('제품 기획: PPPP로 창업 의사결정 흐름 구조화<br/>데이터·시스템: 원천·가공·API·화면의 연결과 출처 관리<br/>연구 판단: 기준선 비교, 계산 재현, 기각 결과와 미측정 영역의 기록',62,398,470,size=10)
text('논문 원문',48,484,size=15,bold=True)
text('네 편 모두 참고문헌을 포함한 연구 초안이며 공개 URL은 없다. 아래는 이 PC의 원본 Word 파일 링크다. 외부 열람자는 이 링크에 접근할 수 없으므로 원문은 별도 파일로 제공해야 한다.',48,519,size=10)
titles=[
 ('Platform','거점 사전분포를 고려한 GNN 업종 분류의 성능 한계'),
 ('Page','공공행정자료 기반 공실 정보의 품질과 계산 재현성'),
 ('Posting','입점 시나리오의 관측 단위와 면적 소스 적격성'),
 ('Program','창업 검증 계획의 입력·출력 계약과 사실성 가드레일'),
]
for i,(name,title) in enumerate(titles):
    path=next((ROOT/'docs/papers/output').glob(f'PlaceOS_{name}_*.docx'))
    y=580+i*35
    text(f'<link href="{escape(path.as_uri())}" color="#087F83"><b>{name} 원문 열기</b></link>',48,y,145,size=10)
    text(title,195,y,352,size=9.5)
note('기여도 및 공개 상태: 박석현 본인 확인, 2026.09.26. 요약 PDF 편집: Codex 활용.\n원문 기준: output/제출목록.md 및 2026.09.20 수정본. 학술지 게재본이 아닌 연구 초안.',749)
c.showPage()
c.save()

# 검증: 페이지 수·필수 절·원문 링크·문자 범위와 렌더링 결과를 검사한다.
doc=fitz.open(OUT)
assert len(doc)==5
full='\n'.join(p.get_text() for p in doc)
for required in ['PPPP','시스템 아키텍처','데이터 출처','연구 결과','본인 기여도','논문 원문','91.7%','89.4%','54 passed']:
    assert required in full, required
assert sum(len(p.get_links()) for p in doc)==4
for i,p in enumerate(doc):
    for b in p.get_text('dict')['blocks']:
        if b['type']==0:
            assert b['bbox'][0]>=0 and b['bbox'][2]<=W+1 and b['bbox'][3]<=H, b['bbox']
    p.get_pixmap(matrix=fitz.Matrix(1.4,1.4)).save(ROOT/f'tmp/pdfs/placeos-page-{i+1}.png')
print(f'PASS: 5 pages, required content, 4 original links, page bounds; {OUT}')
