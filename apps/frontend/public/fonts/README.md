# Pretendard (자체 호스팅)

`npm i -D pretendard` (v1.3.9) 의 **static subset** 빌드를 그대로 복사한 것이다.
외부 CDN(Google Fonts 등)을 쓰지 않는다 — 폰트는 우리가 서빙한다.

| 파일 | 굵기 | 용량 |
|------|------|------|
| `Pretendard-Regular.subset.woff2` | 400 | 260.8 KiB |
| `Pretendard-Bold.subset.woff2`    | 700 | 264.4 KiB |
|                                   | 합계 | **525.3 KiB** |

서브셋 커버리지: 코드포인트 3,728 · 한글 음절 2,780(KS X 1001 계열).
전체 빌드(`woff2/`, Regular+Bold 1.48 MiB) 대비 **65% 감축**.

## 갱신 방법
```bash
cd apps/frontend
npm i -D pretendard                       # 버전 올릴 때
cp node_modules/pretendard/dist/web/static/woff2-subset/Pretendard-Regular.subset.woff2 public/fonts/
cp node_modules/pretendard/dist/web/static/woff2-subset/Pretendard-Bold.subset.woff2    public/fonts/
```
`@font-face` 선언은 `src/styles/tokens.css` 한 곳에만 있다.

## 라이선스
SIL Open Font License 1.1 — 전문은 `OFL.txt`.
Copyright (c) 2021, Kil Hyung-jin, with Reserved Font Name 'Pretendard'.
