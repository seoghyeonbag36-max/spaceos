// 네이버 지도 Dynamic Map v3 래퍼
// 키: apps/frontend/.env 의 VITE_NAVER_MAPS_KEY_ID (Client ID = 9nbzrvj8qj)
// ※ NCP 콘솔 > Maps > Application 의 Web 서비스 URL 에 http://localhost:5173 등록 필수.
//   미등록 도메인(file:// 포함)에서는 인증오류로 지도가 표시되지 않는다.

declare global {
  interface Window { naver?: any }
}

let _loading: Promise<void> | null = null;

/** 네이버 지도 JS SDK 동적 로드 (중복 로드 방지) */
export function loadNaverMaps(): Promise<void> {
  if (window.naver?.maps) return Promise.resolve();
  if (_loading) return _loading;
  _loading = new Promise<void>((resolve, reject) => {
    const keyId = import.meta.env.VITE_NAVER_MAPS_KEY_ID;
    if (!keyId) return reject(new Error('VITE_NAVER_MAPS_KEY_ID 미설정 (.env 확인)'));
    const s = document.createElement('script');
    // submodules=visualization: 유동인구 HeatMap(naver.maps.visualization.HeatMap) 사용에 필요.
    s.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${keyId}&submodules=visualization`;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('네이버 지도 SDK 로드 실패 — 도메인 등록/키 확인'));
    document.head.appendChild(s);
  });
  return _loading;
}

/** 상권 중심좌표에 지도 생성 + 공실 마커 표시 */
export async function renderDistrictMap(el: HTMLElement, center: { lat: number; lng: number }, vacancies: Array<{ lat: number; lng: number; score: number }>) {
  await loadNaverMaps();
  const { naver } = window;
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
