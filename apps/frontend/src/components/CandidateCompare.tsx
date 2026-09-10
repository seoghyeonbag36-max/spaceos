import { useEffect, useRef } from "react";
import "./CandidateCompare.css";

export interface BuildingCandidate {
  id: string;
  name: string;
  statusLabel: string;
  industry: string;
  capacity: number;
  active: number;
  floors?: number;
  vacancyRate: number | null;
}

interface Props {
  districtName: string;
  candidates: BuildingCandidate[];
  notes: Record<string, string>;
  onNote: (id: string, value: string) => void;
  onRemove: (id: string) => void;
  onReview?: (id: string) => void;
  onClose: () => void;
}

/** 저장한 동일 거점 건물만 비교한다. 숫자의 출처와 사용자 메모는 각각 표시한다. */
export default function CandidateCompare({ districtName, candidates, notes, onNote, onRemove, onReview, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    node?.showModal();
    return () => { node?.close(); previousFocus?.focus(); };
  }, []);

  return (
    <dialog ref={dialog} className="candidate-dialog" aria-labelledby="candidate-title"
      onCancel={(e) => { e.preventDefault(); onClose(); }}>
      <header>
        <div><span className="candidate-eyebrow">PAGE · 후보 비교</span>
          <h2 id="candidate-title">{districtName}에서 고른 건물</h2></div>
        <button type="button" onClick={onClose} aria-label="후보 비교 닫기" autoFocus>닫기</button>
      </header>
      <p className="candidate-source">실측 자료 기반 공실 추정 · 동일 거점 건물 비교 · 층별 매물과는 다른 단위입니다.</p>
      {candidates.length === 0 ? <p className="candidate-empty">저장한 후보가 없습니다. 건물 목록에서 후보를 골라 주세요.</p> : (
        <div className="candidate-table-wrap">
          <table>
            <caption className="candidate-sr">건물별 상태·업종·수용 호실·지상 층수와 사용자 메모</caption>
            <thead><tr><th scope="col">비교 항목</th>{candidates.map((c) => <th scope="col" key={c.id}>{c.name}</th>)}</tr></thead>
            <tbody>
              <tr><th scope="row">공실 상태</th>{candidates.map((c) => <td key={c.id}>{c.statusLabel}</td>)}</tr>
              <tr><th scope="row">공실률(추정)</th>{candidates.map((c) => <td key={c.id}>{c.vacancyRate === null ? "산정 불가" : `${c.vacancyRate}%`}</td>)}</tr>
              <tr><th scope="row">상가 수용 / 영업</th>{candidates.map((c) => <td key={c.id}>{c.capacity}호 / {c.active}호</td>)}</tr>
              <tr><th scope="row">대표 업종</th>{candidates.map((c) => <td key={c.id}>{c.industry || "미상"}</td>)}</tr>
              <tr><th scope="row">지상 층수</th>{candidates.map((c) => <td key={c.id}>{c.floors && c.floors > 0 ? `${c.floors}층` : "확인되지 않음"}</td>)}</tr>
              <tr><th scope="row">선택한 이유<br /><small>직접 작성한 메모</small></th>{candidates.map((c) => <td key={c.id}>
                <textarea aria-label={`${c.name} 선택 이유`} maxLength={500} value={notes[c.id] ?? ""}
                  placeholder="답사 때 확인할 점을 남겨 보세요" onChange={(e) => onNote(c.id, e.target.value)} />
              </td>)}</tr>
              <tr><th scope="row">다음 단계</th>{candidates.map((c) => <td key={c.id}>
                {onReview && <button className="candidate-primary" onClick={() => onReview(c.id)}>{c.name} 입점 검토</button>}
                <button onClick={() => onRemove(c.id)} aria-label={`${c.name} 후보 해제`}>후보 해제</button>
              </td>)}</tr>
            </tbody>
          </table>
        </div>
      )}
      <p className="candidate-footnote">후보와 메모는 현재 작업 중에 유지되며, 새로고침하면 초기화됩니다. 입점 검토에서는 계산 가능한 건물 유닛을 다시 확인합니다.</p>
    </dialog>
  );
}
