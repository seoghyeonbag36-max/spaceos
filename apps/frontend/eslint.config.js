// ESLint 설정 (flat config) — `npm run lint`
//
// ⚠ 왜 생겼나: `package.json` 에 `"lint": "eslint ."` 스크립트만 있고 eslint 는
//   devDependencies 에 **없었다**. `tailwind.config.ts` 와 정확히 같은 종류의
//   죽은 스크립트였다(2026-09-06 에 되살림).
//
// tsc 와 역할을 나눈다 — `npm run build` 의 `tsc -b` 가 타입을 보고, 여기서는
// 타입으로 안 잡히는 것만 본다. 특히 **react-hooks/exhaustive-deps** 가 핵심이다:
// 이 코드베이스는 네이버 지도 인스턴스를 useEffect 로 만들고 정리하는 곳이 많아,
// 의존성 배열이 틀리면 지도가 두 번 생기거나 리스너가 안 떨어진다.
//
// 검사 범위는 tsconfig.json 과 맞춘다(`include: ["src"]`).
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  // 빌드 산출물·의존성은 보지 않는다
  { ignores: ["dist", "node_modules", "public"] },
  {
    files: ["src/**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      // 의도적으로 안 쓰는 인자는 `_` 접두사로 표시한다(tsconfig 의
      // noUnusedParameters 와 같은 관례).
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],

      // ── 아래 둘은 **경고로 낮춘다**. 끄지는 않는다 — 계속 보이게 두되,
      //    고치려면 앱 구조를 손대야 해서 이번 정리와 분리한다.

      // any 18곳은 전부 한 원인이다: **네이버 지도 SDK 에 타입 정의가 없다**.
      // `<script>` 로 실려 오는 전역이라 `@types` 패키지가 존재하지 않는다
      // (`(window as any).naver`, `useRef<any>` 로 잡은 Map·오버레이 핸들).
      // 진짜 해법은 우리가 쓰는 SDK 표면(Map·LatLng·Marker·Polygon·InfoWindow)
      // 만 추린 .d.ts 를 두는 것이고, 그건 별도 작업이다. 그때까지 경고로 남긴다.
      "@typescript-eslint/no-explicit-any": "warn",

      // react-hooks v7 이 들여온 React Compiler 세대 규칙이다. 15곳이 걸리는데
      // 전부 "prop 이 바뀌면 이전 응답을 비우고 다시 가져온다"는 같은 패턴이라
      // (PostingConsole·ProgramStudio·PageDashboard 의 fetch 이펙트), 고치려면
      // 데이터 로딩 구조 자체를 바꿔야 한다. 동작하는 코드를 정리 커밋에서
      // 갈아엎지 않는다 — 경고로 남겨 다음 리팩터의 목록으로 쓴다.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
);
