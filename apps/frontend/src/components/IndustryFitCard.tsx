/**
 * 「내 업종으로 본 상권」 — Platform 패널 맨 위(화면설계서 3판 Platform).
 *
 * 3판의 주요 고객은 업종에서 출발한다. 그래서 「이 상권은 어떤 곳인가」보다 먼저 답한다:
 *   · 창업 · 상권 옮기기 → 내 업종이면 **어느 상권**인가(상권 순위 · 옮기기는 지금 상권 고정 줄)
 *   · 업종 바꾸기        → 지금 상권에서 **무엇으로** 바꾸나(이 상권 업종 순위)
 *
 * ⚠ 입지 적합도는 매출·생존이 아니라 "비슷한 입지에 그 업종이 이미 모여 있는 정도"다(GNN 상권
 *   평균, Top-3 근사). 순위로만 읽는다 — 그 사실을 카드가 늘 한 줄로 적는다. 모델 7종 밖 업종은
 *   순위를 내지 않는다(가까운 업종 점수로 대신 채우지 않는다).
 */
import { useEffect, useId, useState } from "react";
import {
  getDistrictIndustries, getIndustryFit,
  type DistrictIndustries, type DistrictSummary, type IndustryFit, type IndustryFitRow, type IndustryOption,
} from "@/lib/api";
import { GOALS, topic, toward, type BusinessProfile } from "@/lib/businessProfile";
import "./IndustryFitCard.css";

const TOP_N = 5;
const FIT_NOTE = "입지 적합도는 비슷한 입지에 그 업종이 이미 모여 있는 정도를 모델이 배운 값입니다 — 매출·생존율이 아닙니다. 순위로만 읽으세요.";

const pct1 = (v: number | null | undefined) => (v == null || !Number.isFinite(v) ? null : `${(v * 100).toFixed(1)}%`);

export interface IndustryFitCardProps {
  business: BusinessProfile | null;
  industries: IndustryOption[] | null;
  districtId: string;
  districts: DistrictSummary[];
  onDistrictChange: (id: string) => void;
  onOpenBusiness?: () => void;
  onTryIndustry?: (input: string) => void;
}

export default function IndustryFitCard(props: IndustryFitCardProps) {
  const { business, industries, onOpenBusiness } = props;
  const ind = business && industries?.find((i) => i.key === business.industryKey);
  if (!business || !ind) {
    if (!onOpenBusiness) return null;
    return (
      <div className="fitcard fitcard-empty">
        <span>업종을 알려주면 어느 상권이 맞는지부터 보여줍니다.</span>
        <button type="button" onClick={onOpenBusiness}>내 사업 설정</button>
      </div>
    );
  }
  return business.goal === "pivot"
    ? <PivotCard {...props} business={business} ind={ind} />
    : <DistrictRankCard {...props} business={business} ind={ind} />;
}

type CardProps = IndustryFitCardProps & { business: BusinessProfile; ind: IndustryOption };

function Eyebrow({ goal }: { goal: BusinessProfile["goal"] }) {
  return <div className="fit-eyebrow">내 업종으로 본 상권 · {GOALS.find((g) => g.key === goal)?.label}</div>;
}

/* ── 창업 · 상권 옮기기: 상권 순위 ─────────────────────────────────────────── */

