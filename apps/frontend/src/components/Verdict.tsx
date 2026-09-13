import type { ReactNode } from "react";
import "./Verdict.css";

/**
 * 결론 1줄 + 근거 3줄 — PPPP 네 탭이 같은 자리에서 같은 모양으로 답한다.
 *
 * ## 왜 공용인가
 *
 * 한 화면이 결론·근거·원자료를 동시에 펴면 어느 것도 읽히지 않는다(2026-09-07).
 * 그래서 화면의 첫 화면분(스크롤 없이 보이는 자리)에 들어갈 것을 규칙으로 고정한다:
 *
 *   1. **헤드라인** — 그 탭이 답하는 질문 그대로. Platform "이 입지·상권은 어떤
 *      플랫폼인가" · Page "이 platform 안에 어떤 page 가 만들어져야 하는가" ·
 *      Posting "어떤 가격대의 page 가 posting 되어야 하는가" · Program "posting 한
 *      page 를 어떤 홍보 program 으로 돌릴 것인가"
 *   2. **결론 한 문장** — 그 질문에 대한 답. 두 문장으로 늘리지 않는다.
 *   3. **근거 세 줄** — 그 결론을 세운 값. 네 줄째는 접는 자리다.
 *   4. **출처 줄** — 아래 상세를 접어도 **출처만은 접지 않는다**. 출처가 곧 근거다.
 *
 * ## 지키는 것
 *
 * · 값은 계산한 정밀도 그대로 싣는다. 자리를 아끼려고 반올림하지 않는다 —
 *   글자를 줄이자고 정확도를 깎으면 줄인 의미가 없다.
 * · 원자료는 `Fold` 로 접는다. **접는 것이지 지우는 것이 아니다** — 접힌 자리는
 *   한 번 눌러 그대로 다시 편다.
 */

/** 근거 한 줄. 결론을 세운 값 하나와 그 출처. */
export interface Ground {
  /** 이 줄이 답하는 것 — 예: "무엇이 모여 있나" */
  label: string;
  /** 값. 반올림·요약하지 말고 계산한 그대로 넣는다. */
  value: ReactNode;
  /** 이 값이 어디서 왔나 — 예: "서울 상권분석 TRDAR 상권 단위". 접히지 않는다. */
  source?: ReactNode;
}

export default function Verdict({
  eyebrow, conversion, question, verdict, grounds, sources, note,
}: {
  /** 좌상단 표식 — "PLACEOS · PLATFORM" */
  eyebrow: string;
  /** 전통 4P → 디지털 4P 전환 — "PLACE ▶ PLATFORM" */
  conversion: string;
  /** 이 탭이 답하는 질문. 헤드라인은 질문이지 기능 이름이 아니다. */
  question: string;
  /** 결론 한 문장 */
  verdict: ReactNode;
  /** 근거 줄. 세 줄까지만 편다 — 넘치면 아래 상세로 민다. */
  grounds: Ground[];
  /** 이 화면이 실제로 쓴 소스 전부. 상세를 접어도 여기 남는다. */
  sources?: ReactNode[];
  /** 이 화면을 읽는 법 — 길어서 접지만 지우지는 않는다. */
  note?: ReactNode;
}) {
  const shown = grounds.slice(0, 3);
  const rest = grounds.slice(3);
  return (
    <header className="verdict">
      <div className="vey">{eyebrow}<span className="vconv">{conversion}</span></div>
      <h1 className="vq">{question}</h1>
      <p className="vone">{verdict}</p>

      <ol className="vgrounds">
        {shown.map((g, i) => (
          <li key={i}>
            <span className="gl">{g.label}</span>
            <span className="gv">{g.value}</span>
            {g.source && <span className="gs">{g.source}</span>}
          </li>
        ))}
      </ol>

      {/* 네 줄째부터는 접는다 — 규칙이 세 줄이지 값이 셋인 것은 아니다 */}
      {rest.length > 0 && (
        <details className="vmore">
          <summary>근거 {rest.length}줄 더</summary>
          <ol className="vgrounds">
            {rest.map((g, i) => (
              <li key={i}>
                <span className="gl">{g.label}</span>
                <span className="gv">{g.value}</span>
                {g.source && <span className="gs">{g.source}</span>}
              </li>
            ))}
          </ol>
        </details>
      )}

      {/* 출처는 접지 않는다 — 아래 상세가 전부 접혀 있어도 이 줄은 남는다 */}
      {sources && sources.length > 0 && (
        <div className="vsrc">
          <b>출처</b>
          {sources.map((s, i) => <span key={i}>{s}</span>)}
        </div>
      )}

      {note && <details className="vnote"><summary>이 화면을 읽는 법</summary><div>{note}</div></details>}
    </header>
  );
}

/**
 * 접는 상세 — 결론·근거 아래로 밀린 원자료.
 *
 * `summary` 에는 그 안에 무엇이 몇 개 들어 있는지를 적는다. 접힌 채로도 "여기에
 * 무엇이 있고 얼마나 있나"를 알 수 있어야 접은 것이지, 감춘 것이 아니게 된다.
 */
export function Fold({ title, summary, badge, open, children }: {
  title: string;
  /** 접힌 채로 보이는 한 줄 — 안에 든 것의 수와 핵심 값 */
  summary?: ReactNode;
  /** 제목 옆 표식 — "실측" · "LSTM" 처럼 짧게 */
  badge?: ReactNode;
  /** 기본으로 펼쳐 둘 것인가. 결론에 직접 걸리는 자리에만 쓴다. */
  open?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="vfold" open={open}>
      <summary>
        <span className="ft">{title}</span>
        {badge && <span className="fb">{badge}</span>}
        {summary && <span className="fs">{summary}</span>}
        <span className="fx" aria-hidden />
      </summary>
      <div className="vfoldbody">{children}</div>
    </details>
  );
}
