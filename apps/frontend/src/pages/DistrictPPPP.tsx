import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { loadNaverMaps } from "@/lib/naverMap";
import { getDistrict } from "@/lib/api";
import {
  districtById, buildCells, mixFor, scenarios, roiM, TIER,
  fgHex, fgV, vacColor, arrow, rev, rad,
  type District, type PKey, type TierKey, type Cell,
} from "@/lib/districts/pppp";
import "./LafestaPPPP.css";

/**
 * 거점 범용 PPPP 뷰 (API 연동).
 * 데이터: 백엔드 GET /api/v1/commercial-districts/{id} (로딩/에러/재시도).
 * 백엔드 미연결 시 정적 모듈로 폴백. districtId 변경 시 재요청 + 뷰 remount.
 */
export default function DistrictPPPP({ districtId = "lafesta" }: { districtId?: string }) {
  const [district, setDistrict] = useState<District | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true); setError(null); setDistrict(null);
    getDistrict(districtId)
      .then((d) => { setDistrict(d as District); setLoading(false); })
      .catch((e: Error) => { setError(e.message || "불러오기 실패"); setLoading(false); });
  };
  useEffect(load, [districtId]);

  if (loading) return <Centered>📡 {districtId} 거점 데이터를 불러오는 중…</Centered>;
  if (error || !district) return (
    <Centered>
      <div style={{ color: "#b23b39", fontWeight: 700, marginBottom: 8 }}>거점 데이터를 불러오지 못했습니다</div>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 14 }}>백엔드(/api/v1) 연결을 확인하세요. {error}</div>
      <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
        <SmallBtn onClick={load}>다시 시도</SmallBtn>
        {districtById[districtId] && <SmallBtn onClick={() => { setDistrict(districtById[districtId]); setError(null); }}>정적 데이터로 보기</SmallBtn>}
      </div>
    </Centered>
  );
  // key=district.id → 거점 변경 시 내부 상태/오버레이 깔끔히 remount
  return <DistrictView key={district.id} d={district} />;
}

type OG = Record<PKey, any[]>;
const TAB: Record<PKey, { pk: string; pn: string; pd: string; title: string; hint: string }> = {
  P1: { pk: "PLATFORM", pn: "상권 감성 지도", pd: "Place→Platform", title: "상권 감성 히트맵", hint: "원=리뷰량 · 색=감성점수 · 클릭 상세" },
  P2: { pk: "PAGE", pn: "공실 히트맵", pd: "Product→Page · 밀도", title: "공실 히트맵 · 전 공실 밀도", hint: "색 진할수록 공실 밀집 · 지도 클릭 → 구역 상세" },
  P3: { pk: "POSTING", pn: "입점 솔루션", pd: "Promo→Posting · 3-Tier", title: "공실 유닛 추천 Tier", hint: "마커 색=추천 Tier · 클릭 비용-효용" },
  P4: { pk: "PROGRAM", pn: "마케팅 솔루션", pd: "Promo→Program", title: "온·오프라인 마케팅", hint: "핀=행사 거점 · 파란원=온라인 발행" },
};

