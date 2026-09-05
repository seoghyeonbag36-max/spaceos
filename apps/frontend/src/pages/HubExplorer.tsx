/**
 * HubExplorer — 「거점」 탭. 지도 전체화면 위에서 거점 하나를 골라 **실측 범위(경계)와
 * 요약**을 같은 화면 안에서 본다.
 *
 * 설계서: `docs/screen-hub-explorer.md` (양식 `docs/prompt-ux-screen-spec.md` §3)
 *
 * ## 두 불변 조건
 * C1. 중앙은 네이버 지도 전체화면 고정 — 지도는 `MapHost` 가 갖고 여기서는 오버레이만
 *     그린다. 패널은 지도 **위에** 뜨고 지도를 밀어내지 않는다.
 * C2. 거점을 고르면 화면을 옮기지 않고 같은 지도 안에서 셋이 같이 일어난다 —
 *     카메라 이동 · 경계 표시 · 요약 패널.
 *
 * ## 경계는 상권 경계가 아니다
 * 시스템에 거점 경계 폴리곤은 없다. 여기 그리는 선은 `/heatmap/vacancy` 실측 셀의
 * 외곽선(`lib/hubBoundary`)이고, 뜻은 **"이 안이 실제로 재어진 곳"** 이다. 범례 배지가
 * 그 사실을 말한다 — 선 안쪽이 상권이고 바깥이 아니라는 뜻으로 읽히면 안 된다.
 * 커버리지 5.2% 짜리 거점(banpo)의 경계를 상권 경계로 읽는 것이 이 화면이 막아야 할
 * 오해다.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMapHost } from "@/components/MapHost";
import { CaveatNote, MARK, MeasuredValue, caveatKind } from "@/components/DistrictPicker";
import { getVacancyHeatmap, listDistricts, type DistrictSummary } from "@/lib/api";
import { boundaryBadge, computeHubBoundary, EMPTY_BOUNDARY, type HubBoundary } from "@/lib/hubBoundary";
import { colors } from "@/design/tokens/colors";
import "@/styles/tokens.css";
import "./HubExplorer.css";

/** 커버리지가 이 아래면 대표값을 믿을 이유가 준다 — 숫자에 주의색을 준다. */
const COVERAGE_WARN_PCT = 30;

/* ── URL 해시 — `#hub=<slug>` 로 선택을 남긴다(새로고침·공유 복원) ──────────────
   App 의 관리자 패널은 `#admin` 을 정확히 비교하므로 서로 부딪히지 않는다. */
const HASH_RE = /^#hub=([a-z0-9][a-z0-9-]{0,63})$/;

function hubFromHash(): string | null {
  const m = HASH_RE.exec(window.location.hash);
  return m ? m[1] : null;
}

/**
 * 이 페이지 세션에서 거점 화면을 이미 한 번 열었는가 (모듈 스코프 = 새로고침 때 초기화).
 *
 * 탭을 다녀왔을 때는 카메라를 건드리지 않아야 하지만(사용자가 맞춰 둔 중심·줌이 남아야
 * 한다), **새로 연 페이지**는 사정이 다르다. `#hub=yeouido` 링크를 받아 들어온 사람에게
 * 지도는 기본 중심(가로수길)에 서 있고, 그때도 안 움직이면 여의도 경계를 그려 놓고
 * 카메라는 강남을 보는 화면이 된다. 첫 마운트는 맞추고, 그 뒤 재마운트만 건너뛴다.
 */
let openedOnce = false;

