// 네이버 지도 Dynamic Map v3 래퍼
// 키: apps/frontend/.env 의 VITE_NAVER_MAPS_KEY_ID (Client ID = 9nbzrvj8qj)
// ※ NCP 콘솔 > Maps > Application 의 Web 서비스 URL 에 서비스할 origin 을 전부 등록해야 한다.
//   로컬 http://localhost:5173 / 프로덕션 https://spaceos-twin.web.app · https://spaceos-twin.firebaseapp.com
//   미등록 origin(file:// 포함)에서는 인증오류로 지도가 표시되지 않는다.
//   브라우저 없이 확인하는 법 — result 면 통과, errorCode 200 이면 그 origin 이 미등록이다:
//     curl "https://oapi.map.naver.com/v3/auth?ncpKeyId=<KEY>&url=<encoded origin>&time=<ms>&callback=cb"

declare global {
  interface Window { naver?: any; navermap_authFailure?: () => void }
}

let _loading: Promise<void> | null = null;
let _authFailed = false;

/** 미등록 도메인일 때 보여줄 문구 — 원인과 조치가 한 줄에 같이 있어야 한다. */
function authFailMessage(): string {
  const origin = typeof window !== 'undefined' ? window.location.origin : '(unknown)';
  return `네이버 지도 인증 실패 — NCP 콘솔 > Maps > Application 의 Web 서비스 URL 에 ${origin} 이 등록돼 있지 않습니다.`;
}

/**
 * 지도 관련 예외를 사람이 읽을 원인으로 바꾼다.
 * SDK 는 인증 실패를 script.onerror 로 알리지 않는다. 로드는 성공시켜 놓고 약 1.2초 뒤
 * `naver.maps` 를 null 로 갈아버린다(SDK 내부: `t.naver.maps=null, It()`).
 * 그래서 호출부는 "Cannot read properties of null (reading 'Map')" 이라는 엉뚱한 메시지를 받는다.
 * 진짜 원인은 도메인 미등록이므로 여기서 되돌려 준다.
 */
export function describeNaverMapError(e: unknown): string {
  if (_authFailed || (typeof window !== 'undefined' && window.naver && !window.naver.maps)) {
    return authFailMessage();
  }
  return (e as any)?.message ?? String(e);
}