function DistrictView({ d }: { d: District }) {
  const cellsInfo = useMemo(() => buildCells(d.grid), [d]);
  const cellMap = useMemo(() => {
    const m: Record<string, Cell> = {};
    cellsInfo.cells.forEach((c) => { m[`${c.i}_${c.j}`] = c; });
    return m;
  }, [cellsInfo]);
  const worstZone = [...d.zones].sort((a, b) => a.s - b.s)[0].id;
  const topCell = [...cellsInfo.cells].sort((a, b) => b.v - a.v)[0];

  const mapDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const groupsRef = useRef<OG>({ P1: [], P2: [], P3: [], P4: [] });
  const [ready, setReady] = useState(false);
  const [authFailed, setAuthFailed] = useState(false);
  const [activeP, setActiveP] = useState<PKey>("P1");
  const activePRef = useRef(activeP);
  activePRef.current = activeP;
  const [selZone, setSelZone] = useState(worstZone);
  const [selCell, setSelCell] = useState(topCell ? `${topCell.i}_${topCell.j}` : "");
  const [selUnit, setSelUnit] = useState(d.units[0].id);
  const [selEvent, setSelEvent] = useState(d.events[0].id);
  const [subTab, setSubTab] = useState<"on" | "off">("off");
  const [live, setLive] = useState(42);

  const moveTo = (lat: number, lng: number, z = 17) => {
    const m = mapRef.current, naver = (window as any).naver;
    if (m && naver) { m.setCenter(new naver.maps.LatLng(lat, lng)); m.setZoom(z); }
  };

  useEffect(() => { const t = setInterval(() => setLive(36 + Math.floor(Math.random() * 14)), 2000); return () => clearInterval(t); }, []);

  // 지도 init + 오버레이 빌드 (1회)
  useEffect(() => {
    (window as any).navermap_authFailure = () => setAuthFailed(true);
    let cancelled = false;
    loadNaverMaps()
      .then(() => {
        if (cancelled || !mapDivRef.current) return;
        const naver = (window as any).naver;
        const LL = (a: number, b: number) => new naver.maps.LatLng(a, b);
        const map = new naver.maps.Map(mapDivRef.current, {
          center: LL(d.center[0], d.center[1]), zoom: d.zoom, minZoom: 13, maxZoom: 18,
          scaleControl: false, mapDataControl: false, zoomControl: true,
          zoomControlOptions: { position: naver.maps.Position.TOP_RIGHT },
        });
        mapRef.current = map;
        const G: OG = { P1: [], P2: [], P3: [], P4: [] };
        const add = (k: PKey, ov: any) => { G[k].push(ov); return ov; };
        const label = (k: PKey, lat: number, lng: number, html: string, ax: number, ay: number) =>
          add(k, new naver.maps.Marker({ map: null, position: LL(lat, lng), icon: { content: html, anchor: new naver.maps.Point(ax, ay) } }));

        d.poi.forEach((p) => {
          if (p[3] === "sta") new naver.maps.Marker({ map, position: LL(p[0], p[1]), icon: { content: '<div style="width:12px;height:12px;border-radius:50%;background:#c0504a;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)"></div>', anchor: new naver.maps.Point(6, 6) } });
          new naver.maps.Marker({ map, position: LL(p[0], p[1]), icon: { content: `<div class="poi ${p[3] || ""}">${p[2]}</div>`, anchor: new naver.maps.Point(-8, 8) } });
        });
        d.zones.forEach((z) => {
          const c = fgHex(z.s);
          add("P1", new naver.maps.Circle({ map: null, center: LL(z.lat, z.lng), radius: rad(z.r) * 6, strokeColor: c, strokeWeight: 1.4, strokeOpacity: 0.55, fillColor: c, fillOpacity: 0.18 }));
          const m = add("P1", new naver.maps.Marker({ map: null, position: LL(z.lat, z.lng), icon: { content: `<div class="zmk" style="background:${c}"></div>`, anchor: new naver.maps.Point(10, 10) } }));
          naver.maps.Event.addListener(m, "click", () => setSelZone(z.id));
          label("P1", z.lat, z.lng, `<div class="lbl">${z.n} · ${z.s.toFixed(0)}</div>`, -12, 8);
        });
        // P2 — 모든 공실 점포를 반투명 원 밀도 히트맵으로 표현 (그리드 미사용)
        cellsInfo.cells.forEach((cl) => {
          const col = vacColor(cl.v);
          for (let k = 0; k < cl.vacN; k++) {
            const jl = cl.cLat + (Math.random() - 0.5) * cl.dlat * 0.9;
            const jg = cl.cLng + (Math.random() - 0.5) * cl.dlng * 0.9;
            add("P2", new naver.maps.Circle({ map: null, center: LL(jl, jg), radius: 34, strokeWeight: 0, fillColor: col, fillOpacity: 0.13, clickable: false }));
          }
        });
        // 히트맵 위 클릭 → 가장 가까운 공실 구역 상세
        naver.maps.Event.addListener(map, "click", (e: any) => {
          if (activePRef.current !== "P2") return;
          const lat = e.coord.lat(), lng = e.coord.lng();
          let best: Cell | null = null, bd = Infinity;
          cellsInfo.cells.forEach((c) => { const dy = (lat - c.cLat) * 111000, dx = (lng - c.cLng) * 88300, dd = Math.sqrt(dx * dx + dy * dy); if (dd < bd) { bd = dd; best = c; } });
          if (best && bd < 180) setSelCell(`${(best as Cell).i}_${(best as Cell).j}`);
        });
        d.units.forEach((u) => {
          const t = TIER[u.rec];
          const m = add("P3", new naver.maps.Marker({ map: null, position: LL(u.lat, u.lng), icon: { content: `<div class="umk" style="background:${t.c}">${t.nm.charAt(0)}</div>`, anchor: new naver.maps.Point(11, 11) } }));
          naver.maps.Event.addListener(m, "click", () => setSelUnit(u.id));
          label("P3", u.lat, u.lng, `<div class="poi" style="color:${t.c}">${u.n}</div>`, -14, 8);
        });
        const fz = d.zones[0];
        add("P4", new naver.maps.Circle({ map: null, center: LL(fz.lat, fz.lng), radius: 90, strokeColor: "#2563b0", strokeWeight: 1.4, strokeOpacity: 0.5, fillColor: "#2563b0", fillOpacity: 0.12 }));
        d.events.forEach((e) => {
          const m = add("P4", new naver.maps.Marker({ map: null, position: LL(e.lat, e.lng), icon: { content: `<div class="emk" style="background:#b06a1e">${e.ic}</div>`, anchor: new naver.maps.Point(13, 13) } }));
          naver.maps.Event.addListener(m, "click", () => setSelEvent(e.id));
          label("P4", e.lat, e.lng, `<div class="poi" style="color:#b06a1e">${e.n}</div>`, -14, 8);
        });
        groupsRef.current = G;
        (["P1", "P2", "P3", "P4"] as PKey[]).forEach((k) => G[k].forEach((o) => o.setMap(k === "P1" ? map : null)));
        setReady(true);
      })
      .catch(() => setAuthFailed(true));
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 탭 토글
  useEffect(() => {
    if (!ready) return;
    const G = groupsRef.current, m = mapRef.current;
    (["P1", "P2", "P3", "P4"] as PKey[]).forEach((k) => G[k].forEach((o) => o.setMap(k === activeP ? m : null)));
  }, [activeP, ready]);

  useEffect(() => { if (ready && activeP === "P1") { const z = d.zones.find((x) => x.id === selZone); if (z) moveTo(z.lat, z.lng); } }, [selZone]); // eslint-disable-line
  useEffect(() => { if (ready && activeP === "P2") { const c = cellMap[selCell]; if (c) moveTo(c.cLat, c.cLng); } }, [selCell]); // eslint-disable-line
  useEffect(() => { if (ready && activeP === "P3") { const u = d.units.find((x) => x.id === selUnit); if (u) moveTo(u.lat, u.lng); } }, [selUnit]); // eslint-disable-line
  useEffect(() => { if (ready && activeP === "P4") { const e = d.events.find((x) => x.id === selEvent); if (e) moveTo(e.lat, e.lng); } }, [selEvent]); // eslint-disable-line

  const sumR = d.zones.reduce((a, z) => a + z.r, 0);
  const sAvg = d.zones.reduce((a, z) => a + z.s * z.r, 0) / sumR;
  const warn = d.zones.filter((z) => z.s < 40).length;
  const avgV = (cellsInfo.sumVac / cellsInfo.sumStores) * 100;
  const hi = cellsInfo.cells.filter((c) => c.v >= 28).length;
  const avgRoi = d.units.reduce((a, u) => a + roiM(scenarios(u)[u.rec]), 0) / d.units.length;
  const tierCnt = (k: TierKey) => d.units.filter((u) => u.rec === k).length;

  const kpis: Record<PKey, { l: string; v: string | number; suf?: string; c?: string }[]> = {
    P1: [{ l: "😊 감성 지수", v: sAvg.toFixed(1), c: fgV(sAvg) }, { l: "🗂 리뷰", v: sumR.toLocaleString() }, { l: "👍 긍정", v: (sAvg * 0.92).toFixed(1), suf: "%", c: "#4f7a31" }, { l: "⚠ 위험 구역", v: warn, suf: "개", c: warn ? "#b23b39" : "#4f7a31" }, { l: "⚙ 신뢰도", v: "90." + d.zones.length, suf: "%" }],
    P2: [{ l: "🏢 평균 공실률", v: avgV.toFixed(1), suf: "%", c: "#c0392b" }, { l: "🟥 고공실 셀", v: hi, suf: "칸", c: "#c0392b" }, { l: "🏬 상업 셀", v: cellsInfo.cells.length, suf: "칸" }, { l: "🪧 공실 점포", v: cellsInfo.sumVac, suf: "곳", c: "#e8743b" }, { l: "📐 해상도", v: "100", suf: "m" }],
    P3: [{ l: "🟪 고급화", v: tierCnt("premium"), suf: "곳", c: "#7a4f9a" }, { l: "🟩 가성비", v: tierCnt("value"), suf: "곳", c: "#2f7d4f" }, { l: "🟧 공장제", v: tierCnt("factory"), suf: "곳", c: "#b06a1e" }, { l: "🪧 공실 유닛", v: d.units.length, suf: "곳" }, { l: "⏱ 평균 회수", v: avgRoi.toFixed(1), suf: "개월", c: "#9a7b1e" }],
    P4: [{ l: "📤 주간 발행", v: 8 + d.zones.length, suf: "건", c: "#2563b0" }, { l: "🎪 행사 후보", v: d.events.length, suf: "건", c: "#b06a1e" }, { l: "📈 유입 증대", v: "+" + (24 + warn * 3), suf: "%", c: "#2f7d4f" }, { l: "🤝 상생 매칭", v: d.units.length + 1, suf: "건" }, { l: "💬 감성 매칭", v: "9" + d.events.length, suf: "점" }],
  };

  const flowNames = ["Platform", "Page", "Posting", "Program"];
  const flowColors = ["var(--P1)", "var(--P2)", "var(--P3)", "var(--P4)"];
  const pIdx = ["P1", "P2", "P3", "P4"].indexOf(activeP);

  return (
    <div className="pppp">
      <div className="wrap">
        <div className="hd">
          <div>
            <div className="ey">SPACEOS · DIGITAL TWIN · PPPP 심층 · API 연동</div>
            <h1>{d.name}</h1>
            <div className="sub">{d.sub} · 네이버 Dynamic Map · Platform→Page→Posting→Program</div>
          </div>
          <div className="rt"><div className="chip">📍 ncpKeyId {import.meta.env.VITE_NAVER_MAPS_KEY_ID || "—"}</div><div className="chip live">{live}건/s</div></div>
        </div>

        <div className="ptabs">
          {(["P1", "P2", "P3", "P4"] as PKey[]).map((p) => (
            <div key={p} className={"ptab" + (activeP === p ? " on" : "")} data-p={p} onClick={() => setActiveP(p)}>
              <div className="pk">{TAB[p].pk}</div><div className="pn">{TAB[p].pn}</div><div className="pd">{TAB[p].pd}</div>
            </div>
          ))}
        </div>

        <div className="kpis">
          {kpis[activeP].map((k, i) => (
            <div className="kpi" key={i}><div className="l">{k.l}</div>
              <div className="v" style={{ color: k.c || "inherit" }}>{k.v}{k.suf && <small>{k.suf}</small>}</div>
            </div>
          ))}
        </div>

        <div className="cols">
          <div className="left"><div className="card">
            <div className="ch"><h2>{TAB[activeP].title}</h2><div className="hint">{TAB[activeP].hint}</div></div>
            <div className="maphost">
              <div className="map" ref={mapDivRef} />
              {authFailed && (
                <div className="authfail"><div><h3>네이버 지도 인증 실패</h3>
                  <p>NCP 콘솔 → <code>Maps</code> → <code>Application</code> → <b>Web 서비스 URL</b>에 <code>http://localhost:5173</code> 등록 후 그 서버에서 열어 주세요.</p></div></div>
              )}
              <div className="nvbadge">네이버 Dynamic Map · ncpKeyId {import.meta.env.VITE_NAVER_MAPS_KEY_ID || "—"}</div>
            </div>
            <div className="legb">{renderLegend(activeP)}</div>
            <div className="flow">
              {flowNames.map((n, i) => (
                <span key={n} style={{ display: "contents" }}>
                  {i === pIdx ? <b style={{ color: flowColors[i] }}>{`${["①", "②", "③", "④"][i]} ${n}`}</b> : <span>{n}</span>}
                  {i < 3 && <span className="ar">→</span>}
                </span>
              ))}
            </div>
          </div></div>
          <div className="right"><div className="card rp">{renderPanel()}</div></div>
        </div>

        <div className="foot">SpaceOS Digital Twin Platform · {d.name} PPPP 심층 · 데이터: /api/v1/commercial-districts/{d.id}. Humanistic Authority(균형·공생·공감) 설계 기준 적용.</div>
      </div>
    </div>
  );

  function renderLegend(p: PKey) {
    if (p === "P1") return <><span className="lt">감성</span><span><i className="r" style={{ background: "#d9716a" }} />위험</span><span><i className="r" style={{ background: "#e3b95e" }} />주의</span><span><i className="r" style={{ background: "#7faa55" }} />양호</span><span><i className="r" style={{ background: "#3a5a98" }} />우수</span></>;
    if (p === "P2") return <><span className="lt">공실 밀도</span><span><i className="bar" style={{ background: "#cfe3cf" }} />희박</span><span><i className="bar" style={{ background: "#fbe7a6" }} />낮음</span><span><i className="bar" style={{ background: "#f6b96b" }} />보통</span><span><i className="bar" style={{ background: "#e8743b" }} />높음</span><span><i className="bar" style={{ background: "#c0392b" }} />밀집</span></>;
    if (p === "P3") return <><span className="lt">Tier</span><span><i style={{ background: "#7a4f9a" }} />고급화</span><span><i style={{ background: "#2f7d4f" }} />가성비</span><span><i style={{ background: "#b06a1e" }} />공장제</span></>;
    return <><span className="lt">마케팅</span><span><i style={{ background: "#b06a1e" }} />오프라인 행사</span><span><i className="r" style={{ background: "#2563b0" }} />온라인 발행구역</span></>;
  }

  function renderPanel() {
    if (activeP === "P1") {
      const z = d.zones.find((x) => x.id === selZone) ?? d.zones[0];
      const risk = z.s < 40 ? "위험" : z.s < 60 ? "주의" : z.s < 80 ? "양호" : "우수";
      return (<>
        <div className="lab">선택 구역 · {z.grp}</div>
        <div className="top"><div className="nm">{z.n}</div><div><div className="sc" style={{ color: fgV(z.s) }}>{z.s.toFixed(1)}</div><div className="suf" style={{ color: fgV(z.s) }}>{risk} · {arrow(z.d)} · {rev(z.r)}건</div></div></div>
        <div className="sec"><div className="st">{z.d < 0 ? "점수 하락 핵심 요인" : "점수 변동 핵심 요인"}</div>
          {z.f.map((f, i) => <div className="fr" key={i}><span>{f[0]}</span><b className={f[2] === "dn" ? "dn" : "up"}>{f[1]}</b></div>)}
        </div>
        <button className="btn" onClick={() => setActiveP("P2")}>이 구역 공실 그리드 ↗</button>
      </>);
    }
    if (activeP === "P2") {
      const c = cellMap[selCell]; if (!c) return <div className="lab">셀을 선택하세요</div>;
      const lv = c.v < 5 ? ["양호", "#3f7d3f"] : c.v < 10 ? ["주의", "#9a7b1e"] : c.v < 18 ? ["경계", "#d2691e"] : c.v < 28 ? ["위험", "#e8743b"] : ["심각", "#c0392b"];
      const mm = mixFor(c.v);
      return (<>
        <div className="lab">선택 공실 구역 · {c.cLat.toFixed(4)},{c.cLng.toFixed(4)}</div>
        <div className="top"><div><div className="nm">N{c.cLat.toFixed(4)} E{c.cLng.toFixed(4)}</div><div className="lab" style={{ marginTop: 4 }}>{lv[0]} 공실 구간</div></div><div><div className="sc" style={{ color: lv[1] }}>{c.v.toFixed(1)}<small style={{ fontSize: 14 }}>%</small></div><div className="suf">공실 {c.vacN} / 총 {c.stores}</div></div></div>
        <div className="sec"><div className="fr"><span>총 점포</span><b>{c.stores}개</b></div><div className="fr"><span>공실 점포</span><b style={{ color: lv[1] }}>{c.vacN}개</b></div><div className="fr"><span>입주율</span><b>{(100 - c.v).toFixed(1)}%</b></div></div>
        <div className="sec"><div className="st">업종 구성</div>
          <div className="mix">{mm.map((x, i) => <i key={i} style={{ width: `${x[1]}%`, background: x[2] }} />)}</div>
          <div className="mixleg">{mm.map((x, i) => <span key={i}><span className="dt" style={{ background: x[2] }} />{x[0]} {x[1]}%</span>)}</div>
        </div>
        <button className="btn" onClick={() => setActiveP("P3")}>이 셀 입점 솔루션(3-Tier) ↗</button>
      </>);
    }
    if (activeP === "P3") {
      const u = d.units.find((x) => x.id === selUnit) ?? d.units[0]; const sc = scenarios(u); const keys: TierKey[] = ["premium", "value", "factory"];
      return (<>
        <div className="lab">{u.grp} · {u.floor} · 구 {u.was}</div>
        <div className="top"><div className="nm">{u.n}</div></div>
        <div className="recbadge" style={{ background: TIER[u.rec].bg, color: TIER[u.rec].c }}>추천 · {TIER[u.rec].nm} ({TIER[u.rec].sub})</div>
        <div className="lab" style={{ marginTop: 8, lineHeight: 1.5 }}>{u.note} · 타깃: {u.persona}</div>
        <div className="uspec">
          <div className="sp"><div className="k">면적</div><div className="vv">{u.area}㎡</div></div>
          <div className="sp"><div className="k">월 임대료</div><div className="vv">{u.rent}만</div></div>
          <div className="sp"><div className="k">권리금</div><div className="vv">{u.prem ? u.prem + "만" : "없음"}</div></div>
          <div className="sp"><div className="k">유동인구</div><div className="vv">{u.foot}</div></div>
        </div>
        <div className="sec"><div className="st">3-Tier 비용-효용 (월, 만원/백만원)</div>
          {keys.map((k) => {
            const t = TIER[k], s = sc[k], roi = roiM(s), net = s.monthRev - s.monthCost;
            return (
              <div className={"tier" + (k === u.rec ? " sel" : "")} key={k} style={k === u.rec ? { borderColor: t.c } : undefined}>
                <div className="th"><span className="tn"><span className="dot" style={{ background: t.c }} />{t.nm} · {t.sub}{k === u.rec ? " ✓" : ""}</span><span className="roi" style={{ background: t.bg, color: t.c }}>ROI {roi >= 99 ? "—" : roi.toFixed(1) + "개월"}</span></div>
                <div className="met">
                  <div className="m"><div className="mk">초기투자</div><div className="mv">{s.invest}백만</div></div>
                  <div className="m"><div className="mk">월 순익</div><div className="mv" style={{ color: net > 0 ? "#2f7d4f" : "#b23b39" }}>{net > 0 ? "+" : ""}{net}만</div></div>
                  <div className="m"><div className="mk">월 매출</div><div className="mv">{s.monthRev}만</div></div>
                </div>
              </div>
            );
          })}
        </div>
        <button className="btn" onClick={() => setActiveP("P4")}>입점 후 마케팅(Program) ↗</button>
      </>);
    }
    return (<>
      <div className="subtabs">
        <div className={"subtab" + (subTab === "on" ? " on" : "")} onClick={() => setSubTab("on")}>🟦 온라인</div>
        <div className={"subtab" + (subTab === "off" ? " on" : "")} onClick={() => setSubTab("off")}>🟧 오프라인</div>
      </div>
      {subTab === "on" ? (
        <div>{d.insta.map((t, i) => {
          const parts = t.split("\n\n");
          return (
            <div className="gen" key={i}>
              <div className="gh"><span className="pf"><span className="ic" style={{ background: "linear-gradient(135deg,#f58529,#dd2a7b)" }} />인스타 피드 #{i + 1}</span></div>
              <div className="body">{parts.slice(0, -1).join("\n\n")}</div>
              <div className="tags">{parts[parts.length - 1]}</div>
              <div className="meta">예상 도달 <b>{8 + i * 3}K</b> · 감성 매칭 <b>9{1 + i}</b></div>
            </div>
          );
        })}</div>
      ) : (
        <div>{d.events.map((e) => (
          <div className={"ev" + (e.id === selEvent ? " sel" : "")} key={e.id} onClick={() => setSelEvent(e.id)}>
            <div className="eh"><div><div className="en">{e.ic} {e.n}</div><div className="edt">{e.when}</div></div><div className="k2">{e.k2}</div></div>
            <div className="desc">{e.desc}</div>
            <div className="roles">{e.roles.map((r, i) => <span key={i}>{r}</span>)}</div>
            <div className="ha" dangerouslySetInnerHTML={{ __html: e.ha }} />
          </div>
        ))}</div>
      )}
    </>);
  }
}

function Centered({ children }: { children: ReactNode }) {
  return <div className="pppp"><div className="wrap"><div className="card" style={{ textAlign: "center", padding: "48px 20px", marginTop: 40 }}>{children}</div></div></div>;
}
function SmallBtn({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button onClick={onClick} style={{ fontFamily: "inherit", fontSize: 13, fontWeight: 700, cursor: "pointer", padding: "8px 14px", borderRadius: 9, border: "1px solid #3a5a98", background: "#3a5a98", color: "#fff" }}>{children}</button>;
}
