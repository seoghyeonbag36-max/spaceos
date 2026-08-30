import { useEffect, useMemo, useState } from "react";
import DistrictPicker, { CaveatNote, MeasuredValue } from "@/components/DistrictPicker";
import {
  getPlatformProfile, getSentiment, listDistricts, predictVacancy, recommendIndustry,
} from "@/lib/api";
import type {
  DistrictSummary, IndustryRecommend, OpeningSite, PlatformProfile, VacancyForecast, Zone,
} from "@/lib/api";
import "./PlatformConsole.css";

/**
 * Platform 콘솔 — "이 상권은 어떤 플랫폼인가" 를 답하는 화면.
 *
 * Platform 트랙의 본질은 모델 지표가 아니라 두 답이다(2026-08-29 방향 확정):
 *   ① **이 상권은 어떤 플랫폼인가** — 무엇이 모여 있고, 누가·언제 오고,
 *      밖에서 뭐라고 불리며, 어디로 가고 있나 (`/commercial-districts/{id}/platform`)
 *   ② **그 안 어느 자리에 어떤 업소가 들어오면 좋은가** — 실측 공실 자리마다
 *      GNN 최근접 노드 추천
 *
 * 그래서 화면 순서가 곧 답의 순서다: 정체성 → 자리 제안 → (그 답을 뒷받침하는)
 * 모델 근거 → 감성(시드). LSTM·GNN 지표는 근거 자리로 내려가 있다 — 지표가
 * 위에 오면 "이 상권이 어떤 곳인가"라는 질문에 MAE 로 답하는 화면이 된다.
 *
 * 값 옆에 그 값의 한계를 같이 싣는다:
 *   · 유형 라벨은 규칙과 함께 — 묶음이 근거를 가리지 않게 군을 펼쳐 볼 수 있다.
 *   · 예측 단위는 vac_proxy 다. %는 delta 가산 **근사**로만 쓴다.
 *   · GNN 은 Top-3 만 보면 과대평가되므로 거점 사전확률 대비로 같이 읽힌다.
 *   · 감성은 전부 시드라 정체성 근거에 섞지 않고 맨 아래 별도 영역에 둔다.
 */

const DEFAULT_DISTRICT = "garosugil";
const QUARTERS = [1, 2, 3, 4];
const SITES_PAGE = 9;

/** 업종 군 색 — 순위 순서대로 집는다(군 이름에 색을 고정하면 거점마다 범례가 뒤바뀐다) */
const GROUP_COLORS = [
  "#3A5A98", "#0EA5B7", "#22B07D", "#E0A13E", "#B07AA1",
  "#7C9BC7", "#D9736A", "#6BA368", "#9A8CD0", "#C2A25A",
];
const UNGROUPED_COLOR = "#CBD5E1";

