/**
 * TrackMapFrame — Platform·Posting·Program 을 **지도 전체화면 위 좌측 패널**로 띄운다.
 *
 * ## 왜 (2026-09-13 「네 트랙 모두 Page 처럼 지도 전체화면」)
 *
 * 그전까지 지도 위에 사는 화면은 Page 하나였고, 나머지 셋은 지도가 없는 대시보드였다.
 * 탭을 옮기면 지도가 통째로 사라졌다가 Page 로 돌아와야 다시 보였다 — 네 트랙이 같은
 * 상권(place)에 대한 네 질문인데, 화면은 "지도 제품 하나 + 보고서 셋"으로 읽혔다.
 *
 * 이제 네 트랙 모두 같은 지도(MapHost) 위에 뜬다. Page 가 쓰는 배치를 그대로 따른다:
 *   · 지도는 뷰포트 전체 — 패널은 지도를 밀어내지 않고 **위에** 뜬다
 *   · 패널은 접을 수 있다 — 접으면 화면 전체가 지도다(MapShell `panelOpen` 과 같은 동선)
 *   · 모바일(≤768px)은 하단 바텀시트
 *
 * 지도에 무엇을 그릴지는 이 프레임이 아니라 **각 콘솔이** 정한다(`useMapMarkers`).
 * 콘솔만 알고 있는 상태(고른 자리·검색 후보)가 곧 지도의 강조이기 때문이다.
 *
 * 콘솔의 본문 레이아웃(2단 그리드 등)은 뷰포트 폭 기준 미디어쿼리로 짜여 있어, 폭이
 * 좁은 패널 안에서는 그대로 두면 칸이 짓눌린다. 패널 안에서만 1단으로 접는 규칙은
 * TrackMapFrame.css 가 갖는다 — 콘솔 CSS 는 단독 화면(테스트·#board)용으로 그대로 둔다.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { TrackKey } from "@/design/tokens/colors";
import { isEditableTarget } from "@/lib/keyboard";
import "./TrackMapFrame.css";

export default function TrackMapFrame({ track, label, children }: {
  track: TrackKey;
  /** 접었을 때 펴기 버튼에 뜨는 이름 — "상권 정체성" 처럼 이 패널이 무엇인지 */
  label: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(true);
  const panelId = `track-panel-${track}`;
  const collapseRef = useRef<HTMLButtonElement>(null);
  const reopenRef = useRef<HTMLButtonElement>(null);
  // 접기·펴기 뒤 포커스를 **짝 버튼으로** 옮긴다(화면설계서 2판 C-03). 누른 버튼이 사라지면
  // 포커스가 body 로 떨어져 키보드 사용자는 어디서 다시 시작할지 모른다. 첫 렌더는 건너뛴다 —
  // 탭을 열자마자 포커스를 뺏으면 레일에서 Tab 하던 흐름이 끊긴다.
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return; }
    (open ? collapseRef.current : reopenRef.current)?.focus();
  }, [open]);

  // Esc 로 패널을 접는다 — Page(MapShell R5)와 같은 동선. 입력 중에는 건드리지 않는다
  // (textarea 에서 Esc 를 눌렀는데 패널이 닫히면 쓰던 내용이 눈앞에서 사라진다).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || !open) return;
      if (isEditableTarget(e.target)) return;
      if (document.querySelector("dialog[open]")) return;
      setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="trackmap" data-track={track}>
      {!open && (
        <button ref={reopenRef} type="button" className="trackmap-reopen" onClick={() => setOpen(true)}
          aria-expanded={false} aria-controls={panelId}>
          ☰ {label}
        </button>
      )}
      <aside id={panelId} className="trackmap-panel" hidden={!open} aria-label={label}>
        <button ref={collapseRef} type="button" className="trackmap-collapse" onClick={() => setOpen(false)}
          aria-expanded aria-controls={panelId} aria-label={`${label} 접기`}
          title="패널을 접고 지도를 넓게 본다">‹</button>
        <div className="trackmap-scroll">{children}</div>
      </aside>
    </div>
  );
}
