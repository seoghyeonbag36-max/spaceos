/**
 * 키보드 공통 규칙 — 화면설계서 2판 §공통 프레임 「키보드」.
 *
 * **입력칸에 포커스가 있으면 Esc 로 아무것도 닫지 않는다.** 검색어를 지우려고 Esc 를 누른
 * 사람의 패널·상세가 눈앞에서 닫히면 쓰던 맥락이 통째로 사라진다. 1판 때는 트랙 패널만 이
 * 규칙을 지키고 Page 는 입력칸에서도 한 겹씩 닫아, 네 화면이 같은 키에 다르게 반응했다.
 */
export function isEditableTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el || typeof el.tagName !== "string") return false;
  return /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable === true;
}
