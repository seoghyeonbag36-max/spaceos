/**
 * 계정 화면 틀 — 가입·로그인·API 키를 **지도 위 모달**로 띄운다 (2026-09-23 B9).
 *
 * 지도 대신 화면을 갈아끼우지 않는 이유: 지도(MapHost)는 앱 수명 동안 하나이고 사용자가
 * 맞춰 둔 중심·줌을 지켜야 한다(App.tsx). 트랙 패널도 그대로 둔다 — 닫으면 보던 자리로 돌아온다.
 * 네이티브 <dialog> + showModal 은 CandidateCompare 와 같은 방식이다: 포커스가 대화상자 안에
 * 갇히고, Esc 가 대화상자만 닫는다(TrackMapFrame 은 dialog[open] 이 있으면 Esc 를 양보한다).
 */
import { useEffect, useRef, type ReactNode } from "react";
import "@/pages/Account.css";

export type AccountScreen = "login" | "signup" | "account";

/** 세 화면이 받는 공통 props — 화면끼리 옮겨 갈 때 해시를 바꾸는 한 가지 방법만 준다. */
export interface AccountScreenProps {
  go: (screen: AccountScreen) => void;
}

/** 각 화면의 제목 h2 가 쓰는 id — 대화상자의 접근 가능한 이름이 된다 */
export const ACCOUNT_TITLE_ID = "account-title";

export default function AccountDialog({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    node?.showModal();
    return () => { node?.close(); previousFocus?.focus(); };
  }, []);

  return (
    <dialog ref={dialog} className="acct-dialog" aria-labelledby={ACCOUNT_TITLE_ID}
      onCancel={(e) => { e.preventDefault(); onClose(); }}>
      <button type="button" className="acct-close" onClick={onClose} aria-label="계정 창 닫기">닫기</button>
      {children}
    </dialog>
  );
}
