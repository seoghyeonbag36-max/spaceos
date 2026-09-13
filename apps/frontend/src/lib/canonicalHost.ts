/**
 * 정식 주소로 보내기 — 2026-09-13.
 *
 * Firebase Hosting 은 사이트마다 주소를 두 개씩 준다(`*.web.app` · `*.firebaseapp.com`). 사이트도 둘이다
 * (정식 `placeos`, 옛 `spaceos-twin`). 네 주소가 같은 Cloud Run 을 서빙하는데, **네이버 지도 키는 등록된
 * origin 에서만 인증된다.** 등록되지 않은 주소로 들어온 사람은 지도가 회색으로 비고 인증 오류만 본다.
 *
 * 서버 쪽 301 은 옛 사이트의 페이지 경로(`/`)에만 건다(firebase.json) — `/api/**` 까지 돌리면 POST 가
 * 301 에서 GET 으로 바뀌어 옛 주소로 부르던 API 호출이 깨진다. 그리고 Firebase 리다이렉트는 **호스트를
 * 가르지 못해** `placeos.firebaseapp.com` 만 골라 보낼 수 없다. 그 두 빈틈을 여기서 메운다.
 *
 * 경로·쿼리·해시(#admin · #board)는 그대로 붙인다. 로컬 개발·Cloud Run 원본 주소는 건드리지 않는다.
 */
export const CANONICAL_ORIGIN = "https://placeos.web.app";

/** 정식 주소가 아닌 **Firebase 호스트**들. 여기 없는 호스트(localhost·run.app 등)는 그대로 둔다. */
const NON_CANONICAL_HOSTS = new Set([
  "placeos.firebaseapp.com",
  "spaceos-twin.web.app",
  "spaceos-twin.firebaseapp.com",
]);

/** 옮겨야 하면 새 URL, 아니면 null. */
export function canonicalRedirect(loc: Pick<Location, "hostname" | "pathname" | "search" | "hash">): string | null {
  if (!NON_CANONICAL_HOSTS.has(loc.hostname)) return null;
  return `${CANONICAL_ORIGIN}${loc.pathname}${loc.search}${loc.hash}`;
}
