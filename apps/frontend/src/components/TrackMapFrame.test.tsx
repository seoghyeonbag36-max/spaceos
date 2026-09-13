/**
 * TrackMapFrame — 화면설계서 2판 공통 통과 조건 C-03(접기·펴기 포커스) · C-04(입력칸 Esc).
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import TrackMapFrame from "@/components/TrackMapFrame";

function mount() {
  return render(
    <TrackMapFrame track="posting" label="입점 계산">
      <input aria-label="검색칸" />
    </TrackMapFrame>,
  );
}

describe("TrackMapFrame — 접기·펴기와 키보드", () => {
  it("C-03 접으면 포커스가 펴기 버튼으로, 펴면 접기 버튼으로 간다", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "입점 계산 접기" }));
    const reopen = screen.getByRole("button", { name: "☰ 입점 계산" });
    expect(document.activeElement).toBe(reopen);
    expect(screen.queryByRole("complementary", { name: "입점 계산" })).toBeNull();

    fireEvent.click(reopen);
    expect(screen.getByRole("complementary", { name: "입점 계산" })).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "입점 계산 접기" }));
  });

  it("C-04 입력칸에서 누른 Esc 는 패널을 닫지 않고, 그 밖에서는 닫는다", () => {
    mount();
    const input = screen.getByRole("textbox", { name: "검색칸" });
    input.focus();
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.getByRole("complementary", { name: "입점 계산" })).toBeTruthy();

    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.queryByRole("complementary", { name: "입점 계산" })).toBeNull();
  });
});
