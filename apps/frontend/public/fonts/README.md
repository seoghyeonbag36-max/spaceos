# Pretendard (자체 호스팅)

`npm i -D pretendard` (v1.3.9) 의 **static subset** 빌드를 그대로 복사한 것이다.
외부 CDN(Google Fonts 등)을 쓰지 않는다 — 폰트는 우리가 서빙한다.

| 파일 | 굵기 | 용량 | 전체 빌드 |
|------|------|------|-----------|
| `Pretendard-Regular.subset.woff2`  | 400 | 260.8 KiB | 748.0 KiB |
| `Pretendard-SemiBold.subset.woff2` | 600 | 262.5 KiB | 767.4 KiB |
| `Pretendard-Bold.subset.woff2`     | 700 | 264.4 KiB | 772.6 KiB |
|                                    | 합계 | **787.7 KiB** | 2.23 MiB |

서브셋 커버리지: 파일마다 코드포인트 3,728 · 한글 음절 2,780(KS X 1001 계열).
전체 빌드 대비 **65% 감축**.

세 웨이트만 받는다. 500 은 400 으로, 800·900 은 700 으로 브라우저가 떨어뜨린다
(합성 볼드가 아니라 폰트매칭이라 획은 뭉개지지 않는다).

## 갱신 방법
```bash
cd apps/frontend
npm i -D pretendard                       # 버전 올릴 때
SRC=node_modules/pretendard/dist/web/static/woff2-subset
for w in Regular SemiBold Bold; do cp "$SRC/Pretendard-$w.subset.woff2" public/fonts/; done
```
`@font-face` 선언은 `src/styles/tokens.css` 한 곳에만 있다.

## 라이선스
SIL Open Font License 1.1 — 전문은 `OFL.txt`.
Copyright (c) 2021, Kil Hyung-jin, with Reserved Font Name 'Pretendard'.
