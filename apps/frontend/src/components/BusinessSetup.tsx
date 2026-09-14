/**
 * 「내 사업」 카드 + 칩 — 화면설계서 3판 공통 프레임.
 *
 * 처음 방문이면 지도 위에 카드를 펴고, 설정하면 오른쪽 위 칩으로 접는다. 모달이 아니다 —
 * 카드가 떠 있어도 지도·패널을 그대로 쓸 수 있다(「그냥 둘러보기」는 언제나 눌린다).
 * 단계를 넘기는 마법사가 아니라 위에서 아래로 채우는 카드 하나다.
 */
import { useEffect, useId, useRef, useState } from "react";
import DistrictPicker from "@/components/DistrictPicker";
import type { DistrictSummary, IndustryOption } from "@/lib/api";
import { GOALS, businessChipText, type BusinessGoal, type BusinessProfile, type BusinessState } from "@/lib/businessProfile";
import { isEditableTarget } from "@/lib/keyboard";
import "./BusinessSetup.css";

export interface BusinessSetupProps {
  state: BusinessState;
  /** null = 불러오는 중 · "error" = 실패 */
  industries: IndustryOption[] | null | "error";
  districts: DistrictSummary[];
  /** 지금 공유 상권 — 지금 가게 상권 칸의 첫 값 */
  districtId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onStart: (profile: BusinessProfile) => void;
  onBrowse: () => void;
}

export default function BusinessSetup({
  state, industries, districts, districtId, open, onOpenChange, onStart, onBrowse,
}: BusinessSetupProps) {
  const id = useId();
  const cardId = `biz-card-${id}`;
  const saved = state.status === "set" ? state.profile : null;
  const [goal, setGoal] = useState<BusinessGoal | null>(saved?.goal ?? null);
  const [industryKey, setIndustryKey] = useState<string | null>(saved?.industryKey ?? null);
  const [home, setHome] = useState<string>(saved?.homeDistrictId ?? districtId);
  const list = Array.isArray(industries) ? industries : null;

  // 카드를 다시 펼 때는 저장된 값에서 시작한다(칩으로 연 편집이 이전 편집의 잔여를 들고 오지 않게).
  const wasOpen = useRef(open);
  useEffect(() => {
    if (open && !wasOpen.current) {
      setGoal(saved?.goal ?? null);
      setIndustryKey(saved?.industryKey ?? null);
      setHome(saved?.homeDistrictId ?? districtId);
    }
    wasOpen.current = open;
  }, [open, saved, districtId]);

  // 접기·펴기 뒤 포커스를 짝 버튼으로(공통 프레임 C-03 과 같은 규칙). 첫 렌더는 건너뛴다.
  const chipRef = useRef<HTMLButtonElement>(null);
  const headRef = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    (open ? headRef.current : chipRef.current)?.focus();
  }, [open]);

  // Esc — 카드가 가장 위의 한 겹이다. 입력칸에 포커스가 있으면 닫지 않는다.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || isEditableTarget(e.target)) return;
      e.stopImmediatePropagation();
      if (state.status === "unset") onBrowse(); else onOpenChange(false);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, state.status, onBrowse, onOpenChange]);

  const needsHome = goal === "pivot" || goal === "move";
  const homeOk = !needsHome || districts.some((d) => d.id === home);
  const ready = !!goal && !!industryKey && !!list?.some((i) => i.key === industryKey) && homeOk;
  const chipText = businessChipText(state, list, districts);

  return (
    <div className="biz">
      <button ref={chipRef} type="button" className={"biz-chip" + (state.status === "set" ? " is-set" : "")}
        aria-expanded={open} aria-controls={cardId} onClick={() => onOpenChange(!open)} title={chipText}>
        <span className="biz-chip-text">{chipText}</span> <span aria-hidden>▾</span>
      </button>

      {open && (
        <section id={cardId} className="biz-card" aria-labelledby={`${cardId}-h`}>
          <h2 id={`${cardId}-h`} ref={headRef} tabIndex={-1}>무엇을 하려고 하세요?</h2>
          <p className="biz-sub">업종과 지금 가게를 알려주면 네 화면이 그 기준으로 답합니다. 이 브라우저에만 저장됩니다.</p>

          <fieldset className="biz-goals">
            <legend className="sr-only">목적</legend>
            {GOALS.map((g) => (
              <label key={g.key} className={"biz-goal" + (goal === g.key ? " on" : "")}>
                <input type="radio" name={`${cardId}-goal`} value={g.key} checked={goal === g.key}
                  onChange={() => setGoal(g.key)} />
                <b>{g.label}</b>
                <span>{g.hint}</span>
              </label>
            ))}
          </fieldset>

          <fieldset className="biz-inds" disabled={!list}>
            <legend>{goal === "pivot" ? "지금 업종은 무엇인가요?" : "어떤 업종인가요?"}</legend>
            {industries === "error" && (
              <p className="biz-error" role="alert">업종 목록을 불러오지 못했습니다. 「그냥 둘러보기」로 계속할 수 있습니다.</p>
            )}
            {industries === null && <p className="biz-hint">업종 목록 불러오는 중…</p>}
            {list && (
              <div className="biz-ind-grid">
                {list.map((i) => (
                  <label key={i.key} className={"biz-ind" + (industryKey === i.key ? " on" : "")}>
                    <input type="radio" name={`${cardId}-ind`} value={i.key} checked={industryKey === i.key}
                      onChange={() => setIndustryKey(i.key)} />
                    <b>{i.label}</b>
                    {!i.model_label && <small>상권 비교만</small>}
                  </label>
                ))}
              </div>
            )}
          </fieldset>

          {needsHome && (
            <div className="biz-home">
              {/* DistrictPicker 는 id 를 받지 않는다 — 이름은 aria-label 로 잇고, 보이는 글자는 같은 말을 쓴다 */}
              <span className="biz-home-label" aria-hidden>지금 가게 상권</span>
              <DistrictPicker districts={districts} value={home} onChange={setHome}
                className="biz-home-select" ariaLabel="지금 가게 상권" disabled={!districts.length} />
            </div>
          )}

          <div className="biz-actions">
            <button type="button" className="biz-start" disabled={!ready}
              onClick={() => ready && onStart({ goal: goal!, industryKey: industryKey!, homeDistrictId: needsHome ? home : null })}>
              시작
            </button>
            <button type="button" className="biz-browse" onClick={onBrowse}>그냥 둘러보기</button>
          </div>
        </section>
      )}
    </div>
  );
}
