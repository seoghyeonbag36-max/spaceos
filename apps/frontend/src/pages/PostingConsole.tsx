import { useEffect, useMemo, useState } from "react";
import DistrictPicker, { CaveatNote } from "@/components/DistrictPicker";
import {
  BASIS_LABEL, getPostings, listDistricts, recommendIndustry, simulateRevenue,
} from "@/lib/api";
import type {
  DistrictSummary, IndustryRec, Posting, SimulateResult, TierScenario,
} from "@/lib/api";
import "./PostingConsole.css";

/**
 * Posting 콘솔 — "이 자리에 들어가면 얼마가 남나"에 답하는 화면.
 *
 * 백엔드 `POST /ai/simulate-revenue`(services/posting)는 2026-07-18 부터 있었지만
 * **이걸 부르는 화면이 없었다** — `simulateRevenue()` 는 api.ts 에 정의만 되어 있고
 * 호출부가 0건이었다. ProgramStudio 가 `/marketing/generate` 에 표면을 준 것과 같은
 * 자리다(2026-08-29).
 *
 * 이 화면이 여는 것 둘:
 *   ① **권리금(prem) 입력 계약** — 공개 통계가 없고 임대인·기존 임차인과의 협상값이라
 *      그 자리에 들어갈 기업만 안다. 입력란이 없어 지금까지 늘 `absent`(0 전제)로만
 *      계산돼 왔다. 계약은 입력란이 있어야 성립한다.
 *   ② **외부 AI 창업 코파일럿 어댑터** — `POSTING_COPILOT_URL` 이 채워지면 같은 화면이
 *      코파일럿 결과를 그린다. `source`/`source_note` 가 어느 쪽이 돌았는지 밝힌다.
 *
 * 화면 원칙:
 *   · 비용 기준(`basis`)과 입력 출처(`inputs_source`)를 결과 옆에 같이 싣는다 —
 *     실측 임대료와 시드 프록시가 같은 숫자처럼 보이면 안 된다.
 *   · `viable === false` 는 "모른다"가 아니라 "회수가 안 된다"다. 셋 다 안 되면
 *     `unviable_note` 를 그대로 보여주고 추천을 만들지 않는다.
 */

const DEFAULT_DISTRICT = "garosugil";

const TIER_LABEL: Record<string, { name: string; sub: string }> = {
  premium: { name: "고급화", sub: "객단가 높이고 회전 낮게" },
  value: { name: "가성비", sub: "객단가 낮추고 회전 높게" },
  factory: { name: "기능중심", sub: "면적·인력 최소로" },
};

const won = (v: number) => `${Math.round(v).toLocaleString()}만원`;

