---
description: "서울 자치구 건물 단위 상권 세분화 HTML 생성 + 통합 파일 병합"
argument-hint: "<구 이름> <상권존1,상권존2,...> <중심위도,중심경도> <구색상hex>"
---

# District Map 생성·통합 커맨드

너는 지금 SpaceOS의 **서울 자치구 디지털 트윈 맵** 작업을 수행한다.

## 필수 선독(先讀) 파일

작업 전 반드시 읽어라.

```
html/Seoul/SpaceOS_Mapo_Building_Map.html          # 단일 구 파일 패턴 기준선
html/Seoul/SpaceOS_Jongno_Building_Map.html        # 단일 구 파일 패턴 기준선 (종로구)
html/Seoul/SpaceOS_Seoul_GangnamMapo_Building_Map.html  # 통합 파일 패턴 기준선
data/config/seoul_districts.py                     # 구 코드·base 점수·키워드 SSOT
```

## 인수 파싱

`$ARGUMENTS` 에서 다음을 추출한다.

| 인수 | 예시 | 설명 |
|------|------|------|
| 구 이름 | `용산구` | 한국어 자치구명 (필수) |
| 상권 존 목록 | `이태원,한남동,용리단길,한강진` | 쉼표 구분, 2~6개 (필수) |
| 중심 좌표 | `37.5385,126.9947` | 구 대표 중심점 (필수) |
| 구 색상 | `#f472b6` | 테두리·배지용 hex (없으면 아래 팔레트에서 자동 배정) |

인수가 부족하면 **즉시 질문**하고 작업을 시작하지 마라.

### 자동 색상 팔레트 (이미 사용된 색 제외 후 순서대로 배정)

```
이미 배정됨: 강남구 #f59e0b | 마포구 #34d399 | 종로구 #60a5fa
우선순위:    #f472b6(핑크) → #fb923c(오렌지) → #a78bfa(보라) → #4ade80(라임) → #e879f9(퍼플)
```

---

## STEP 1 — 개별 구 HTML 파일 생성

파일명: `html/Seoul/SpaceOS_{구영문명}_Building_Map.html`
(영문명 예: 용산구→Yongsan, 서초구→Seocho, 중구→Jung, 동대문구→Dongdaemun)

### 1-1. 구조 (기준 파일과 동일하게 유지)

```
Leaflet 다크 테마 맵 (CartoDBDark) +
컨트롤바 (지역필터 | 지표 | 업종 | 검색) +
사이드패널 (KPI 4개 | 건물목록 | 상세패널)
```

CSS 변수·클래스·함수 이름은 기준 파일(`Mapo` 또는 `Jongno`)과 **동일 구조** 유지.  
지역명 텍스트와 데이터만 바꾼다.

### 1-2. 존(zone) 버튼 생성 규칙

인수로 받은 상권 존마다 버튼 하나씩. 예:

```html
<button class="on" onclick="filterZone(this,'all')">전체</button>
<button onclick="filterZone(this,'이태원')">이태원</button>
<button onclick="filterZone(this,'한남동')">한남동</button>
...
```

### 1-3. 건물 데이터 (BUILDINGS 배열)

총 **30동**을 생성한다.  
존마다 건물 수를 균등 배분 (예: 존 5개 → 존당 6동).

각 건물 객체 필드:

```js
{
  id:       'XX001',        // 구 약어 2자 + 3자리 순번 (예: YS001)
  name:     '건물명',
  dong:     '행정동명',
  zone:     '상권존명',     // 위 존 버튼값과 일치
  addr:     '도로명주소',
  cat:      '오피스|상업|F&B|복합|문화|의료',
  floors:   숫자,
  year:     연도,
  area:     연면적(㎡),
  vac:      공실률(0~40),   // 구 성격에 맞게 분포
  sent:     감성지수(40~98),
  rent:     임대료(만원/평, 0~35),
  tenants:  임차인수,
  polygon:  [[lat,lng],[lat,lng],[lat,lng],[lat,lng]]  // 사각형 4점
}
```

**데이터 품질 기준:**
- 공실률·임대료는 해당 구의 실제 상권 특성을 반영한 합리적 값
- 감성지수: 핫플 존 85~96, 노후 구역 50~70
- 폴리곤: 실제 위치 기반 위경도 사각형 (약 50~100m 크기)
- 모든 필드에 `// TODO:` 주석으로 실데이터 연동 지점 명시 불필요 — 파일 상단 주석 블록에 한번만

**`getInsight(b)` 함수**: 마지막 else 분기에 해당 구 특성을 반영한 코멘트 추가.

### 1-4. V-World bbox

해당 구 전체를 감싸는 위경도 범위:

