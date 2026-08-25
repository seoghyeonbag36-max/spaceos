# 여기에는 워크플로를 두지 않는다

GitHub Actions 는 **저장소 루트의 `.github/workflows/` 만** 읽는다. 경로를 설정으로
바꿀 수 없다. 이 디렉터리에 `ci.yml` 을 두면 **파일은 있는데 CI 는 안 도는** 상태가
된다 — 이 저장소가 반복해 잡아 온 실패 양식(설정이 있으니 됐다고 읽히지만 산출물이
제품에 안 닿는다)과 같은 모양이다.

실제 워크플로: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
(2026-08-25 신설 — 백엔드 pytest · 데이터 파이프라인 pytest · 프론트 tsc+빌드).

경위와 남은 인프라 결정: [`docs/decision-infra-layer-2026-08-25.md`](../../docs/decision-infra-layer-2026-08-25.md)

## 그럼 이 디렉터리는 무엇인가

CI 가 **아닌** 인프라 자료를 둔다 — 이슈·PR 템플릿 원본, 배포 노트, k8s 매니페스트로
가기 전의 초안 따위. 비어 있어도 무방하다. 다만 `.gitkeep` 만 남아 있으면 "CI 가
여기 있어야 하는데 아직 없다"로 읽히므로 이 파일을 남긴다.