export default function PostingConsole() {
  const [districts, setDistricts] = useState<DistrictSummary[]>([]);
  const [districtId, setDistrictId] = useState(DEFAULT_DISTRICT);
  const [units, setUnits] = useState<Posting[]>([]);
  const [unitId, setUnitId] = useState<string>("");
  const [industry, setIndustry] = useState("");
  const [prem, setPrem] = useState("");
  const [strategy, setStrategy] = useState("");
  const [recs, setRecs] = useState<IndustryRec[] | null>(null);

  const [result, setResult] = useState<SimulateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const unit = useMemo(() => units.find((u) => u.id === unitId), [units, unitId]);

  useEffect(() => {
    let live = true;
    listDistricts()
      .then((all) => {
        if (!live) return;
        setDistricts(all);
        if (all.length && !all.some((d) => d.id === DEFAULT_DISTRICT)) setDistrictId(all[0].id);
      })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, []);

  // 자리 목록 — 실측 공실 인벤토리(services/vacant_inventory)에서 온다
  useEffect(() => {
    let live = true;
    setUnits([]); setUnitId(""); setResult(null); setRecs(null); setErr(null);
    getPostings(districtId)
      .then((p) => { if (live) { setUnits(p); setUnitId(p[0]?.id ?? ""); } })
      .catch((e) => { if (live) setErr(String(e)); });
    return () => { live = false; };
  }, [districtId]);

  // 자리를 고르면 그 좌표로 GNN 업종 추천을 물어 온다 — 업종 입력의 출발점이다.
  // (Platform 이 자리마다 답하는 것과 같은 질의다. 여기서는 그 답을 비용 계산에 넘긴다.)
  useEffect(() => {
    if (!unit) { setRecs(null); return; }
    let live = true;
    setRecs(null);
    recommendIndustry({ district_id: districtId, lat: unit.lat, lon: unit.lng })
      .then((r) => { if (live && r.model !== "gnn-stub") setRecs(r.recommendations); })
      .catch(() => { if (live) setRecs(null); });   // 404 = 400m 안에 노드 없음
    return () => { live = false; };
  }, [unit, districtId]);

  // 자리가 정해지면 우선 **입력 없이** 한 번 돌려 빈 화면을 만들지 않는다.
  // 이때 prem 은 보내지 않으므로 결과가 `absent`(0 전제)로 온다 — 그 사실은 화면이 밝힌다.
  useEffect(() => {
    if (!unitId) return;
    run({ quiet: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unitId]);

  async function run(opts: { quiet?: boolean } = {}) {
    if (!unitId) return;
    setBusy(true);
    if (!opts.quiet) setErr(null);
    try {
      const parsed = prem.trim() === "" ? undefined : Math.max(0, Number(prem));
      const r = await simulateRevenue({
        district_id: districtId,
        unit_id: unitId,
        industry_type: industry.trim() || undefined,
        strategy: strategy || undefined,
        prem: Number.isFinite(parsed as number) ? (parsed as number) : undefined,
      });
      setResult(r);
    } catch (e) {
      setErr(String(e));
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const tiers = result ? Object.entries(result.scenarios) : [];

  return (
    <div className="postconsole"><div className="wrap">
      <div className="hd">
        <div className="ey">SPACEOS · POSTING</div>
        <h1>이 자리에 들어가면 얼마가 남나</h1>
        <div className="sub">
          실측 공실 자리를 골라 <b>업종·권리금</b>을 넣으면 세 전략(고급화·가성비·기능중심)의
          월 순익과 회수기간을 낸다. 임대료는 R-ONE 실측, 면적은 건축물대장이며,
          <b> 권리금은 공개 통계가 없어 기업이 넣는 입력</b>이다 — 비워 두면 0 을 전제로 계산하고
          결과가 그 사실을 밝힌다.
        </div>
      </div>

      {err && (
        <div className="err">
          <strong>계산에 실패했습니다.</strong>
          <div className="errdetail">{err}</div>
        </div>
      )}

      <div className="cols">
        {/* ── 입력 ── */}
        <form className="panel" onSubmit={(e) => { e.preventDefault(); run(); }}>
          <div className="ptitle">입력</div>

          <label className="field">
            <span className="flabel">상권</span>
            <DistrictPicker districts={districts} value={districtId}
              onChange={setDistrictId} suffix={(d) => d.gu} />
            <CaveatNote district={districts.find((d) => d.id === districtId)} />
          </label>

          <label className="field">
            <span className="flabel">
              자리 <em>실측 {units.length}곳</em>
            </span>
            <select value={unitId} onChange={(e) => setUnitId(e.target.value)} disabled={!units.length}>
              {units.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.n} · {u.area}평 · {u.floor}
                </option>
              ))}
            </select>
            {unit && (
              <span className="fhint">
                임대료 {won(unit.rent)}/월 · 직전 업종 {unit.was || "미상"}
                {unit.foot ? ` · 유동 ${unit.foot}` : ""}
              </span>
            )}
          </label>

          <label className="field">
            <span className="flabel">업종</span>
            <input value={industry} onChange={(e) => setIndustry(e.target.value)}
              placeholder="예: 카페 (비우면 자리 기본값)" />
            {recs && recs.length > 0 && (
              <span className="chips">
                {recs.map((r) => (
                  <button type="button" key={r.industry}
                    className={"chip" + (industry === r.industry ? " on" : "")}
                    onClick={() => setIndustry(r.industry)}>
                    {r.industry} {Math.round(r.score * 100)}%
                  </button>
                ))}
                <i className="chipnote">GNN 추천 — 이 자리 좌표 기준</i>
              </span>
            )}
          </label>

          <label className="field">
            <span className="flabel">권리금 <em>입력 계약</em></span>
            <input value={prem} inputMode="numeric"
              onChange={(e) => setPrem(e.target.value.replace(/[^\d]/g, ""))}
              placeholder="만원 — 비우면 0 전제" />
            <span className="fhint">
              공개 통계가 없다(bronze 전수 확인). 임대인·기존 임차인과의 <b>협상값</b>이라
              그 자리에 들어갈 기업만 안다. 비워 두면 0 을 전제로 계산하고
              결과에 <code>absent</code> 로 표시된다.
            </span>
          </label>

          <label className="field">
            <span className="flabel">전략</span>
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
              <option value="">세 전략 비교</option>
              <option value="premium">고급화</option>
              <option value="value">가성비</option>
              <option value="factory">기능중심</option>
            </select>
          </label>

          <button className="run" type="submit" disabled={busy || !unitId}>
            {busy ? "계산 중…" : "시뮬레이션"}
          </button>
        </form>

        {/* ── 결과 ── */}
        <div className="results">
          {!result && !busy && <div className="empty">자리를 고르면 계산한다.</div>}
          {result && (
            <>
              <div className="rhead">
                <div className="rtitle">
                  {unit?.n ?? result.unit_id}
                  {result.industry_type && <span className="rind">{result.industry_type}</span>}
                </div>
                <div className="rbadges">
                  {/* 코파일럿이 돌았는지 폴백인지 — 안 붙였다와 붙였는데 실패했다를 섞지 않는다 */}
                  <span className={"badge " + (result.source === "copilot" ? "is-copilot" : "is-fallback")}>
                    {result.source === "copilot" ? "코파일럿" : "내부 3-Tier 폴백"}
                  </span>
                  {result.inputs_quarter && <span className="badge is-q">{result.inputs_quarter} 기준</span>}
                </div>
              </div>

              {result.source_note && (
                <div className="note is-warn">
                  <b>코파일럿이 설정돼 있는데 실패했다</b> — 아래는 폴백 계산이다.
                  <div className="notedetail">{result.source_note}</div>
                </div>
              )}

              {result.inputs_source && (
                <div className="inputs">
                  {(["area", "rent", "prem", "foot"] as const).map((k) => (
                    <span key={k} className={"isrc " + srcClass(result.inputs_source![k])}>
                      {{ area: "면적", rent: "임대료", prem: "권리금", foot: "유동" }[k]}
                      <i>{srcLabel(result.inputs_source![k])}</i>
                    </span>
                  ))}
                  {result.inputs_source.floor && (
                    <span className={"isrc " + srcClass(result.inputs_source.floor)}>
                      층<i>{result.inputs_source.floor === "flr_ouln" ? "층별개요 실측" : "1층 가정(상한)"}</i>
                    </span>
                  )}
                </div>
              )}

              {result.unviable_note && <div className="note is-bad">{result.unviable_note}</div>}

              <div className="tiers">
                {tiers.map(([key, s]) => (
                  <TierCard key={key} tierKey={key} s={s} />
                ))}
              </div>

              <div className="rsrc">
                비용 기준: {BASIS_LABEL[tiers[0]?.[1]?.basis] ?? tiers[0]?.[1]?.basis ?? "미상"}
                {" · "}자리 = 건축물대장 실측 공실 인벤토리 · 임대료 = R-ONE ·
                매출 앵커 = KOSIS 서비스업조사 + 공정위 가맹사업 면적
                <br />
                권리금을 넣으면 회수기간이 바뀐다 — 실측 감도(270유닛 전수)로
                <b> 추천 5.2% 뒤집힘 · 회수 가부 판정은 0건 변화</b>였다. 즉 "회수 불가" 결론은
                권리금과 무관하게 성립한다.
              </div>
            </>
          )}
        </div>
      </div>
    </div></div>
  );
}

function TierCard({ tierKey, s }: { tierKey: string; s: TierScenario }) {
  const meta = TIER_LABEL[tierKey] ?? { name: s.name ?? tierKey, sub: s.sub ?? "" };
  return (
    <div className={"tier" + (s.recommended ? " rec" : "") + (s.viable ? "" : " dead")}>
      <div className="thd">
        <span className="tname">{meta.name}</span>
        {s.recommended && <span className="trec">추천</span>}
      </div>
      <div className="tsub">{meta.sub}</div>

      <div className="trow"><span>초기 투자</span><span>{won(s.invest_mn)}</span></div>
      <div className="trow"><span>월 비용</span><span>{won(s.month_cost)}</span></div>
      <div className="trow"><span>월 매출</span><span>{won(s.month_rev)}</span></div>
      <div className="trow big">
        <span>월 순익</span>
        <span className={s.month_net > 0 ? "pos" : "neg"}>{won(s.month_net)}</span>
      </div>
      <div className="trow">
        <span>회수기간</span>
        {/* "모른다"와 "안 된다"는 다른 정보다 — 순익이 0 이하면 회수기간이 정의되지 않는다 */}
        <span>{s.viable ? `${s.roi_months}개월` : "회수 불가"}</span>
      </div>
    </div>
  );
}

/** 입력 출처 라벨 — 프록시를 실측으로 오독하지 않게 한다. 모르는 값은 그대로 노출한다. */
function srcLabel(v: string | undefined): string {
  return ({
    rone: "R-ONE 실측", flpop: "유동 실측", "flpop+seed": "유동+서열",
    "flpop+jipgyegu": "유동 실측(집계구)",
    seed: "시드 프록시", absent: "전제(0)", contract: "기업 입력",
    bldg: "대장 실측", "gold-ledger": "대장 실측", "bldg+split": "대장·균등분할",
  } as Record<string, string>)[v ?? ""] ?? (v ?? "미상");
}
/** 실측(초록) / 프록시(회색 점선) / 전제(노랑 점선). 모르는 값은 프록시로 눕힌다 —
 *  라벨을 모르는 것을 실측으로 올리면 그게 곧 출처 왜곡이다. */
function srcClass(v: string | undefined): string {
  if (["contract", "rone", "flpop", "flpop+jipgyegu", "bldg", "gold-ledger", "flr_ouln"].includes(v ?? "")) {
    return "is-real";
  }
  if (v === "absent") return "is-absent";
  return "is-proxy";
}
