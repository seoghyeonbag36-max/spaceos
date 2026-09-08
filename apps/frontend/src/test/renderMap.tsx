/**
 * 지도 오버레이 화면(MapShell·HubExplorer)을 **실제 MapHost 안에서** 렌더한다.
 *
 * `useMapHost()` 를 통째로 목킹하지 않는 이유: 이 그물이 잡으려는 회귀가 바로 그
 * 경계에 있다. 지도는 MapHost 가 하나만 만들어 앱 수명 동안 들고 있고 탭은 오버레이만
 * 갈아끼우므로, "MapHost 가 지도를 넘겨주는가 → 오버레이가 붙는가 → 전환할 때 걷히는가"
 * 를 한 줄로 봐야 의미가 있다. 목으로 잘라 내면 정리 누락이 그대로 통과한다.
 *
 * 대신 **SDK 로더만** 목킹한다(`@/lib/naverMap`) — 각 테스트 파일이 스스로 건다.
 */
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import MapHost from "@/components/MapHost";

export function renderOnMap(node: ReactNode) {
  return render(<MapHost active>{node}</MapHost>);
}
