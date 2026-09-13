/**
 * DistrictPicker — 화면설계서 2판 C-05: 상권을 바꾸면 스크린리더가 "상권 {이름} 선택됨" 을 읽는다.
 * 처음 그릴 때는 말하지 않는다(바뀐 것이 없다).
 */
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import DistrictPicker from "@/components/DistrictPicker";
import { district } from "@/test/fixtures";

const HUBS = [district("a", { name: "가로수길" }), district("b", { name: "연남동" })];

function Harness() {
  const [value, setValue] = useState("a");
  return <DistrictPicker districts={HUBS} value={value} onChange={setValue} ariaLabel="상권 선택" />;
}

describe("DistrictPicker — 선택 알림", () => {
  it("C-05 처음에는 조용하고, 바꾸면 새 상권 이름을 알린다", () => {
    const { container } = render(<Harness />);
    const live = container.querySelector("[aria-live='polite']")!;
    expect(live.textContent).toBe("");
    fireEvent.change(screen.getByRole("combobox", { name: "상권 선택" }), { target: { value: "b" } });
    expect(live.textContent).toBe("상권 연남동 선택됨");
    // 알림 자리는 role 을 갖지 않는다 — 화면마다 있는 role="status" 와 겹치지 않게.
    expect(live.getAttribute("role")).toBeNull();
  });
});
