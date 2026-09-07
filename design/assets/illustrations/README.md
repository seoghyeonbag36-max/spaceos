# 일러스트 에셋 (design/assets/illustrations)

프로덕트·IR·문서에서 재사용하는 벡터 일러스트. **SVG 가 원본**이고 PNG 는 그 파생물이다.
좌표를 손으로 고치지 말고 생성기 스크립트를 고친 뒤 다시 굽는다.

## iso-commercial-building — 아이소메트릭 한국 도심 상가

| 항목 | 값 |
|------|-----|
| 원본 | `iso-commercial-building.svg` (800×800, 배경 투명) |
| 파생 | `iso-commercial-building.png` (1024×1024, RGBA 투명) |
| 생성기 | `gen_iso_building.py` |

Page 트랙(공실 = 비어 있는 page 자리)을 한 장으로 설명하는 그림이다.
4층 상가에서 **1F 는 영업 중**(통유리 조명·빈 간판·차양·다운라이트),
**2~3F 는 공실**(어두운 창 + 강조색 테두리 + 임대 현수막 가로/세로),
**4F 는 정상 입주**(밝은 창)로 층 상태를 색으로만 구분한다.

색은 `design/tokens/tokens.json` 과 1:1 이다.

| 역할 | 값 | 토큰 |
|------|-----|------|
| 선 · 공실 창 | `#1C2533` | `color.ink` |
| 밝은 면 | `#F4F7FB` | `color.bg` |
| 가장 밝은 면(윗면·조명 켜진 유리) | `#FFFFFF` | `color.surface` |
| 빈 층 강조(밴드·창 테두리·현수막) | `#0EA5B7` | `color.brand.primary` |
| 좌측면 음영 | `#E3EAF3` | 위 `bg` 파생 — 아이소 면 분리에 필요한 유일한 파생색 |

제약: 평면적·미니멀, **그림자 없음**, **캔버스 배경 투명**(배경 `<rect>` 없음),
**텍스트·간판 글씨 없음**(`<text>`·`<tspan>` 0개 — 간판과 현수막은 빈 판이다), 정사각 비율.

### 다시 굽기

```bash
python design/assets/illustrations/gen_iso_building.py     # SVG 재생성

# PNG 파생 (Chromium 이 있는 환경에서만)
NODE_PATH=$(npm root -g) node -e "
const fs=require('fs'),{chromium}=require('playwright');(async()=>{
  const s=1024,svg=fs.readFileSync('design/assets/illustrations/iso-commercial-building.svg','utf8');
  const b=await chromium.launch(),p=await b.newPage({viewport:{width:s,height:s}});
  await p.setContent('<style>html,body{margin:0;background:transparent}svg{display:block;width:'+s+'px;height:'+s+'px}</style>'+svg);
  await p.screenshot({path:'design/assets/illustrations/iso-commercial-building.png',omitBackground:true});
  await b.close();})()"
```

투영은 정아이소메트릭(30°)이며 화면상 가까운 모서리가 `(x=W, y=D)` 다.
보이는 면은 평면 `y=D`(우측·정면) · 평면 `x=W`(좌측) · 윗면 세 개뿐이라
생성기의 `fr()` · `fl()` · `top()` 세 헬퍼로 모든 디테일을 얹는다.
스케일·중심은 실제 극점만으로 자동 산출하므로(`S` · `CX` · `CY`) 치수를 바꿔도 캔버스에 다시 맞춰진다.