/** 네이버 지도 JS SDK 동적 로드 (중복 로드 방지) */
export function loadNaverMaps(): Promise<void> {
  if (window.naver?.maps) return Promise.resolve();
  if (_loading) return _loading;
  _loading = new Promise<void>((resolve, reject) => {
    // 환경변수에 BOM(U+FEFF)·공백이 섞이면 네이버 인증이 실패하므로 반드시 제거한다.
    const keyId = (import.meta.env.VITE_NAVER_MAPS_KEY_ID ?? '').replace(/\uFEFF/g, '').trim();
    if (!keyId) return reject(new Error('VITE_NAVER_MAPS_KEY_ID 미설정 (.env 확인)'));
    // SDK 가 인증 실패를 알리는 유일한 창구. 스크립트보다 먼저 걸어 둬야 놓치지 않는다.
    window.navermap_authFailure = () => {
      _authFailed = true;
      _loading = null;              // 도메인을 등록한 뒤 새로고침하면 다시 시도할 수 있게
      reject(new Error(authFailMessage()));
    };
    const s = document.createElement('script');
    // submodules 는 **한 번에** 받는다. SDK 는 첫 로드의 submodule 집합을 그대로 굳히므로,
    // 지도를 먼저 띄운 뒤 파노라마를 따로 부르면 `naver.maps.Panorama` 가 없다.
    //   visualization: 유동인구 HeatMap(naver.maps.visualization.HeatMap)
    //   panorama:      거리뷰(naver.maps.Panorama) — 별도 상품·키가 아니라 Dynamic Map 에
    //                  포함이고, 인증도 지금 지도와 같은 도메인 화이트리스트를 쓴다.
    s.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${keyId}&submodules=visualization,panorama`;
    s.async = true;
    s.onload = () => (_authFailed ? reject(new Error(authFailMessage())) : resolve());
    s.onerror = () => reject(new Error('네이버 지도 SDK 로드 실패 — 네트워크/차단 확인'));
    document.head.appendChild(s);
  });
  return _loading;
}

/** 상권 중심좌표에 지도 생성 + 공실 마커 표시 */
export async function renderDistrictMap(el: HTMLElement, center: { lat: number; lng: number }, vacancies: Array<{ lat: number; lng: number; score: number }>) {
  await loadNaverMaps();
  const { naver } = window;
  if (!naver?.maps) throw new Error(authFailMessage());
  const map = new naver.maps.Map(el, {
    center: new naver.maps.LatLng(center.lat, center.lng),
    zoom: 16,
  });
  // TODO: score(공실 위험도)에 따라 마커 색상 차등 — Page 히트맵과 색상 규칙 공유
  vacancies.forEach((v) => {
    new naver.maps.Marker({ position: new naver.maps.LatLng(v.lat, v.lng), map });
  });
  return map;
}

/* ===== 거리뷰(파노라마) ===== */

/** 두 좌표 사이의 방위각(0=북, 시계방향 도).
 *
 * 거리뷰는 좌표를 주면 **가장 가까운 도로**의 파노라마를 잡는다. 그대로 두면 카메라가
 * 도로를 보고 있어서 정작 그 건물이 화면 밖에 있다. 파노라마 실제 위치에서 건물
 * 중심으로의 방위각을 구해 `pan` 에 넣어야 건물이 정면에 온다.
 */
export function bearingDeg(from: { lat: number; lng: number }, to: { lat: number; lng: number }): number {
  const r = Math.PI / 180;
  const p1 = from.lat * r, p2 = to.lat * r, dl = (to.lng - from.lng) * r;
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return (Math.atan2(y, x) / r + 360) % 360;
}

/** 파노라마 메타 — 화면이 근거를 밝히는 데 쓴다. */
export interface PanoramaInfo {
  panoId: string;
  /** 촬영 시점("2023-04-12" 등). ⚠ 몇 년 전일 수 있다 — 공실 판정의 근거로 쓰면 안 된다. */
  photodate?: string;
  address?: string;
  title?: string;
  /** 파노라마 위치 → 건물 중심 거리(m). 크면 건물이 멀리 보인다. */
  distanceM?: number;
}

/** 대상 좌표를 바라보는 거리뷰를 el 에 띄운다.
 *
 * 성공하면 `PanoramaInfo`, 그 좌표에 파노라마가 없으면 **null** 을 돌려준다(예외 아님) —
 * 골목 안 건물에서 실제로 일어나는 정상 상태이고, 호출부는 폴백을 그려야 한다.
 * 정리 함수는 `destroy()` 로 받는다.
 */
export async function renderStreetView(
  el: HTMLElement,
  target: { lat: number; lng: number },
): Promise<{ info: PanoramaInfo | null; destroy: () => void }> {
  await loadNaverMaps();
  const { naver } = window;
  if (!naver?.maps) throw new Error(authFailMessage());
  if (!naver.maps.Panorama) {
    // submodules 에 panorama 가 빠진 채 SDK 가 이미 굳은 경우. 조용히 빈 화면을 두면
    // "이 건물엔 거리뷰가 없다"로 오독되므로 원인을 그대로 올린다.
    throw new Error('네이버 거리뷰 모듈 미로드 — SDK submodules 에 panorama 가 빠졌다');
  }

  return new Promise((resolve) => {
    let done = false;
    const pano = new naver.maps.Panorama(el, {
      position: new naver.maps.LatLng(target.lat, target.lng),
      pov: { pan: 0, tilt: 0, fov: 100 },
      flightSpot: false,
      aroundControl: true,
    });
    const destroy = () => { try { pano.destroy?.(); } catch { /* 이미 정리됨 */ } };

    // 파노라마가 없는 좌표는 여기로 온다. 예외가 아니라 상태다.
    naver.maps.Event.addListener(pano, 'pano_status', (status: string) => {
      if (done || status === 'OK') return;
      done = true;
      destroy();
      resolve({ info: null, destroy: () => {} });
    });

    naver.maps.Event.addListener(pano, 'init', () => {
      if (done) return;
      done = true;
      const loc = pano.getLocation?.() ?? {};
      const at = pano.getPosition?.();
      const here = at ? { lat: at.lat(), lng: at.lng() } : null;
      // 파노라마가 선 자리에서 건물을 향하도록 카메라를 돌린다.
      if (here) pano.setPov({ pan: bearingDeg(here, target), tilt: 8, fov: 100 });
      resolve({
        info: {
          panoId: loc.panoId ?? '',
          photodate: loc.photodate,
          address: loc.address,
          title: loc.title,
          distanceM: here ? Math.round(haversineM(here, target)) : undefined,
        },
        destroy,
      });
    });
  });
}

/** 두 좌표 사이 거리(m). 파노라마가 건물에서 얼마나 떨어져 있는지 밝히는 데 쓴다. */
function haversineM(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const r = Math.PI / 180, R = 6371000;
  const dp = (b.lat - a.lat) * r, dl = (b.lng - a.lng) * r;
  const s = Math.sin(dp / 2) ** 2
    + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}
