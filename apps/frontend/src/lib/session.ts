/**
 * 로그인 세션 — 액세스 토큰(JWT) 하나를 **sessionStorage** 에 둔다 (2026-09-23 B9).
 *
 * ## 왜 sessionStorage 인가
 * - **새로고침은 버틴다.** 메모리에만 두면 새로고침 한 번에 로그아웃된다 — 키 발급 화면을
 *   보다가 지도로 돌아오는 흐름에서 매번 다시 로그인하게 된다.
 * - **탭을 닫으면 사라진다.** 백엔드 토큰은 7일짜리다(config.jwt_expires_minutes). localStorage 에
 *   두면 지자체·중개사무소 공용 PC 에 7일 동안 조직 관리자 권한이 남는다.
 * - httpOnly 쿠키가 XSS 에는 가장 강하지만 백엔드가 Set-Cookie·CSRF 를 새로 가져야 한다 —
 *   B9 범위는 "백엔드를 고치지 않는다"다. 관리자 토큰(AdminCoverage)도 같은 자리를 쓴다.
 *
 * ⚠ **조직 API 키 원문은 여기 두지 않는다.** 원문은 발급 직후 화면의 React 상태에만 있고
 *   화면을 닫으면 사라진다(ProgramStudio 도 키를 입력칸 상태로만 쓴다).
 */
const TOKEN_KEY = "placeos.session.v1";
/** 저장소가 막힌 환경(사생활 보호 모드 등)에서만 쓰는 대체 자리 — 새로고침하면 사라진다 */
let memoryToken: string | null = null;

export function loadToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return memoryToken;
  }
}

export function saveToken(token: string): void {
  try {
    window.sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    memoryToken = token;
  }
}

export function clearToken(): void {
  memoryToken = null;
  try {
    window.sessionStorage.removeItem(TOKEN_KEY);
  } catch { /* 지울 것이 없다 */ }
}
