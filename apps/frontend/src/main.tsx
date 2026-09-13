import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { canonicalRedirect } from "@/lib/canonicalHost";
// 전역 리셋·토큰. MapShell 에서만 임포트하던 탓에 실제 화면에는 로드되지 않아
// body 기본 여백이 남아 있었다(2026-07-24 스크롤바 2개 증상).
import "@/styles/tokens.css";

// 정식 주소가 아니면(옛 사이트·firebaseapp.com) 그리기 전에 옮긴다 — 등록 안 된 origin 에서는
// 지도 인증이 실패한다(lib/canonicalHost). replace 라 뒤로가기에 옛 주소가 남지 않는다.
const moveTo = canonicalRedirect(window.location);
if (moveTo) {
  window.location.replace(moveTo);
} else {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
