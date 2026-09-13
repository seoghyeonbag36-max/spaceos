/**
 * useMapMarkers — 공유 지도(MapHost) 위에 **HTML 마커 묶음**을 그렸다 걷는 훅.
 *
 * ## 왜 따로 뺐나 (2026-09-13 「네 트랙 모두 지도 전체화면」)
 *
 * 그전까지 지도 위에 무언가를 그리는 화면은 Page(MapShell)·거점(HubExplorer) 둘뿐이었고,
 * 둘 다 "오버레이 배열 + 리스너 배열을 들고 있다가 같은 자리에서 걷는다"를 손으로 짰다.
 * Platform·Posting·Program 도 지도 위로 올라오면서 같은 코드가 세 벌 더 생길 참이라,
 * **걷는 규칙을 한 곳에** 둔다. MapShell 이 계측으로 배운 두 가지를 그대로 지킨다:
 *
 *   1. 리스너 핸들을 **오버레이와 같은 수명**으로 들고 있다가 먼저 뗀다.
 *      `setMap(null)` 은 지도에서 떼기만 하고 등록은 남긴다(2026-09-08 계측: 10회 전환에
 *      addListener 1,710 / removeListener 0).
 *   2. 클릭 콜백은 ref 로 읽는다. 콜백이 렌더마다 새로 만들어져도 마커를 다시 만들지 않는다.
 *
 * ## 지도가 없을 때
 *
 * `useMapHost()` 의 기본값은 `{ map: null, ready: false }` 다. 콘솔을 MapHost 밖에서 단독으로
 * 렌더하면(단위 테스트) 이 훅은 아무것도 하지 않는다 — 화면 로직은 지도 없이도 돈다.
 */
import { useEffect, useRef } from "react";
import { useMapHost } from "@/components/MapHost";

export interface MapMarkerItem {
  id: string;
  lat: number;
  lng: number;
  /** `icon.content` 에 들어갈 HTML. 데이터 문자열은 `escapeHTML` 을 거쳐 넣는다. */
  html: string;
  zIndex?: number;
}

export function useMapMarkers(items: MapMarkerItem[], onClick?: (id: string) => void): void {
  const { map, ready } = useMapHost();
  const clickRef = useRef(onClick);
  useEffect(() => { clickRef.current = onClick; }, [onClick]);

  useEffect(() => {
    const naver = (window as any).naver;
    if (!ready || !map || !naver?.maps) return;
    const overlays: any[] = [];
    const listeners: any[] = [];
    for (const it of items) {
      if (!Number.isFinite(it.lat) || !Number.isFinite(it.lng)) continue;
      const marker = new naver.maps.Marker({
        map,
        position: new naver.maps.LatLng(it.lat, it.lng),
        zIndex: it.zIndex ?? 70,
        // 칩 HTML 이 스스로 translate(-50%,-100%) 로 꼬리 끝을 좌표에 맞춘다 — 앵커는 0,0.
        icon: { content: it.html, anchor: new naver.maps.Point(0, 0) },
      });
      listeners.push(naver.maps.Event.addListener(marker, "click", () => clickRef.current?.(it.id)));
      overlays.push(marker);
    }
    return () => {
      // 리스너를 **먼저** 뗀다 — 오버레이 참조를 버린 뒤에는 짝을 찾을 자리가 없다.
      listeners.forEach((h) => naver?.maps?.Event?.removeListener(h));
      overlays.forEach((o) => o.setMap?.(null));
    };
  }, [ready, map, items]);
}

/**
 * 카메라를 점들에 맞춘다 — `key` 가 바뀔 때만(거점 전환 등). 사용자가 옮겨 둔 카메라를
 * 매 렌더 되돌리지 않는다. 점이 없으면 `fallback` 중심으로만 옮긴다.
 *
 * `padLeft` 는 좌측 패널 폭이다. 패널 **밑에** 점이 깔리면 없는 것처럼 보인다.
 */
export function useFitMap(key: string | null, points: Array<{ lat: number; lng: number }>,
  fallback: { lat: number; lng: number } | null, padLeft = 0): void {
  const { map, ready } = useMapHost();
  const doneRef = useRef<string | null>(null);
  useEffect(() => {
    const naver = (window as any).naver;
    if (!ready || !map || !naver?.maps || key == null) return;
    const pts = points.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng));
    // 점이 아직 안 왔으면 중심만 옮기고, 점이 오면 한 번 더 맞춘다(같은 key 에서 최대 2번).
    const stage = `${key}|${pts.length > 0 ? "fit" : "center"}`;
    if (doneRef.current === stage || (doneRef.current === `${key}|fit`)) return;
    if (pts.length === 0) {
      if (!fallback) return;
      map.setCenter?.(new naver.maps.LatLng(fallback.lat, fallback.lng));
      doneRef.current = stage;
      return;
    }
    if (pts.length === 1) {
      // 점 하나로 fitBounds 를 부르면 크기 0 범위라 최대 줌까지 치고 들어간다 — 중심만 옮긴다.
      map.setCenter?.(new naver.maps.LatLng(pts[0].lat, pts[0].lng));
      doneRef.current = stage;
      return;
    }
    const lats = pts.map((p) => p.lat), lngs = pts.map((p) => p.lng);
    const narrow = window.innerWidth <= 768;
    map.fitBounds?.(
      new naver.maps.LatLngBounds(
        new naver.maps.LatLng(Math.min(...lats), Math.min(...lngs)),
        new naver.maps.LatLng(Math.max(...lats), Math.max(...lngs)),
      ),
      narrow
        ? { top: 72, right: 24, bottom: Math.round(window.innerHeight * 0.52) + 24, left: 24 }
        : { top: 72, right: 48, bottom: 48, left: padLeft + 48 },
    );
    doneRef.current = stage;
  }, [ready, map, key, points, fallback, padLeft]);
}