/** 분기 코드(20262) → 사람이 읽는 표기(26년 2분기) */
function quarterLabel(q?: string): string {
  if (!q || q.length < 5) return q ?? "—";
  return `${q.slice(2, 4)}년 ${q.slice(4)}분기`;
}
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const signed = (v: number, digits = 3) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}`;

export default function PlatformConsole() {
  const [districts, setDistricts] = useState<DistrictSummary[]>([]);
  const [districtId, setDistrictId] = useState(DEFAULT_DISTRICT);
  const [quarters, setQuarters] = useState(1);
  const [listErr, setListErr] = useState<string | null>(null);

  const [prof, setProf] = useState<PlatformProfile | null>(null);
  const [profErr, setProfErr] = useState<string | null>(null);
  const [fc, setFc] = useState<VacancyForecast | null>(null);
  const [fcErr, setFcErr] = useState<string | null>(null);
  const [rec, setRec] = useState<IndustryRecommend | null>(null);
  const [recErr, setRecErr] = useState<string | null>(null);
  const [zones, setZones] = useState<Zone[] | null>(null);

  const hub = useMemo(
    () => districts.find((d) => d.id === districtId),
    [districts, districtId],
  );

  useEffect(() => {
    let live = true;
    listDistricts()
      .then((all) => {
        if (!live) return;
        setDistricts(all);
        if (all.length && !all.some((d) => d.id === DEFAULT_DISTRICT)) setDistrictId(all[0].id);
      })
      .catch((e) => live && setListErr(String(e)));
    return () => { live = false; };
  }, []);

  // 정체성 + 자리 제안 — 이 화면의 본론
  useEffect(() => {
    let live = true;
    setProf(null); setProfErr(null);
    getPlatformProfile(districtId)
      .then((p) => { if (live) setProf(p); })
      .catch((e) => { if (live) setProfErr(String(e)); });
    return () => { live = false; };
  }, [districtId]);

  // 예측: 분기 선택이 실제 질의를 바꾼다(백엔드가 개월→분기로 환산한다).
  useEffect(() => {
    let live = true;
    setFc(null); setFcErr(null);
    predictVacancy(districtId, quarters * 3)
      .then((r) => { if (live) setFc(r); })
      .catch((e) => { if (live) setFcErr(String(e)); });
    return () => { live = false; };
  }, [districtId, quarters]);

  // 거점 단위 추천(좌표 없이) — 자리 단위는 위 openings 가 자리마다 따로 물어 온다.
  useEffect(() => {
    let live = true;
    setRec(null); setRecErr(null);
    recommendIndustry({ district_id: districtId })
      .then((r) => { if (live) setRec(r); })
      .catch((e) => { if (live) setRecErr(String(e)); });
    return () => { live = false; };
  }, [districtId]);

  useEffect(() => {
    let live = true;
    setZones(null);
    getSentiment(districtId)
      .then((z) => { if (live) setZones(z); })
      .catch(() => { if (live) setZones([]); });
    return () => { live = false; };
  }, [districtId]);

  return (
    <div className="platconsole"><div className="wrap">
      <div className="hd">
        <div className="ey">SPACEOS · PLATFORM</div>
        <h1>이 상권은 어떤 플랫폼인가</h1>
        <div className="sub">
          상권을 하나의 플랫폼으로 본다. 무엇이 모여 있고, 누가·언제 오고, 밖에서 뭐라고
          불리는지로 <b>정체성</b>을 세우고, 그 안 <b>어느 빈 자리에 어떤 업소</b>가 들어오면
          좋은지까지 잇는다. LSTM·GNN 은 그 답을 뒷받침하는 근거로 아래에 둔다.
        </div>
      </div>

      {listErr && (
        <div className="err">
          <strong>거점 목록을 불러오지 못했습니다.</strong>
          <div className="errdetail">{listErr}</div>
        </div>
      )}

      <div className="picker">
        <label className="pk">
          <span>상권</span>
          <DistrictPicker districts={districts} value={districtId}
            onChange={setDistrictId} suffix={(d) => d.gu} />
        </label>
        {hub && (
          <div className="chips">
            <span className="chip">{hub.type}</span>
            <span className="chip">
              공실률 {hub.vacancy_rate.toFixed(1)}%
              <i className={`src ${hub.vacancy_source === "gold" ? "is-gold" : "is-syn"}`}>
                {hub.vacancy_source === "gold" ? "실측" : "합성"}
              </i>
            </span>
            {hub.building_count != null && (
              <span className="chip">건물 {hub.building_count.toLocaleString()}동</span>
            )}
          </div>
        )}
      </div>

      {profErr && (
        <div className="err">
          <strong>이 상권의 Platform 산출물이 없습니다.</strong>
          {/* 404 는 고장이 아니라 **아직 수집하지 않았다**는 뜻이다(경기 거점은 Platform
              트랙이 미착수다). 원시 에러 문자열을 사용자에게 보이면 고장처럼 읽히므로
              404 만 사람 말로 바꾸고, 그 외(5xx·네트워크)는 원문을 남겨 진단을 돕는다. */}
          <div className="errdetail">
            {/404/.test(profErr)
              ? "이 도시에는 아직 Platform 소스(업종 구성·감성·트렌드)를 수집하지 않았다."
              : profErr}
          </div>
        </div>
      )}
      {!profErr && !prof && <div className="loading">상권 정체성 불러오는 중…</div>}

      {prof?.identity && <IdentitySection ident={prof.identity} hub={hub} />}
      {prof && <OpeningsSection openings={prof.openings} />}

      {/* 근거 — 위 두 답을 만든 모델의 성능과 한계 */}
      <h2 className="sec">
        모델 근거
        <small>위 두 답을 만든 모델이다. 지표가 아니라 <b>답</b>이 먼저 오도록 여기에 둔다</small>
      </h2>
      <div className="cols">
        <ForecastCard fc={fc} err={fcErr} quarters={quarters} onQuarters={setQuarters} hub={hub} />
        <RecommendCard rec={rec} err={recErr} />
      </div>

      <SentimentSection zones={zones} hub={hub} />
    </div></div>
  );
}

/* ───────────────── ① 이 상권은 어떤 플랫폼인가 ───────────────── */

function IdentitySection({ ident, hub }: { ident: NonNullable<PlatformProfile["identity"]>; hub?: DistrictSummary }) {
  const { categories: cats, keywords, trends, demand } = ident;
  const total = cats.total || 1;
  const ungroupedN = cats.ungrouped.reduce((s, u) => s + u.n, 0);
  const maxKw = keywords.words[0]?.n ?? 1;
  const bands = demand.bands ?? [];
  const maxBand = Math.max(...bands.map((b) => Math.max(b.flpop, b.selng ?? 0)), 1);
  const maxAge = Math.max(...(demand.ages ?? []).map((a) => a.share), 1);

  return (
    <section className="hero">
      <div className="herotop">
        <div>
          <div className="herolabel">이 상권의 유형</div>
          <div className="heroarch">{ident.archetype ?? "판정할 업종 근거가 없다"}</div>
          <div className="herorule">{ident.archetype_rule}</div>
        </div>
        {hub && (
          <div className="herokpis">
            {demand.store_count != null && (
              <div className="kpi"><div className="l">점포</div><div className="v">{Math.round(demand.store_count).toLocaleString()}<small>곳</small></div></div>
            )}
            {demand.franchise_share != null && (
              <div className="kpi"><div className="l">프랜차이즈</div><div className="v">{demand.franchise_share.toFixed(1)}<small>%</small></div></div>
            )}
            {demand.open_rate != null && demand.close_rate != null && (
              <div className="kpi">
                <div className="l">개업 / 폐업률</div>
                <div className="v">{demand.open_rate.toFixed(1)}<small>/ {demand.close_rate.toFixed(1)}%</small></div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="herogrid">
        {/* 무엇이 모여 있나 */}
        <div className="panel">
          <h3>무엇이 모여 있나<small>업종 구성 {cats.total.toLocaleString()}곳</small></h3>
          <div className="stack">
            {cats.groups.map((g, i) => (
              <i key={g.group} style={{ width: `${(g.n / total) * 100}%`, background: GROUP_COLORS[i % GROUP_COLORS.length] }}
                 title={`${g.group} ${g.n}곳 (${pct(g.share)})`} />
            ))}
            {ungroupedN > 0 && (
              <i style={{ width: `${(ungroupedN / total) * 100}%`, background: UNGROUPED_COLOR }} title={`미분류 ${ungroupedN}곳`} />
            )}
          </div>
          <div className="glegend">
            {cats.groups.map((g, i) => (
              <details key={g.group} className="gitem">
                <summary>
                  <i style={{ background: GROUP_COLORS[i % GROUP_COLORS.length] }} />
                  <b>{g.group}</b>
                  <span>{g.n}곳 · {pct(g.share)}</span>
                </summary>
                {/* 묶음이 근거를 가리지 않게 — 어떤 라벨이 이 군에 들어갔는지 펼쳐 본다 */}
                <div className="gmembers">
                  {g.members.map((m) => <span key={m.label} className="kw">{m.label} {m.n}</span>)}
                </div>
              </details>
            ))}
            {ungroupedN > 0 && (
              <details className="gitem">
                <summary>
                  <i style={{ background: UNGROUPED_COLOR }} />
                  <b>미분류</b>
                  <span>{ungroupedN}곳 · {pct(ungroupedN / total)}</span>
                </summary>
                <div className="gmembers">
                  {cats.ungrouped.map((m) => <span key={m.label} className="kw">{m.label} {m.n}</span>)}
                </div>
                <div className="pnote">
                  카카오 라벨에 상호·브랜드가 섞여 오는 자리다. 억지로 분류하지 않고 남긴다.
                </div>
              </details>
            )}
          </div>
        </div>

        {/* 누가·언제 오나 */}
        <div className="panel">
          <h3>누가 · 언제 오나<small>서울 상권분석(TRDAR)</small></h3>
          {demand.ages && demand.ages.length > 0 && (
            <div className="ages">
              {demand.ages.map((a) => (
                <div key={a.band} className="agecol">
                  <div className="agebarwrap">
                    <i style={{ height: `${(a.share / maxAge) * 100}%` }} />
                  </div>
                  <div className="agev">{a.share.toFixed(0)}</div>
                  <div className="agel">{a.band}</div>
                </div>
              ))}
            </div>
          )}
          <div className="minirow">
            {demand.female_share != null && <span className="chip">여성 {demand.female_share.toFixed(1)}%</span>}
            {demand.weekend_flpop != null && <span className="chip">주말 유동 {demand.weekend_flpop.toFixed(1)}%</span>}
            {demand.weekend_selng != null && <span className="chip">주말 매출 {demand.weekend_selng.toFixed(1)}%</span>}
          </div>

          {bands.length > 0 && (
            <>
              <div className="bandhd">시간대 · 유동 대비 매출</div>
              {bands.map((b) => (
                <div key={b.band} className={`bandrow${b.band === demand.peak_band ? " peak" : ""}${b.band === demand.gap_band ? " gap" : ""}`}>
                  <span className="bl">{b.label}</span>
                  <span className="bbar">
                    <i className="f" style={{ width: `${(b.flpop / maxBand) * 100}%` }} />
                    <i className="s" style={{ width: `${((b.selng ?? 0) / maxBand) * 100}%` }} />
                  </span>
                  <span className="bv">
                    {b.band === demand.peak_band ? "최다" : b.band === demand.gap_band ? "빈틈" : ""}
                  </span>
                </div>
              ))}
              <div className="pnote">
                위 막대 = 유동인구 비중, 아래 = 매출 비중. <b>빈틈</b>은 유동 대비 매출이 가장
                낮은 구간(0~6시는 가게가 닫혀 있어 제외)이라, 이 상권이 사람은 있는데
                돈이 안 도는 시간이다.
              </div>
            </>
          )}
        </div>

        {/* 밖에서 뭐라고 불리나 */}
        <div className="panel">
          <h3>밖에서 뭐라고 불리나<small>블로그 언급 · 검색 트렌드</small></h3>
          <div className="kwcloud">
            {keywords.words.map((w) => (
              <span key={w.word} className="kwc"
                style={{ fontSize: `${11 + (w.n / maxKw) * 7}px`, opacity: 0.55 + (w.n / maxKw) * 0.45 }}>
                {w.word}<i>{w.n}</i>
              </span>
            ))}
          </div>
          <div className="pnote">
            블로그 원문 토큰 상위 {keywords.scanned}개 중 일반어 {keywords.dropped}개를 표시에서
            뺐다. 감성 점수가 아니라 <b>언급 빈도</b>다 — 좋다/나쁘다는 여기서 알 수 없다.
          </div>

          {trends.length > 0 && (
            <div className="trends">
              {trends.map((t) => (
                <div key={t.keyword} className="trend">
                  <div className="trhd">
                    <b>{t.keyword}</b>
                    <span className={`trdir ${t.direction}`}>
                      {t.direction === "up" ? "▲ 상승" : t.direction === "down" ? "▼ 하락" : "— 보합"}
                      {" "}{t.change_pct > 0 ? "+" : ""}{t.change_pct}%
                    </span>
                  </div>
                  <Spark points={t.points.map((p) => p.value)} direction={t.direction} />
                  <div className="trmeta">
                    직전 3개월 {t.prior} → 최근 3개월 {t.recent} · 네이버 데이터랩
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="herosrc">근거: {ident.source}</div>
    </section>
  );
}

/** 검색 트렌드 스파크라인 — 값의 절대 눈금이 아니라 흐름을 보여주는 용도다. */
function Spark({ points, direction }: { points: number[]; direction: string }) {
  if (points.length < 2) return null;
  const w = 100, h = 28;
  const min = Math.min(...points), max = Math.max(...points);
  const span = Math.max(1e-9, max - min);
  const d = points
    .map((v, i) => `${(i / (points.length - 1)) * w},${h - ((v - min) / span) * (h - 4) - 2}`)
    .join(" ");
  const color = direction === "up" ? "#E03E36" : direction === "down" ? "#2E6FB7" : "#8A93A0";
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden>
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.6"
        strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/* ───────────────── ② 어느 자리에 어떤 업소가 ───────────────── */

function OpeningsSection({ openings }: { openings: PlatformProfile["openings"] }) {
  const [shown, setShown] = useState(SITES_PAGE);
  const sites = openings.sites;
  // 한 지번에 자리가 여럿이면 이름이 똑같이 찍힌다(신사동 552-19 가 3곳). 좌표가 다른
  // 별개의 자리인데 화면에서는 중복 버그처럼 보이므로, 겹칠 때만 유닛 번호를 붙인다.
  const dupNames = useMemo(() => {
    const seen = new Map<string, number>();
    sites.forEach((s) => seen.set(s.name, (seen.get(s.name) ?? 0) + 1));
    return seen;
  }, [sites]);

  return (
    <>
      <h2 className="sec">
        어느 자리에 어떤 업소가 들어오면 좋나
        <small>
          공실 {openings.unit_count}곳 · 추천이 붙은 자리 {openings.matched_count}곳
          (반경 {openings.match_radius_m}m 안 그래프 노드 기준) ·
          <b> 상권 평균과 가장 다른 자리부터</b>
        </small>
      </h2>

      {sites.length === 0 && <div className="loading">이 상권에는 실측 공실 자리가 없다.</div>}

      <div className="sites">
        {sites.slice(0, shown).map((s) => (
          <SiteCard key={s.unit_id} site={s}
            seq={(dupNames.get(s.name) ?? 0) > 1 ? s.unit_id.split("-").pop() ?? null : null} />
        ))}
      </div>

      {sites.length > shown && (
        <button className="more" onClick={() => setShown((n) => n + SITES_PAGE)}>
          자리 {sites.length - shown}곳 더 보기
        </button>
      )}

      <div className="sitesrc">
        {openings.source}
        {openings.distinct_note && <><br />{openings.distinct_note}</>}
        <br />
        ⚠ <b>직전 업종과 추천 업종은 눈금이 다르다</b> — 직전 업종은 상가정보 분류,
        추천은 GNN 7군이다. 둘이 다르다고 그 자체로 &ldquo;업종 전환&rdquo;을 뜻하지 않는다.
      </div>
    </>
  );
}

function SiteCard({ site, seq }: { site: OpeningSite; seq: string | null }) {
  const max = site.recommendations[0]?.score ?? 1;
  return (
    <div className="site">
      <div className="sitehd">
        <span className="sname" title={site.name}>
          {site.name}{seq && <em> · 자리 {seq}</em>}
        </span>
        {site.matched_distance_m != null && (
          <span className="sdist">{Math.round(site.matched_distance_m)}m</span>
        )}
      </div>
      <div className="smeta">
        {site.area_py != null && `${site.area_py}평`}
        {site.floor && ` · ${site.floor}`}
        {site.capacity != null && ` · ${site.capacity}호 중 공실 ${site.vacancy_rate?.toFixed(0)}%`}
      </div>

      {site.recommendations.length > 0 ? (
        <div className="srecs">
          {site.recommendations.map((r, i) => (
            <div key={r.industry} className={`srec${i === 0 ? " top" : ""}`}>
              <span className="ri">{r.industry}</span>
              <span className="rb"><i style={{ width: `${(r.score / max) * 100}%` }} /></span>
              <span className="rs">{pct(r.score)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="snorec">
          반경 안에 그래프 노드가 없다 — 거점 평균으로 채우지 않는다.
        </div>
      )}

      {/* 이 자리만의 신호 — 상권 평균을 뺀 값. 없으면 그리지 않는다(0 을 신호처럼 보이게 하지 않는다) */}
      {site.distinct && (
        <div className="sdistinct">
          상권 평균 대비 <b>{site.distinct.industry}</b>
          <span>+{site.distinct.delta_pp}p</span>
        </div>
      )}

      {site.was && <div className="swas">직전 업종 <b>{site.was}</b></div>}
    </div>
  );
}

/* ───────────────── 근거 ①: LSTM 공실 예측 ───────────────── */

function ForecastCard({ fc, err, quarters, onQuarters, hub }: {
  fc: VacancyForecast | null; err: string | null;
  quarters: number; onQuarters: (q: number) => void; hub?: DistrictSummary;
}) {
  const stub = fc?.model === "lstm-stub";
  // 공실률(%)은 예측의 단위가 아니다 — delta 를 현재 공실률에 가산한 **근사**로만 쓴다.
  // 백엔드 services/districts._predicted 와 같은 식이라 거점 대시보드 값과 어긋나지 않는다.
  const approxPct = fc && hub
    ? Math.max(0, Math.min(100, hub.vacancy_rate + fc.delta))
    : null;
  const maxAbs = fc
    ? Math.max(...fc.horizons.map((h) => Math.abs(h.forecast_vac_proxy)), 0.001)
    : 1;
  const holdout = fc?.district_holdout;
  const mae = fc?.metrics?.holdout_mae;
  const absErr = holdout ? Math.abs(holdout.pred - holdout.actual) : null;

  return (
    <section className="card">
      <div className="chead">
        <h2>공실 예측 <span className="badge is-model">LSTM</span></h2>
        {fc && !stub && (
          <div className="cmeta">{fc.model} · {fc.trained_at?.slice(0, 10) ?? "학습일 미상"}</div>
        )}
      </div>

      <div className="seg" role="tablist">
        {QUARTERS.map((q) => (
          <button key={q} className={quarters === q ? "on" : ""} onClick={() => onQuarters(q)}>
            +{q}분기
          </button>
        ))}
      </div>

      {err && <div className="empty">이 거점의 예측 산출물이 없다{/404/.test(err)
        ? " — LSTM 은 서울 54거점 pooled 로 학습돼 경기 거점 예측이 없다."
        : <> — <code>{err}</code></>}</div>}
      {!err && !fc && <div className="empty">예측 불러오는 중…</div>}
      {stub && <div className="empty">Gold 미적재 폴백(<code>lstm-stub</code>) — 실측 예측이 아니다.</div>}

      {fc && !stub && (
        <>
          <div className="big">
            <div className="bigval">
              {fc.forecast_vac_proxy.toFixed(3)}
              <small>vac_proxy · {quarterLabel(fc.forecast_quarter ?? fc.horizons[fc.horizon_quarters - 1]?.quarter)}</small>
            </div>
            <div className={`bigdelta ${fc.direction}`}>
              {fc.direction === "up" ? "▲" : "▼"} {signed(fc.delta)}
              <small>마지막 관측 {quarterLabel(fc.last_quarter)} 대비</small>
            </div>
          </div>

          {/* 단위를 숨기지 않는다 — %는 예측의 단위가 아니라 파생 근사다 */}
          {approxPct != null && hub && (
            <div className="approx">
              <div className="approxv">
                공실률 환산 <b>{hub.vacancy_rate.toFixed(1)}%</b> → <b>{approxPct.toFixed(1)}%</b>
              </div>
              <div className="note">
                예측의 단위는 vac_proxy 다. %는 delta 를 현재 공실률에 가산한 <b>근사</b>이고,
                거점 대시보드의 예측 배지와 같은 식으로 계산한다.
              </div>
            </div>
          )}

          <div className="hz">
            {fc.horizons.map((h, i) => {
              const w = (Math.abs(h.forecast_vac_proxy) / maxAbs) * 50;
              const neg = h.forecast_vac_proxy < 0;
              const on = i + 1 === fc.horizon_quarters;
              return (
                <div key={h.quarter} className={`hzrow${on ? " on" : ""}${i > 0 ? " recur" : ""}`}>
                  <span className="hzq">{quarterLabel(h.quarter)}</span>
                  <span className="hzbar">
                    <i className="zero" />
                    <i
                      className="fill"
                      style={neg ? { right: "50%", width: `${w}%` } : { left: "50%", width: `${w}%` }}
                    />
                  </span>
                  <span className="hzv">{h.forecast_vac_proxy.toFixed(3)}</span>
                </div>
              );
            })}
            <div className="hznote">
              +1분기만 관측 피처로 민 것이다. <b>+2분기부터는 외생 피처를 마지막 관측값으로
              고정한 재귀 예측</b>이라 뒤로 갈수록 불확실하다(연한 행).
            </div>
          </div>

          {/* 전체 MAE 옆에 이 거점의 홀드아웃 1점을 붙인다 — 평균 뒤에 거점 오차를 숨기지 않는다 */}
          <div className="evid">
            <div className="evidh">검증 근거</div>
            <div className="row">
              <span>홀드아웃 MAE / RMSE (전 거점)</span>
              <span>{mae?.toFixed(3) ?? "—"} / {fc.metrics?.holdout_rmse?.toFixed(3) ?? "—"}</span>
            </div>
            {holdout && absErr != null && (
              <>
                <div className="row">
                  <span>이 거점 홀드아웃 · 예측 → 실측</span>
                  <span>{holdout.pred.toFixed(3)} → {holdout.actual.toFixed(3)}</span>
                </div>
                <div className="row">
                  <span>이 거점 오차</span>
                  <span className={mae != null && absErr > mae ? "worse" : "better"}>
                    {absErr.toFixed(3)}
                    {mae != null && (absErr > mae ? " · 전체 평균보다 나쁨" : " · 전체 평균보다 좋음")}
                  </span>
                </div>
              </>
            )}
            <div className="evidnote">
              방향정확도는 <b>싣지 않는다</b> — 홀드아웃이 거점당 1분기뿐이라 한 거점만 뒤집혀도
              크게 흔들려 게이트 지표에서 내렸다. 주지표는 MAE다.
            </div>
          </div>

          {fc.ground_anchor && (
            <div className="anchor">
              <div className="evidh">지상검증 앵커 <span className="badge is-ground">실측</span></div>
              <div className="row">
                <span>건물 실측 공실률</span>
                <span>
                  {fc.ground_anchor.estimated_vacancy_pct?.toFixed(1)}%
                  {fc.ground_anchor.buildings_used
                    ? ` · ${fc.ground_anchor.buildings_used.toLocaleString()}동`
                    : ""}
                </span>
              </div>
              {fc.ground_anchor.anchor_street_pct != null && (
                <div className="row">
                  <span>R-ONE 앵커</span>
                  <span>{fc.ground_anchor.anchor_street_pct.toFixed(1)}%</span>
                </div>
              )}
              <div className="evidnote">{fc.ground_anchor.source} · {fc.ground_anchor.as_of}</div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

/* ───────────────── 근거 ②: GNN 업종 추천 ───────────────── */

function RecommendCard({ rec, err }: { rec: IndustryRecommend | null; err: string | null }) {
  const stub = rec?.model === "gnn-stub";
  const m = rec?.metrics ?? null;
  const top1 = m?.test_top1, prior1 = m?.baseline_district_prior_top1;
  const top3 = m?.test_top3, prior3 = m?.baseline_district_prior_top3;
  const lift3 = top3 != null && prior3 ? ((top3 - prior3) / prior3) * 100 : null;
  const max = rec?.recommendations.length ? rec.recommendations[0].score : 1;

  return (
    <section className="card">
      <div className="chead">
        <h2>업종 추천 <span className="badge is-model">GNN</span></h2>
        {rec && !stub && (
          <div className="cmeta">
            {rec.scope === "district" ? "상권 전체 노드 평균" : "최근접 자리"}
            {m?.nodes ? ` · 노드 ${m.nodes.toLocaleString()}개` : ""}
          </div>
        )}
      </div>

      {err && <div className="empty">이 거점의 추천 산출물이 없다{/404/.test(err)
        ? " — GNN 노드·엣지가 이 거점에는 아직 없다."
        : <> — <code>{err}</code></>}</div>}
      {!err && !rec && <div className="empty">추천 불러오는 중…</div>}
      {stub && <div className="empty">Gold 미적재 폴백(<code>gnn-stub</code>) — 실측 추천이 아니다.</div>}
      {rec && !stub && rec.recommendations.length === 0 && (
        <div className="empty">이 거점에는 추천할 그래프 노드가 없다.</div>
      )}

      {rec && !stub && rec.recommendations.length > 0 && (
        <>
          <div className="recs">
            {rec.recommendations.map((r, i) => (
              <div key={r.industry} className={`recrow${i === 0 ? " top" : ""}`}>
                <span className="rank">{i + 1}</span>
                <span className="rind">{r.industry}</span>
                <span className="rbar"><i style={{ width: `${(r.score / max) * 100}%` }} /></span>
                <span className="rsc">{pct(r.score)}</span>
              </div>
            ))}
          </div>
          <div className="recnote">
            상권 전체 노드의 평균이라 <b>이 플랫폼의 성향</b>을 뜻한다. 자리마다의 답은
            위 「어느 자리에 어떤 업소가」가 좌표로 물어 온 것이다.
          </div>

          <div className="evid">
            <div className="evidh">검증 근거 <span className="badge is-warn">prior 대비로 읽을 것</span></div>
            <div className="row">
              <span>Top-1 정확도 / 상권 사전확률</span>
              <span>
                {top1 != null ? pct(top1) : "—"} / {prior1 != null ? pct(prior1) : "—"}
                {m?.lift_vs_district_prior_pct != null && <b> (+{m.lift_vs_district_prior_pct}%)</b>}
              </span>
            </div>
            <div className="row">
              <span>Top-3 정확도 / 상권 사전확률</span>
              <span>
                {top3 != null ? pct(top3) : "—"} / {prior3 != null ? pct(prior3) : "—"}
                {lift3 != null && <b> (+{lift3.toFixed(1)}%)</b>}
              </span>
            </div>
            {m?.test_offprior_top3 != null && (
              <div className="row">
                <span>사전확률과 답이 갈리는 자리의 Top-3</span>
                <span className="worse">
                  {pct(m.test_offprior_top3)}
                  {m.offprior_nodes ? ` · ${m.offprior_nodes.toLocaleString()}노드` : ""}
                </span>
              </div>
            )}
            <div className="evidnote">
              Top-3 만 보면 과대평가된다 — 상권에서 가장 흔한 업종 셋을 그냥 찍어도
              {prior3 != null ? ` ${pct(prior3)}` : " 약 89%"} 다. 모델의 기여는 그 위의 lift 이고,
              사전확률과 답이 갈리는 자리에서는
              {m?.test_offprior_top3 != null ? ` ${pct(m.test_offprior_top3)}` : ""} 로 떨어진다.
              그게 이 모델의 현재 한계다.
            </div>
          </div>
        </>
      )}
    </section>
  );
}

/* ───────────────── 감성 (시드) ───────────────── */

function SentimentSection({ zones, hub }: { zones: Zone[] | null; hub?: DistrictSummary }) {
  return (
    <section className="seedwrap">
      <div className="seedhd">
        <h2>감성 구역 <span className="badge is-seed">시드</span></h2>
        <div className="seednote">
          <b>전부 추정치다.</b> 리뷰 수집기가 아직 없어 점수·표본 수·증감이 모두 손으로 넣은
          시드값이고, 블로그 코퍼스는 상권 단위 광고성 스니펫이라 구역 단위 감성으로 못 내린다.
          그래서 <b>위 정체성의 근거에 넣지 않았다</b> — 리뷰 수집이 붙으면 &ldquo;밖에서 뭐라고
          불리나&rdquo;가 언급 빈도에서 감성으로 올라선다.
        </div>
      </div>
      {hub && <CaveatNote district={hub} />}
      {hub && (
        <div className="seedsum">
          거점 감성 <MeasuredValue value={hub.sentiment} unit="pt" /> ·
          위험 구역 {hub.risk_zones ?? "—"}곳 ·
          가정 표본 {hub.reviews === null || hub.reviews === undefined
            ? <span className="value-absent">없음</span> : `${hub.reviews.toLocaleString()}건`}
        </div>
      )}
      {!zones && <div className="empty">감성 구역 불러오는 중…</div>}
      {zones && zones.length === 0 && <div className="empty">이 거점의 감성 구역이 없다.</div>}
      <div className="zones">
        {(zones ?? []).map((z) => (
          <div key={z.id} className="zone">
            <div className="zhead">
              <span className="zname">{z.n}</span>
              <span className="zscore">{z.s.toFixed(1)}</span>
            </div>
            <div className="zmeta">
              {z.grp} · 가정 표본 {z.r.toLocaleString()}건 · {z.d >= 0 ? "▲" : "▼"}
              {Math.abs(z.d).toFixed(1)}
            </div>
            <div className="zkw">
              {z.f.map(([label, delta], i) => <span key={i} className="kw">{label} {delta}</span>)}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
