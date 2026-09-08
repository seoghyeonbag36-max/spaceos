/**
 * vitest 설정 — 프론트 회귀를 **초 단위**로 잡는 그물.
 *
 * ⚠ `vite.config.ts` 는 손대지 않는다. vitest 는 `vitest.config.ts` 가 있으면 그쪽만
 *   읽으므로, 빌드 설정(별칭 `@/`·react 플러그인)을 여기서 다시 적지 않고 그대로 물려받는다
 *   (`mergeConfig`). 두 곳에 같은 별칭을 적어 두면 한쪽만 바뀌었을 때 조용히 어긋난다.
 *
 * 환경은 jsdom 이다 — 이 그물이 보는 것은 지도 픽셀이 아니라 **오버레이 수명·API 경로·
 * 패널이 무엇을 그리는가** 셋이고, 셋 다 DOM 과 SDK 스텁으로 판정된다. 실제 지도와
 * 실제 백엔드를 부르는 검증은 `/verify`(로컬 앱)와 Playwright 의 몫이다.
 */
import { mergeConfig, defineConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      // 테스트는 대상 코드 옆에 둔다. `src/test/*` 는 헬퍼라 여기에 안 걸린다.
      include: ["src/**/*.test.{ts,tsx}"],
      // `describe`·`it`·`expect` 는 각 파일이 명시 import 한다 — eslint 의 no-undef 와
      // tsc 가 전역 없이도 그대로 본다.
      globals: false,
      restoreMocks: true,
      unstubGlobals: true,
    },
  }),
);
