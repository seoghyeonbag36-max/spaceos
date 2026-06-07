// Storybook 설정 — 디자인 시스템 문서화·공유의 기준점
// TODO: 설치 → npx storybook@latest init  (vite-react)
import type { StorybookConfig } from "@storybook/react-vite";
const config: StorybookConfig = {
  stories: ["../src/design/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-essentials", "@storybook/addon-a11y"], // a11y=대비 검사
  framework: { name: "@storybook/react-vite", options: {} },
};
export default config;
