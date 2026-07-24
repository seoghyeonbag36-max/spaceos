import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
// 전역 리셋·토큰. MapShell 에서만 임포트하던 탓에 실제 화면에는 로드되지 않아
// body 기본 여백이 남아 있었다(2026-07-24 스크롤바 2개 증상).
import "@/styles/tokens.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
