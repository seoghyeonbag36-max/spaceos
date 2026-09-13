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

export interface FitPadding { top: number; right: number; bottom: number; left: number }

/** 칩은 좌표에 가운데 정렬로 걸린다 — 점만 비키면 칩 왼쪽 절반이 패널 밑에 남는다. 칩 반폭 + 여유. */
const CHIP_CLEARANCE = 72;

/**
 * 지도 캔버스 중 **UI 가 덮고 있는 가장자리**(px) — 카메라를 맞출 때 이만큼 비킨다.
 *
 * 캔버스는 레일 **밑**(x=0)부터 깔리고 오버레이는 `--rail-w` 부터 시작한다(MapHost.css).
 * 2026-09-13 실사이트 확인: 종전 여백은 `패널 폭 + 48` 이라 레일 64px + 패널 좌측 여백 12px 가
 * 빠져 있었고, Posting 에서 가장 왼쪽 자리 칩(월 1,307만 · 월 562만)이 패널 가장자리에 잘렸다.
 * 상수를 더하지 않고 **그려진 패널을 잰다** — 접힌 패널(=레일만)·모바일 시트 높이·좁은 화면의
 * `min(560px, 100% − 24px)` 가 저절로 맞는다. DOM 이 없으면(단위 테스트) 레일·패널 0 으로 본다.
 */
export function mapFitPadding(): FitPadding {
  const rail = document.querySelector(".maphost .map-overlays")?.getBoundingClientRect().left ?? 0;
  const panel = document.querySelector(".trackmap-panel:not([hidden])")?.getBoundingClientRect();
  const shown = !!panel && panel.width > 0 && panel.height > 0;
  if (window.innerWidth <= 768) {
    // 모바일: 패널은 하단 시트다 — 시트 윗변부터 아래가 가려진다.
    const covered = shown ? Math.max(0, window.innerHeight - panel.top) : 0;
    return { top: 72, right: 24, bottom: Math.round(covered) + 24, left: Math.round(rail) + 24 };
  }
  return { top: 72, right: CHIP_CLEARANCE, bottom: 48, left: Math.round(shown ? panel.right : rail) + CHIP_CLEARANCE };
}

/**
 * 좌표 하나를 **가려지지 않은 영역의 가운데**로 민다(카메라가 이미 선 뒤에 부른다).
 *
 * 네이버 API 두 성질을 09-13 실측으로 확인하고 쓴다:
 *   · `panBy(+x)` 는 **시야**를 오른쪽으로 옮긴다(중심 경도가 커진다) — 내용은 왼쪽으로 간다.
 *   · `projection.fromCoordToOffset` 은 뷰포트가 아니라 지도 판 기준이라 panBy 뒤에도 값이 같다 —
 *     그래서 **지도 중심의 오프셋과의 차**로 뷰포트 좌표를 구한다.
 * 투영이 없으면(단위 테스트 스텁) 아무것도 하지 않는다.
 */
function shiftIntoView(map: any, naver: any, target: any, pad: FitPadding): void {
  const proj = map.getProjection?.();
  const size = map.getSize?.();
  const center = map.getCenter?.();
  if (!proj?.fromCoordToOffset || !size || !center) return;
  const t = proj.fromCoordToOffset(target), c = proj.fromCoordToOffset(center);
  const x = t.x - c.x + size.width / 2, y = t.y - c.y + size.height / 2;
  const dx = Math.round(x - (pad.left + size.width - pad.right) / 2);
  const dy = Math.round(y - (pad.top + size.height - pad.bottom) / 2);
  if (dx || dy) map.panBy?.(new naver.maps.Point(dx, dy));
}

/** 점 하나 — `setCenter` 만 하면 점이 뷰포트 한가운데(1440px 에서 x=720)라 패널 끝(x≈638) 바로 옆에 붙는다. */
function centerInView(map: any, naver: any, lat: number, lng: number): void {
  const at = new naver.maps.LatLng(lat, lng);
  map.setCenter?.(at);
  shiftIntoView(map, naver, at, mapFitPadding());
}

/**
 * 범위 맞춤 + 가운데 보정.
 *
 * `fitBounds(bounds, 여백)` 만으로는 비대칭 여백이 지켜지지 않는다. 네이버는 여백을 **소수 줌**에서
 * 맞춘 뒤 줌을 정수로 내리는데, 그때 치우침(px)도 같이 줄어든다 — 09-13 Posting 실측: left 710 ·
 * right 72 를 줬는데 자리들의 중심이 화면 가운데에서 +160px(기대 319px)에 그쳐 가장 왼쪽 칩이 패널
 * 끝에 걸렸다. 줌은 네이버가 고른 대로 두고, 범위 중심만 가려지지 않은 영역 가운데로 다시 민다.
 */
export function fitInView(map: any, naver: any, bounds: any, pad: FitPadding = mapFitPadding()): void {
  map.fitBounds?.(bounds, pad);
  const center = bounds.getCenter?.();
  if (center) shiftIntoView(map, naver, center, pad);
}

/**
 * 카메라를 점들에 맞춘다 — `key` 가 바뀔 때만(거점 전환 등). 사용자가 옮겨 둔 카메라를
 * 매 렌더 되돌리지 않는다. 점이 없으면 `fallback` 중심으로만 옮긴다.
 *
 * 패널 **밑에** 점이 깔리면 없는 것처럼 보인다 — 여백은 `mapFitPadding()` 이 잰다.
 */
export function useFitMap(key: string | null, points: Array<{ lat: number; lng: number }>,
  fallback: { lat: number; lng: number } | null): void {
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
      centerInView(map, naver, fallback.lat, fallback.lng);
      doneRef.current = stage;
      return;
    }
    if (pts.length === 1) {
      // 점 하나로 fitBounds 를 부르면 크기 0 범위라 최대 줌까지 치고 들어간다 — 중심만 옮긴다.
      centerInView(map, naver, pts[0].lat, pts[0].lng);
      doneRef.current = stage;
      return;
    }
    const lats = pts.map((p) => p.lat), lngs = pts.map((p) => p.lng);
    fitInView(map, naver, new naver.maps.LatLngBounds(
      new naver.maps.LatLng(Math.min(...lats), Math.min(...lngs)),
      new naver.maps.LatLng(Math.max(...lats), Math.max(...lngs)),
    ));
    doneRef.current = stage;
  }, [ready, map, key, points, fallback]);
}