export default function HubExplorer() {
  const { map, ready } = useMapHost();

  const [hubs, setHubs] = useState<DistrictSummary[]>([]);
  const [listErr, setListErr] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(() => hubFromHash());
  const [boundary, setBoundary] = useState<HubBoundary>(EMPTY_BOUNDARY);
  const [calc, setCalc] = useState(false);
  const [summaryErr, setSummaryErr] = useState(false);
  const [q, setQ] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  /** 재시도용 — 같은 거점을 다시 부르려면 의존성이 실제로 바뀌어야 한다. */
  const [retry, setRetry] = useState(0);
  /* 좁은 화면에서는 목록과 요약을 **동시에** 띄우지 않는다. 둘을 겹쳐 놓으면
     38vh + 44vh = 82vh 라 지도가 사실상 사라진다 — 불변 조건 C1 위반이다.
     거점을 고르면 목록이 접히고, "거점 목록" 버튼으로 되돌아온다. */
  const [narrow, setNarrow] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches,
  );
  const [listOpen, setListOpen] = useState(true);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const onChange = (e: MediaQueryListEvent) => setNarrow(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const overlaysRef = useRef<any[]>([]);
  // 탭을 다녀와 다시 열린 경우에만 첫 경계의 카메라 맞춤을 건너뛴다 — 중심·줌이
  // 그대로여야 하기 때문이다(설계서 §3 "초기(탭 진입)"). 새로 연 페이지는 맞춘다.
  const skipFitRef = useRef(openedOnce);
  useEffect(() => { openedOnce = true; }, []);

  const selected = useMemo(
    () => hubs.find((h) => h.id === selectedId) ?? null,
    [hubs, selectedId],
  );

  /* ── 거점 목록 — 한 번만. 거점 전환 시 재요청하지 않는다 ────────────────── */
  useEffect(() => {
    let alive = true;
    listDistricts()
      .then((all) => { if (alive) { setHubs(all); setListErr(false); } })
      .catch(() => { if (alive) setListErr(true); });
    return () => { alive = false; };
  }, []);

  /* ── 해시 ⇄ 선택 동기화 ──────────────────────────────────────────────── */
  useEffect(() => {
    const onHash = () => {
      const next = hubFromHash();
      // 밖에서 바뀐 해시(뒤로가기 등)는 사용자의 선택이므로 카메라를 맞춘다.
      if (next !== selectedId) { skipFitRef.current = false; setSelectedId(next); }
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [selectedId]);

  const pick = useCallback((id: string) => {
    skipFitRef.current = false;
    setSelectedId(id);
    setCollapsed(false);
    // 좁은 화면: 고른 순간 목록을 접어 지도와 요약에 자리를 내준다.
    if (window.matchMedia("(max-width: 768px)").matches) setListOpen(false);
    if (hubFromHash() !== id) window.location.hash = `hub=${id}`;
  }, []);

  /* ── 경계 — 실측 셀 외곽선 ────────────────────────────────────────────── */
  useEffect(() => {
    if (!selectedId) { setBoundary(EMPTY_BOUNDARY); setSummaryErr(false); return; }
    let alive = true;
    setCalc(true);
    setSummaryErr(false);
    getVacancyHeatmap(selectedId)
      .then((hm) => { if (alive) { setBoundary(computeHubBoundary(hm.cells)); setCalc(false); } })
      .catch(() => {
        // 경계를 못 그리는 것은 정상 상태다(예외 아님) — 배지가 "실측 범위 없음"을 낸다.
        if (alive) { setBoundary(EMPTY_BOUNDARY); setCalc(false); setSummaryErr(true); }
      });
    return () => { alive = false; };
  }, [selectedId, retry]);

  /* ── 경계 렌더 + 카메라 ───────────────────────────────────────────────── */
  useEffect(() => {
    if (!ready || !map) return;
    const naver = (window as any).naver;

    // 이전 거점의 선을 남기지 않는다 — 남으면 두 거점의 범위가 겹쳐 보인다.
    overlaysRef.current.forEach((o) => o.setMap?.(null));
    overlaysRef.current = [];

    for (const piece of boundary.pieces) {
      const toPath = (ring: Array<[number, number]>) =>
        ring.map(([lat, lng]) => new naver.maps.LatLng(lat, lng));
      // 1칸짜리 섬은 경계가 아니라 점으로 읽히게 얇게. 채우면 덩어리로 오독된다.
      const solo = piece.cells <= 1;
      const poly = new naver.maps.Polygon({
        map,
        paths: [toPath(piece.outer), ...piece.holes.map(toPath)],
        strokeColor: colors.brand.primary,
        strokeWeight: solo ? 1 : 2,
        strokeOpacity: solo ? 0.7 : 0.95,
        fillColor: colors.brand.primary,
        fillOpacity: solo ? 0 : 0.06,
        // 경계는 클릭을 먹지 않는다 — 밑의 건물 폴리곤이 클릭을 받아야 한다.
        clickable: false,
      });
      overlaysRef.current.push(poly);
    }

    // 카메라는 거점 center 가 아니라 **경계 bbox** 에 맞춘다. center 는 수집 원점이라
    // 실측 범위와 어긋날 수 있다(banpo: 셀 18개가 7조각으로 흩어져 있다).
    //
    // ⚠ 플래그는 **실제 경계가 왔을 때만** 내린다. 마운트 직후 이 이펙트는 boundary 가
    //   비어 있는 채로 한 번 돌기 때문에, 거기서 내려 버리면 뒤이어 도착한 경계가
    //   카메라를 옮겨 버린다 — 해시로 복원한 탭 왕복에서 중심·줌이 날아간다.
    if (boundary.bbox) {
      if (!skipFitRef.current) {
        const { south, west, north, east } = boundary.bbox;
        map.fitBounds(
          new naver.maps.LatLngBounds(
            new naver.maps.LatLng(south, west),
            new naver.maps.LatLng(north, east),
          ),
          fitPadding(),
        );
      }
      skipFitRef.current = false;
    }

    return () => {
      overlaysRef.current.forEach((o) => o.setMap?.(null));
      overlaysRef.current = [];
    };
  }, [ready, map, boundary]);

  /* ── Esc — 요약만 접는다(거점 선택은 유지) ────────────────────────────── */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setCollapsed(true); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const filtered = useMemo(() => {
    const needle = q.trim();
    if (!needle) return hubs;
    return hubs.filter((h) => h.name.includes(needle) || h.gu.includes(needle));
  }, [hubs, q]);

  const byCity = useMemo(() => {
    const m = new Map<string, DistrictSummary[]>();
    for (const h of filtered) {
      const k = h.city_name ?? "서울";
      const b = m.get(k);
      if (b) b.push(h); else m.set(k, [h]);
    }
    return [...m.entries()];
  }, [filtered]);

  const badge = calc ? "범위 계산 중" : boundaryBadge(boundary);

  return (
    <>
      {/* ── A 상단: 거점 검색 ── */}
      <div className="overlay hx-top">
        <input
          className="hx-search"
          placeholder={`거점 검색 (${hubs.length ? `${hubs.length}곳` : "불러오는 중"})`}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="거점 이름·자치구 검색"
        />
      </div>

      {/* ── B 좌측: 거점 목록 ── */}
      <div className={"overlay hx-list" + (narrow && !listOpen ? " is-collapsed" : "")} aria-label="거점 목록">
        <div className="hx-list-head">
          {/* PPPP: Product ▶ Page — 이 platform 에 page 를 놓을 만한 자리인지를 거점
              단위로 먼저 거른다. 가격대는 Posting, 홍보는 Program 의 몫이다. */}
          <div className="hx-track">PRODUCT ▶ PAGE</div>
          <div className="hx-title">거점 {hubs.length ? `${hubs.length}곳` : ""}</div>
          <div className="hx-sub">
            {listErr
              ? "목록을 못 불러왔다"
              : q ? `검색 ${filtered.length}곳` : "고르면 실측 범위와 요약이 뜬다"}
          </div>
        </div>

        <div className="hx-list-body">
          {byCity.map(([city, rows]) => (
            <div key={city}>
              <div className="hx-city">{city} ({rows.length})</div>
              {rows.map((h) => {
                const kind = caveatKind(h);
                return (
                  <button
                    key={h.id}
                    className={"hx-item" + (h.id === selectedId ? " active" : "")}
                    aria-current={h.id === selectedId ? "true" : undefined}
                    onClick={() => pick(h.id)}
                  >
                    <span className="hx-item-main">
                      <span className="hx-item-name">
                        {kind && <span className="hx-mark" title="다른 거점과 직접 비교하지 말 것">{MARK[kind]}</span>}
                        {h.name}
                      </span>
                      <span className="hx-item-meta">{h.gu}</span>
                    </span>
                    <span className="hx-item-vac">
                      {h.vacancy_withheld
                        ? <span className="value-absent">미제공</span>
                        : <MeasuredValue value={h.vacancy_rate} unit="%" absent="실측 없음" />}
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
          {!listErr && hubs.length > 0 && filtered.length === 0 && (
            <div className="hx-empty">"{q}" 에 맞는 거점이 없다</div>
          )}
        </div>
      </div>

      {/* ── C 우측: 거점 요약 ── */}
      {!collapsed && (
        <div className={"overlay hx-summary" + (narrow && listOpen ? " with-list" : "")} aria-label="거점 요약">
          {!selected ? (
            <div className="hx-placeholder">
              거점을 고르면 실측 범위와 요약이 여기 뜬다
            </div>
          ) : (
            <>
              <div className="hx-sum-head">
                <div className="hx-sum-name">{selected.name}</div>
                <div className="hx-sum-where">{selected.city_name} · {selected.gu}</div>
                <button className="hx-close" onClick={() => setCollapsed(true)} aria-label="요약 접기">✕</button>
              </div>

              <CaveatNote district={selected} />

              {summaryErr && (
                <div className="hx-err">
                  거점 요약을 못 불러왔다
                  <button onClick={() => setRetry((n) => n + 1)}>다시 시도</button>
                </div>
              )}

              {/* 대표 공실률 — null 이 두 뜻이라 문구를 가른다.
                  withheld=true → 쟀지만 대표하지 못해 내렸다 / false+null → 재지 않았다 */}
              <div className="hx-figure">
                <div className="hx-figure-label">
                  거점 대표 공실률
                  <span className="hx-badge hx-badge-src">
                    {selected.vacancy_source === "gold" ? "실측(Gold)" : "합성"}
                  </span>
                </div>
                <div className="hx-figure-value">
                  {selected.vacancy_withheld
                    ? <span className="hx-withheld">대표값 미제공</span>
                    : <MeasuredValue value={selected.vacancy_rate} unit="%" absent="실측 없음" />}
                </div>
              </div>

              <dl className="hx-rows">
                <Row label="공실 호실 / 점포">
                  {selected.vacant_units.toLocaleString()}호 / {selected.store_count.toLocaleString()}곳
                </Row>

                {selected.building_count !== null && (
                  <Row label="집계 건물 / 정밀도">
                    {selected.building_count.toLocaleString()}동 ·{" "}
                    <MeasuredValue value={selected.precision_pct} unit="%" />
                  </Row>
                )}

                {selected.inventory_coverage_pct != null && (
                  <Row label="분모 커버리지" hint="공실률 분모가 이 거점 상업 재고에서 차지하는 비율(호실 기준)">
                    <span className={selected.inventory_coverage_pct < COVERAGE_WARN_PCT ? "hx-warn" : ""}>
                      {selected.inventory_coverage_pct.toFixed(1)}%
                    </span>
                  </Row>
                )}

                {selected.anchor_pct != null && selected.anchor_gap_pp != null && (
                  <Row label={<>앵커 대조 <span className="hx-badge">R-ONE</span></>}
                       hint="모집단·단위가 달라(우리는 호실·전수, R-ONE 은 면적·표본) 격차 0 이 정상은 아니다. 거점 간 비교·추세 감시용.">
                    {selected.anchor_pct.toFixed(1)}%{" "}
                    <span className="hx-gap">
                      {selected.anchor_gap_pp >= 0 ? "+" : ""}{selected.anchor_gap_pp.toFixed(1)}%p
                    </span>
                  </Row>
                )}

                {selected.predicted_rate != null && (
                  <Row label={<>다음 분기 예측 <span className="hx-badge">LSTM</span></>}>
                    {selected.predicted_rate.toFixed(1)}%
                    {selected.predicted_direction && (
                      <span className="hx-dir">{selected.predicted_direction === "up" ? " ↑" : " ↓"}</span>
                    )}
                  </Row>
                )}

                {/* 감성은 66거점 전부 null 이다(미측정). 0 으로 그리지 않고, 공실률을
                    이 자리에 옮겨 그리지도 않는다 — docs/feature-platform.md §0-K */}
                <Row label="감성 지수" hint="좌표를 가진 점포 리뷰 채널이 없어 아직 재지 못한다">
                  <MeasuredValue value={selected.sentiment} absent="실측 없음" />
                </Row>

                <Row label="실측 범위" hint="공실률 분모에 들어간 100m 격자 셀의 외곽선이다. 상권 경계가 아니다.">
                  {boundary.cellCount ? `${boundary.cellCount}셀 · ${boundary.components}조각` : "없음"}
                </Row>
              </dl>

              <p className="hx-foot">
                이 경계는 <b>우리가 잰 범위</b>다. 선 바깥이 상권이 아니라는 뜻이 아니라,
                선 안쪽이 공실률 분모에 들어갔다는 뜻이다.
              </p>
            </>
          )}
        </div>
      )}

      {collapsed && selected && (
        <button className="overlay hx-reopen" onClick={() => setCollapsed(false)}>
          {selected.name} 요약 열기
        </button>
      )}

      {narrow && !listOpen && (
        <button className="overlay hx-list-toggle" onClick={() => setListOpen(true)}>
          거점 목록
        </button>
      )}

      {/* ── D 범례: 경계 근거 ── */}
      <div className="overlay hx-legend">
        <span className="hx-legend-line" aria-hidden="true" />
        <span className="hx-legend-text">{badge}</span>
      </div>

      {/* 스크린리더 — 경계는 시각 요소라 배지 텍스트로만 전한다 */}
      <div className="hx-live" role="status" aria-live="polite">
        {selected
          ? `${selected.name} 선택됨. ${
              selected.vacancy_withheld
                ? "대표 공실률 미제공."
                : selected.vacancy_rate != null
                  ? `공실률 ${selected.vacancy_rate.toFixed(1)}퍼센트.`
                  : "공실률 실측 없음."
            } ${badge}.`
          : ""}
      </div>
    </>
  );
}

function Row({ label, hint, children }: { label: React.ReactNode; hint?: string; children: React.ReactNode }) {
  return (
    <div className="hx-row">
      <dt title={hint}>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/**
 * fitBounds 여백 — 경계가 오버레이 **밑에** 깔리면 안 된다.
 * 데스크톱은 좌 목록(320)·우 요약(340) 폭을, 모바일은 바텀시트 높이를 비켜준다.
 */
function fitPadding(): { top: number; right: number; bottom: number; left: number } {
  const narrow = window.innerWidth < 768;
  if (narrow) {
    return { top: 64, right: 16, bottom: Math.round(window.innerHeight * 0.38) + 16, left: 16 };
  }
  return { top: 76, right: 364, bottom: 68, left: 344 };
}
