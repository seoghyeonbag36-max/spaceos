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
    // submodules=visualization: 유동인구 HeatMap(naver.maps.visualization.HeatMap) 사용에 필요.
    s.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${keyId}&submodules=visualization`;
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
