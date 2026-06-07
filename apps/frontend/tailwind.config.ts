// SpaceOS Tailwind 설정 — design/tokens 와 1:1 매핑
// TODO: tailwindcss 설치 후 활성화 (npm i -D tailwindcss postcss autoprefixer && npx tailwindcss init)
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        naver: { DEFAULT: "#03C75A", pressed: "#02B350", soft: "#E6F8EE" },
        brand: { DEFAULT: "#0EA5B7", pressed: "#0B8294", soft: "#E6F7F9" },
        ink: "#1C2533", muted: "#6B7280", line: "#E3E9F2", surface: "#FFFFFF", bg: "#F4F7FB",
      },
      fontFamily: { sans: ["Pretendard", "system-ui", "sans-serif"] },
      borderRadius: { sm: "8px", md: "12px", lg: "16px" },
      boxShadow: {
        card: "0 1px 3px rgba(11,27,51,.08), 0 4px 12px rgba(11,27,51,.06)",
        sheet: "0 -4px 24px rgba(11,27,51,.12)",
      },
    },
  },
  plugins: [],
};
export default config;