```js
const {구영문}_BBOX = [minLat, minLng, maxLat, maxLng];
```

`loadVWorldData()` 함수 내에서 사용. `parseVWorldGeoJSON`의 `dong` 기본값은 구 이름으로.

### 1-5. 지도 초기 중심

```js
map = L.map('map').setView([중심위도, 중심경도], 14);
```

존별 `filterZone` 내 centers 객체에 각 존 좌표 추가.

---

## STEP 2 — 통합 파일에 병합

파일: `html/Seoul/SpaceOS_Seoul_GangnamMapo_Building_Map.html`  
(파일명은 현재 그대로 유지 — 내용만 추가)

### 2-1. CSS

`:root` 에 구 색상 변수 추가:

```css
--{구소문자}: {색상hex};
```

버튼·배지 스타일 추가:

```css
.seg button.on-{구소문자} { background: var(--{구소문자}); color: #000; font-weight: 700 }
.gu-badge.{구소문자} { color: var(--{구소문자}); border-color: rgba(R,G,B,.3); background: rgba(R,G,B,.08) }
```

`gu-compare` grid-template-columns에 `1fr` 하나 추가.

### 2-2. HTML

| 위치 | 추가 내용 |
|------|-----------|
| 헤더 `.gu-badges` | `<div class="gu-badge {구소문자}">{구이름} 30동</div>` |
| `#seg-gu` | `<button onclick="filterGu(this,'{구이름}')">{구이름}</button>` |
| `#seg-zone` | 존 버튼 5개, 각각 `data-gu="{구이름}"` 속성 |
| `.gu-legend` | `<div class="gu-row"><div class="gu-dot" style="background:var(--{구소문자})"></div><span style="color:var(--mut)">{구이름}</span></div>` |
| `.gu-compare` | 구별 비교 `<div class="gc">` 블록 추가 (id: `gc-{구소문자}-vac`, `gc-{구소문자}-sent`) |

타이틀 `<title>` 과 `.title` 텍스트에 `·{구이름}` 추가.

### 2-3. JavaScript

**데이터 배열:**

```js
const {구영문대문자} = [
  // STEP 1에서 생성한 30동 — gu: '{구이름}' 필드 추가
];
```

`BUILDINGS` 병합:

```js
const BUILDINGS = [...GANGNAM, ...MAPO, ...JONGNO, ...{구영문대문자}];
```

**GU_BORDER:**

```js
const GU_BORDER = { ..., '{구이름}': '{색상hex}' };
```

**filterGu 분기:**

```js
btn.className = ... gu==='{구이름}' ? 'on-{구소문자}' : 'on';
const centers = { ..., '{구이름}': [중심위도, 중심경도, 14] };
```

**filterZone centers:**

```js
const centers = { ..., '존1': [lat,lng], '존2': [lat,lng], ... };
```

**updateKPIs:**

```js
const {구소문자} = vis.filter(b => b.gu === '{구이름}');
if ({구소문자}.length) {
  document.getElementById('gc-{구소문자}-vac').textContent = (avg({구소문자},'vac')).toFixed(1)+'%';
  document.getElementById('gc-{구소문자}-sent').textContent = `감성 ${Math.round(avg({구소문자},'sent'))}pt`;
}
```

**kb-cnt 분모:** 기존 값에 30 추가 (현재 90이면 120으로).

---

## STEP 3 — 완료 체크리스트

작업 마친 뒤 아래를 직접 확인한다.

- [ ] 개별 파일 `html/Seoul/SpaceOS_{구영문명}_Building_Map.html` 생성됨
- [ ] 건물 30동 완비 (id 중복 없음, zone 값이 버튼 값과 일치)
- [ ] 통합 파일 CSS — 구 색상 변수·버튼·배지 추가됨
- [ ] 통합 파일 HTML — 헤더 배지·구 버튼·존 버튼·범례·비교 패널 추가됨
- [ ] 통합 파일 JS — 데이터 배열·BUILDINGS 병합·GU_BORDER·filterGu·filterZone·updateKPIs 모두 갱신됨
- [ ] kb-cnt 분모 +30 갱신됨
- [ ] `Grep '구이름' 통합파일` 로 누락 없는지 확인

---

## 호출 예시

```
/district-map 용산구 이태원,한남동,용리단길,한강진,녹사평 37.5385,126.9947 #f472b6
/district-map 서초구 고속터미널,서래마을,반포,방배,양재 37.4837,127.0324
/district-map 중구 명동,을지로,동대문,충무로,남대문 37.5638,126.9976 #fb923c
```

색상 인수를 생략하면 팔레트 우선순위에 따라 자동 배정한다.
