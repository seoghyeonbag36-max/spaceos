/**
 * 계정 화면의 실패 문구 — 상태 코드 → 화면 문장 (2026-09-23 B9).
 *
 * 한곳에 모은 이유: 같은 401 이 로그인에서는 "비밀번호가 틀렸다"이고 키 화면에서는
 * "로그인이 만료됐다"다. 화면마다 따로 적으면 한쪽만 고쳐져 같은 상황을 두 문장으로 말하게 된다.
 * 백엔드의 detail 문자열을 그대로 띄우지 않는 이유도 같다 — 422 는 detail 이 배열이라
 * 화면에 옮길 수 없고, 문구를 백엔드에 맡기면 이 표가 무엇을 보여 주는지 프론트가 모른다.
 */
import { ApiError } from "@/lib/api";

export const NETWORK_TEXT = "서버에 연결하지 못했습니다. 네트워크를 확인하고 다시 시도해 주세요.";

function common(err: unknown, action: string): string {
  if (!(err instanceof ApiError)) return `${action} 못했습니다. 다시 시도해 주세요.`;
  if (err.status === 0) return NETWORK_TEXT;
  if (err.status >= 500) return `서버 오류로 ${action} 못했습니다(HTTP ${err.status}). 잠시 뒤 다시 시도해 주세요.`;
  return `${action} 못했습니다(HTTP ${err.status}).`;
}

/** 로그인 실패. 이메일이 없는지 비밀번호가 틀렸는지는 **가르지 않는다** — 백엔드와 같은 이유로,
 *  가르면 어떤 이메일이 가입돼 있는지 캐내는 데 쓰인다. */
export function loginErrorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "이메일 또는 비밀번호가 올바르지 않습니다.";
    if (err.status === 422) return "이메일 형식을 확인해 주세요.";
  }
  return common(err, "로그인하지");
}

/** 가입 실패. 409 는 화면이 「로그인으로」 버튼을 같이 띄운다(isAlreadyRegistered). */
export function signupErrorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) return "이미 가입된 이메일입니다. 이 이메일로 로그인해 주세요.";
    if (err.status === 422) {
      return "입력값을 서버가 받지 않았습니다. 이메일 형식, 비밀번호 8자 이상, 조직 이름(1~200자)을 확인해 주세요.";
    }
  }
  return common(err, "가입하지");
}

export const isAlreadyRegistered = (err: unknown) => err instanceof ApiError && err.status === 409;

/** 토큰이 만료됐거나 계정이 사라졌다 — 키 화면은 토큰을 지우고 로그인 안내로 돌아간다. */
export const isSessionExpired = (err: unknown) => err instanceof ApiError && err.status === 401;
export const SESSION_EXPIRED_TEXT = "로그인이 만료됐습니다. 다시 로그인해 주세요.";

/** 키 목록·발급·폐기 실패. 401 은 여기 오기 전에 isSessionExpired 로 따로 처리한다. */
export function apiKeyErrorText(err: unknown, action: "불러오지" | "발급하지" | "폐기하지"): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return "키 발급·폐기는 조직 관리자만 할 수 있습니다.";
    if (err.status === 404 && action === "폐기하지") return "이미 없는 키입니다. 목록을 새로 불러왔습니다.";
    if (err.status === 422 && action === "발급하지") return "키 이름을 1~100자로 적어 주세요.";
  }
  return common(err, `키를 ${action}`);
}