function DistrictRankCard({ business, ind, districtId, districts, onDistrictChange }: CardProps) {
  const headId = useId();
  const [data, setData] = useState<{ key: string; fit: IndustryFit } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setErr(null);
    getIndustryFit(ind.key)
      .then((fit) => live && setData({ key: ind.key, fit }))
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [ind.key]);
  const fit = data?.key === ind.key ? data.fit : null;

  if (err) return <div className="fitcard"><Eyebrow goal={business.goal} /><p className="fit-err">업종 기준 상권 비교를 불러오지 못했습니다.</p></div>;
  if (!fit) return <div className="fitcard"><Eyebrow goal={business.goal} /><p className="fit-loading">{ind.label} 기준으로 상권을 견주는 중…</p></div>;

  const byId = new Map(fit.districts.map((d) => [d.district_id, d]));
  const here = byId.get(districtId) ?? null;
  const homeId = business.goal === "move" ? business.homeDistrictId : null;
  const home = homeId ? byId.get(homeId) ?? null : null;
  const hereName = here?.name ?? districts.find((d) => d.id === districtId)?.name ?? districtId;
  const vac = (id: string) => districts.find((d) => d.id === id);

  // 표: (옮기기) 지금 상권 고정 → 순위 상위 5 → 지금 보는 상권이 그 밖이면 한 줄 더
  const rows: Array<{ row: IndustryFitRow; tag?: string }> = [];
  if (fit.model_covered) {
    if (home) rows.push({ row: home, tag: "지금" });
    for (const r of fit.districts.filter((d) => d.fit_rank != null && d.fit_rank <= TOP_N)) {
      if (r.district_id !== homeId) rows.push({ row: r });
    }
    if (here && !rows.some((x) => x.row.district_id === here.district_id)) rows.push({ row: here, tag: "보는 중" });
  }

  const diff = home && here && home.district_id !== here.district_id && home.fit != null && here.fit != null
    ? (here.fit - home.fit) * 100 : null;

  return (
    <section className="fitcard" aria-labelledby={headId}>
      <Eyebrow goal={business.goal} />
      <h2 id={headId}>
        {ind.label} — {hereName}
        {fit.model_covered && (here?.fit_rank != null
          ? <> 서울 {fit.ranked_n}곳 중 <b>{here.fit_rank}위</b></>
          : <> <span className="fit-muted">순위 없음(이 상권은 모델 산출물이 없습니다)</span></>)}
      </h2>
      {!fit.model_covered && (
        <p className="fit-uncovered">{topic(ind.label)} 모델 추천 대상(7종) 밖이라 적합도 순위를 내지 않습니다. 같은 업종 비중·임대료·공실률은 그대로 보여줍니다.</p>
      )}
      {diff != null && (
        <p className="fit-diff">지금 상권({home!.name}) 대비 적합도 <b>{diff > 0 ? "+" : ""}{diff.toFixed(1)}%p</b></p>
      )}
      {home && home.district_id === districtId && (
        <p className="fit-diff">지금 가게 상권을 보고 있습니다 — 아래 표에서 다른 상권과 견주세요.</p>
      )}
      {here && <Facts row={here} seoulFit={fit.seoul_fit} covered={fit.model_covered} district={vac(districtId)} />}
      <p className="fit-note">{FIT_NOTE}</p>

      {rows.length > 0 && (
        <div className="fit-table-wrap">
          <table className="fit-table">
            <caption>{ind.label} 기준 상권 순위 · 상위 {TOP_N}</caption>
            <thead><tr><th scope="col">순위</th><th scope="col">상권</th><th scope="col">적합도</th><th scope="col">같은 업종</th><th scope="col">1층 평당</th><th scope="col">공실률</th><th scope="col"><span className="sr-only">이동</span></th></tr></thead>
            <tbody>
              {rows.map(({ row, tag }) => {
                const current = row.district_id === districtId;
                const d = vac(row.district_id);
                return (
                  <tr key={`${tag ?? "r"}-${row.district_id}`} className={current ? "is-current" : undefined}>
                    <td className="num">{row.fit_rank ?? "—"}</td>
                    <th scope="row">{row.name}{tag && <em className="fit-tag">{tag}</em>}<small>{row.gu}</small></th>
                    <td className="num">{pct1(row.fit) ?? "미제공"}</td>
                    <td className="num">{shareText(row)}</td>
                    <td className="num">{row.rent_1f_per_pyeong != null ? `${row.rent_1f_per_pyeong}만` : "미제공"}</td>
                    <td className="num">{vacancyText(d)}</td>
                    <td>
                      {current
                        ? <span className="fit-here">보는 중</span>
                        : <button type="button" onClick={() => onDistrictChange(row.district_id)}
                            aria-label={`${row.name} 상권 보기`}>이 상권 보기</button>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="fit-src">{fit.source}</p>
    </section>
  );
}

function Facts({ row, seoulFit, covered, district }: {
  row: IndustryFitRow; seoulFit: number | null; covered: boolean; district?: DistrictSummary;
}) {
  return (
    <dl className="fit-facts">
      {covered && <div><dt>입지 적합도</dt><dd>{pct1(row.fit) ?? "미제공"}{seoulFit != null && <small> 서울 평균 {pct1(seoulFit)}</small>}</dd></div>}
      <div><dt>같은 업종</dt><dd>{shareText(row)}</dd></div>
      <div><dt>1층 평당 월세</dt><dd>{row.rent_1f_per_pyeong != null ? `${row.rent_1f_per_pyeong}만원` : "미제공"}{row.rent_shared && <small> 인접 상권 표본</small>}</dd></div>
      <div><dt>공실률</dt><dd>{vacancyText(district)}</dd></div>
    </dl>
  );
}

function shareText(row: { same_n: number | null; same_share: number | null; sample_n?: number | null }): string {
  if (row.same_n == null || row.same_share == null) return "미제공";
  return row.sample_n != null ? `${pct1(row.same_share)} (${row.same_n}/${row.sample_n}곳)` : `${pct1(row.same_share)} (${row.same_n}곳)`;
}

function vacancyText(d?: DistrictSummary): string {
  if (!d) return "—";
  if (d.vacancy_withheld) return "대표값 미제공";
  return d.vacancy_rate != null && Number.isFinite(d.vacancy_rate) ? `${d.vacancy_rate.toFixed(1)}%` : "실측 없음";
}

/* ── 업종 바꾸기: 이 상권 업종 순위 ─────────────────────────────────────────── */

function PivotCard({ business, ind, districtId, districts, onDistrictChange, onTryIndustry }: CardProps) {
  const headId = useId();
  const [data, setData] = useState<{ id: string; mix: DistrictIndustries } | null>(null);
  const [err, setErr] = useState<{ id: string; msg: string } | null>(null);
  useEffect(() => {
    let live = true;
    getDistrictIndustries(districtId)
      .then((mix) => live && setData({ id: districtId, mix }))
      .catch((e) => live && setErr({ id: districtId, msg: String(e) }));
    return () => { live = false; };
  }, [districtId]);
  const mix = data?.id === districtId ? data.mix : null;
  const hereName = districts.find((d) => d.id === districtId)?.name ?? districtId;
  const homeId = business.homeDistrictId;
  const homeName = districts.find((d) => d.id === homeId)?.name ?? "지금 가게 상권";

  if (err?.id === districtId) {
    return (
      <div className="fitcard"><Eyebrow goal={business.goal} />
        <p className="fit-err">{/404/.test(err.msg) ? "이 상권은 업종 순위 산출물이 없습니다." : "업종 순위를 불러오지 못했습니다."}</p>
      </div>
    );
  }
  if (!mix) return <div className="fitcard"><Eyebrow goal={business.goal} /><p className="fit-loading">{hereName}의 업종을 견주는 중…</p></div>;

  const mine = mix.rows.find((r) => r.key === ind.key);
  return (
    <section className="fitcard" aria-labelledby={headId}>
      <Eyebrow goal={business.goal} />
      <h2 id={headId}>
        {hereName}에서 바꿔볼 업종
        <span className="fit-sub"> — 지금 업종 {mine?.fit_rank != null
          ? <>{topic(ind.label)} <b>{mine.fit_rank}위</b></>
          : <>{topic(ind.label)} 모델 7종 밖이라 순위가 없습니다</>}</span>
      </h2>
      {homeId && homeId !== districtId && (
        <p className="fit-diff">
          지금 가게 상권({homeName})이 아닌 상권을 보고 있습니다.{" "}
          <button type="button" className="fit-link" onClick={() => onDistrictChange(homeId)}>지금 상권으로</button>
        </p>
      )}
      <p className="fit-note">{FIT_NOTE}</p>
      <div className="fit-table-wrap">
        <table className="fit-table">
          <caption>{hereName} 업종 순위</caption>
          <thead><tr><th scope="col">순위</th><th scope="col">업종</th><th scope="col">적합도</th><th scope="col">같은 업종</th><th scope="col"><span className="sr-only">계산</span></th></tr></thead>
          <tbody>
            {mix.rows.map((r) => {
              const isMine = r.key === ind.key;
              return (
                <tr key={r.key} className={isMine ? "is-current" : undefined}>
                  <td className="num">{r.fit_rank ?? "—"}</td>
                  <th scope="row">{r.label}{isMine && <em className="fit-tag">지금</em>}</th>
                  <td className="num">{r.model_label ? (pct1(r.fit) ?? "미제공") : <span className="fit-muted">모델 밖</span>}</td>
                  <td className="num">{shareText({ ...r, sample_n: mix.sample_n })}</td>
                  <td>
                    {!isMine && onTryIndustry && (
                      <button type="button" onClick={() => onTryIndustry(r.input)} aria-label={`${toward(r.label)} 입점 계산`}>
                        이 업종으로 입점 계산 →
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="fit-src">{mix.source}</p>
    </section>
  );
}
