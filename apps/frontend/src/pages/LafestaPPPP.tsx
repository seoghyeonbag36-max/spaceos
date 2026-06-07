import { useEffect, useRef, useState } from "react";
import { loadNaverMaps } from "@/lib/naverMap";
import {
  zones, zoneById, cells, cellById, sumStores, sumVac, mixFor,
  units, unitById, TIER, scenarios, roiM, events, eventById, insta,
  fgHex, fgV, vacColor, arrow, rev, rad, DLAT, DLNG,
  type PKey, type TierKey,
} from "@/lib/pppp/data";
import "./LafestaPPPP.css";

/**
 * 라페스타·웨스턴돔 PPPP 통합 뷰 (React 이식).
 * 정적 프로토타입(SpaceOS_Lafesta_PPPP_Platform_Naver.html)을 컴포넌트화.
 * 지도는 네이버 Dynamic Map(JS API). 키: VITE_NAVER_MAPS_KEY_ID(.env).
 * ※ NCP 콘솔 Web 서비스 URL 에 http://localhost:5173 등록 필수.
 */

type OverlayGroups = Record<PKey, any[]>;

const TAB_META: Record<PKey, { pk: string; pn: string; pd: string; title: string; hint: string }> = {
  P1: { pk: "PLATFORM", pn: "상권 감성 지도", pd: "Place→Platform · 8구역", title: "상권 감성 히트맵", hint: "원=리뷰량 · 색=감성점수 · 클릭 상세" },
  P2: { pk: "PAGE", pn: "공실률 그리드", pd: "Product→Page · 100m", title: "100m 그리드 공실률", hint: "색=공실률 · 숫자=셀 공실률% · 클릭 상세" },
  P3: { pk: "POSTING", pn: "입점 솔루션", pd: "Promo→Posting · 3-Tier", title: "공실 유닛 추천 Tier", hint: "마커 색=추천 Tier · 클릭 비용-효용" },
  P4: { pk: "PROGRAM", pn: "마케팅 솔루션", pd: "Promo→Program · 온·오프", title: "온·오프라인 마케팅", hint: "핀=행사 거점 · 파란원=온라인 집중 발행" },
};

const avgVac = ((sumVac / sumStores) * 100).toFixed(1);
const hiCells = cells.filter((c) => c.v >= 28).length;
const topCell = [...cells].sort((a, b) => b.v - a.v)[0];

export default function LafestaPPPP() {
  const mapDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const groupsRef = useRef<OverlayGroups>({ P1: [], P2: [], P3: [], P4: [] });

  const [authFailed, setAuthFailed] = useState(false);
  const [ready, setReady] = useState(false);
  const [activeP, setActiveP] = useState<PKey>("P1");
  const [selZone, setSelZone] = useState("wes-3");
  const [selCell, setSelCell] = useState(`${topCell.i}_${topCell.j}`);
  const [selUnit, setSelUnit] = useState("u-cc");
  const [selEvent, setSelEvent] = useState("e1");
  const [subTab, setSubTab] = useState<"on" | "off">("off");
  const [live, setLive] = useState(47);

  // 지도 이동 헬퍼
  const moveTo = (lat: number, lng: number, z = 17) => {
    const m = mapRef.current, naver = (window as any).naver;
    if (m && naver) { m.setCenter(new naver.maps.LatLng(lat, lng)); m.setZoom(z); }
  };

  // 라이브 카운터
  useEffect(() => {
    const t = setInterval(() => setLive(42 + Math.floor(Math.random() * 12)), 2000);
    return () => clearInterval(t);
  }, []);

  // 지도 초기화 (1회)
  useEffect(() => {
    (window as any).navermap_authFailure = () => setAuthFailed(true);
    let cancelled = false;
    loadNaverMaps()
      .then(() => {
        if (cancelled || !mapDivRef.current) return;
        const naver = (window as any).naver;
        const LL = (a: number, b: number) => new naver.maps.LatLng(a, b);
        const map = new naver.maps.Map(mapDivRef.current, {
          center: LL(37.6593, 126.7711), zoom: 16, minZoom: 15, maxZoom: 18,
          scaleControl: false, mapDataControl: false,
          zoomControl: true, zoomControlOptions: { position: naver.maps.Position.TOP_RIGHT },
        });
        mapRef.current = map;

        // 정발산역 (항상 표시)
        new naver.maps.Marker({ map, position: LL(37.65950, 126.77415), icon: { content: '<div style="width:12px;height:12px;border-radius:50%;background:#c0504a;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4)"></div>', anchor: new naver.maps.Point(6, 6) } });
        new naver.maps.Marker({ map, position: LL(37.65950, 126.77415), icon: { content: '<div class="poi sta">◉ 정발산역</div>', anchor: new naver.maps.Point(-6, 8) } });

        const G: OverlayGroups = { P1: [], P2: [], P3: [], P4: [] };
        const add = (p: PKey, ov: any) => { G[p].push(ov); return ov; };
        const label = (p: PKey, lat: number, lng: number, html: string, ax: number, ay: number) =>
          add(p, new naver.maps.Marker({ map: null, position: LL(lat, lng), icon: { content: html, anchor: new naver.maps.Point(ax, ay) } }));

        // P1
        zones.forEach((z) => {
          const c = fgHex(z.s);
          add("P1", new naver.maps.Circle({ map: null, center: LL(z.lat, z.lng), radius: rad(z.r) * 6, strokeColor: c, strokeWeight: 1.4, strokeOpacity: 0.55, fillColor: c, fillOpacity: 0.18 }));
          const m = add("P1", new naver.maps.Marker({ map: null, position: LL(z.lat, z.lng), icon: { content: `<div class="zmk" style="background:${c}"></div>`, anchor: new naver.maps.Point(10, 10) } }));
          naver.maps.Event.addListener(m, "click", () => setSelZone(z.id));
          label("P1", z.lat, z.lng, `<div class="lbl">${z.n.replace("라페스타 ", "").replace("웨스턴돔 ", "웨돔 ")} · ${z.s.toFixed(0)}</div>`, -12, 8);
        });
        // P2
        cells.forEach((cl) => {
          const col = vacColor(cl.v);
          const rc = add("P2", new naver.maps.Rectangle({ map: null, bounds: new naver.maps.LatLngBounds(LL(cl.lat, cl.lng), LL(cl.lat + DLAT, cl.lng + DLNG)), strokeColor: "#ffffff", strokeWeight: 1, strokeOpacity: 0.7, fillColor: col, fillOpacity: 0.62 }));
          naver.maps.Event.addListener(rc, "click", () => setSelCell(`${cl.i}_${cl.j}`));
          naver.maps.Event.addListener(rc, "mouseover", () => rc.setOptions({ fillOpacity: 0.8, strokeColor: "#1f2937", strokeWeight: 2 }));
          naver.maps.Event.addListener(rc, "mouseout", () => rc.setOptions({ fillOpacity: 0.62, strokeColor: "#ffffff", strokeWeight: 1 }));
          if (cl.v >= 9) label("P2", cl.cLat, cl.cLng, `<div class="glab">${cl.v.toFixed(0)}</div>`, 5, 5);
        });
        // P3
        units.forEach((u) => {
          const t = TIER[u.rec];
          const m = add("P3", new naver.maps.Marker({ map: null, position: LL(u.lat, u.lng), icon: { content: `<div class="umk" style="background:${t.c}">${t.nm.charAt(0)}</div>`, anchor: new naver.maps.Point(11, 11) } }));
          naver.maps.Event.addListener(m, "click", () => setSelUnit(u.id));
          label("P3", u.lat, u.lng, `<div class="poi" style="color:${t.c}">${u.n.replace("웨스턴돔 ", "웨돔 ")}</div>`, -14, 8);
        });
        // P4
        add("P4", new naver.maps.Circle({ map: null, center: LL(37.65820, 126.77085), radius: 70, strokeColor: "#2563b0", strokeWeight: 1.4, strokeOpacity: 0.5, fillColor: "#2563b0", fillOpacity: 0.12 }));
        events.forEach((e) => {
          const m = add("P4", new naver.maps.Marker({ map: null, position: LL(e.lat, e.lng), icon: { content: `<div class="emk" style="background:#b06a1e">${e.ic}</div>`, anchor: new naver.maps.Point(13, 13) } }));
          naver.maps.Event.addListener(m, "click", () => setSelEvent(e.id));
          label("P4", e.lat, e.lng, `<div class="poi" style="color:#b06a1e">${e.n}</div>`, -14, 8);
        });

        groupsRef.current = G;
        setReady(true);
      })
      .catch(() => setAuthFailed(true));
    return () => { cancelled = true; };
  }, []);

  // 탭 변경 → 그룹 토글 + 기본 카메라
  useEffect(() => {
    if (!ready) return;
    const G = groupsRef.current, m = mapRef.current;
    (["P1", "P2", "P3", "P4"] as PKey[]).forEach((k) => G[k].forEach((o) => o.setMap(k === activeP ? m : null)));
    if (activeP === "P1") { const z = zoneById[selZone]; moveTo(z.lat, z.lng); }
    else if (activeP === "P2") { const c = cellById[selCell]; moveTo(c.cLat, c.cLng); }
    else if (activeP === "P3") { const u = unitById[selUnit]; moveTo(u.lat, u.lng); }
    else { const e = eventById[selEvent]; moveTo(e.lat, e.lng); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeP, ready]);

  // 선택 변경 시 카메라 추적
  useEffect(() => { if (ready && activeP === "P1") { const z = zoneById[selZone]; moveTo(z.lat, z.lng); } /* eslint-disable-next-line */ }, [selZone]);
  useEffect(() => { if (ready && activeP === "P2") { const c = cellById[selCell]; moveTo(c.cLat, c.cLng); } /* eslint-disable-next-line */ }, [selCell]);
  useEffect(() => { if (ready && activeP === "P3") { const u = unitById[selUnit]; moveTo(u.lat, u.lng); } /* eslint-disable-next-line */ }, [selUnit]);
  useEffect(() => { if (ready && activeP === "P4") { const e = eventById[selEvent]; moveTo(e.lat, e.lng); } /* eslint-disable-next-line */ }, [selEvent]);

  return (
    <div className="pppp">
      <div className="wrap">
        <div className="hd">
          <div>
            <div className="ey">SPACEOS · DIGITAL TWIN · 통합 PPPP · 네이버 실타일</div>
            <h1>일산 라페스타 · 웨스턴돔</h1>
            <div className="sub">고양시 일산동구 장항동 · 정발산역(3호선) · 네이버 Dynamic Map · Platform→Page→Posting→Program</div>
          </div>
          <div className="rt">
            <div className="chip">📍 ncpKeyId {import.meta.env.VITE_NAVER_MAPS_KEY_ID || "—"}</div>
            <div className="chip live">{live}건/s</div>
          </div>
        </div>

        <div className="ptabs">
          {(["P1", "P2", "P3", "P4"] as PKey[]).map((p) => (
            <div key={p} className={"ptab" + (activeP === p ? " on" : "")} data-p={p} onClick={() => setActiveP(p)}>
              <div className="pk">{TAB_META[p].pk}</div>
              <div className="pn">{TAB_META[p].pn}</div>
              <div className="pd">{TAB_META[p].pd}</div>
            </div>
          ))}
        </div>

        <div className="kpis">{renderKpis(activeP)}</div>

        <div className="cols">
          <div className="left">
            <div className="card">
              <div className="ch"><h2>{TAB_META[activeP].title}</h2><div className="hint">{TAB_META[activeP].hint}</div></div>
              <div className="maphost">
                <div className="map" ref={mapDivRef} />
                {authFailed && (
                  <div className="authfail"><div>
                    <h3>네이버 지도 인증 실패</h3>
                    <p>이 페이지의 도메인이 NCP 콘솔에 등록되어 있지 않습니다. 네이버 Dynamic Map은 <b>등록된 도메인</b>에서만 표시됩니다. 콘솔 → <code>Maps</code> → <code>Application</code> → <b>Web 서비스 URL</b>에 <code>http://localhost:5173</code>을 등록한 뒤 그 서버에서 열어 주세요.</p>
                  </div></div>
                )}
                <div className="nvbadge">네이버 Dynamic Map · ncpKeyId {import.meta.env.VITE_NAVER_MAPS_KEY_ID || "—"}</div>
              </div>
              <div className="legb">{renderLegend(activeP)}</div>
              <div className="flow">{renderFlow(activeP)}</div>
            </div>
          </div>
          <div className="right">
            <div className="card rp">{renderPanel()}</div>
          </div>
        </div>

        <div className="foot">SpaceOS Digital Twin Platform · 단일 네이버 지도 위 PPPP 4계층 전환. 수치는 라페스타 공실 13.6%(실측) 기준 시뮬레이션이며 실데이터 연동 시 자동 갱신. Humanistic Authority(균형·공생·공감) 설계 기준 적용.</div>
      </div>
    </div>
  );

  /* ===== 렌더 헬퍼 ===== */
  function renderKpis(p: PKey) {
    const sets: Record<PKey, { l: string; v: string | number; suf?: string; c?: string; d?: string }[]> = {
      P1: [{ l: "😊 감성 지수", v: "62.4", c: "#3a5a98" }, { l: "🗂 리뷰", v: "6,697" }, { l: "👍 긍정", v: "68.2", suf: "%", c: "#4f7a31" }, { l: "⚠ 위험 구역", v: "3", suf: "개" }, { l: "⚙ 신뢰도", v: "91.4", suf: "%" }],
      P2: [{ l: "🏢 평균 공실률", v: avgVac, suf: "%", c: "#c0392b" }, { l: "🟥 고공실 셀", v: hiCells, suf: "칸", c: "#c0392b" }, { l: "🏬 상업 셀", v: cells.length, suf: "칸" }, { l: "🪧 공실 점포", v: sumVac, suf: "곳", c: "#e8743b" }, { l: "📐 해상도", v: "100", suf: "m" }],
      P3: [{ l: "🟪 고급화", v: units.filter((u) => u.rec === "premium").length, suf: "곳", c: "#7a4f9a" }, { l: "🟩 가성비", v: units.filter((u) => u.rec === "value").length, suf: "곳", c: "#2f7d4f" }, { l: "🟧 공장제", v: units.filter((u) => u.rec === "factory").length, suf: "곳", c: "#b06a1e" }, { l: "🪧 공실 유닛", v: units.length, suf: "곳" }, { l: "⏱ 평균 회수", v: "14.6", suf: "개월", c: "#9a7b1e" }],
      P4: [{ l: "📤 주간 발행", v: "12", suf: "건", c: "#2563b0" }, { l: "🎪 행사 후보", v: "3", suf: "건", c: "#b06a1e" }, { l: "📈 유입 증대", v: "+34", suf: "%", c: "#2f7d4f" }, { l: "🤝 상생 매칭", v: "5", suf: "건" }, { l: "💬 감성 매칭", v: "92", suf: "점" }],
    };
    return sets[p].map((k, i) => (
      <div className="kpi" key={i}><div className="l">{k.l}</div>
        <div className="v" style={{ color: k.c || "inherit" }}>{k.v}{k.suf && <small>{k.suf}</small>}</div>
        {k.d && <div className="d">{k.d}</div>}
      </div>
    ));
  }

  function renderLegend(p: PKey) {
    if (p === "P1") return <><span className="lt">감성</span><span><i className="r" style={{ background: "#d9716a" }} />위험</span><span><i className="r" style={{ background: "#e3b95e" }} />주의</span><span><i className="r" style={{ background: "#7faa55" }} />양호</span><span><i className="r" style={{ background: "#3a5a98" }} />우수</span></>;
    if (p === "P2") return <><span className="lt">공실률</span><span><i className="bar" style={{ background: "#cfe3cf" }} />0~5</span><span><i className="bar" style={{ background: "#fbe7a6" }} />5~10</span><span><i className="bar" style={{ background: "#f6b96b" }} />10~18</span><span><i className="bar" style={{ background: "#e8743b" }} />18~28</span><span><i className="bar" style={{ background: "#c0392b" }} />28%+</span></>;
    if (p === "P3") return <><span className="lt">Tier</span><span><i style={{ background: "#7a4f9a" }} />고급화</span><span><i style={{ background: "#2f7d4f" }} />가성비</span><span><i style={{ background: "#b06a1e" }} />공장제</span></>;
    return <><span className="lt">마케팅</span><span><i style={{ background: "#b06a1e" }} />오프라인 행사</span><span><i className="r" style={{ background: "#2563b0" }} />온라인 발행구역</span></>;
  }

  function renderFlow(p: PKey) {
    const names = ["Platform", "Page", "Posting", "Program"];
    const idx = ["P1", "P2", "P3", "P4"].indexOf(p);
    const colors = ["var(--P1)", "var(--P2)", "var(--P3)", "var(--P4)"];
    return names.map((n, i) => (
      <span key={n} style={{ display: "contents" }}>
        {i === idx ? <b style={{ color: colors[i] }}>{`${["①", "②", "③", "④"][i]} ${n}`}</b> : <span>{n}</span>}
        {i < 3 && <span className="ar">→</span>}
      </span>
    ));
  }

  function renderPanel() {
    if (activeP === "P1") {
      const z = zoneById[selZone];
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
      const c = cellById[selCell];
      const lv = c.v < 5 ? ["양호", "#3f7d3f"] : c.v < 10 ? ["주의", "#9a7b1e"] : c.v < 18 ? ["경계", "#d2691e"] : c.v < 28 ? ["위험", "#e8743b"] : ["심각", "#c0392b"];
      const mm = mixFor(c.v);
      return (<>
        <div className="lab">선택 셀 · 100m 격자 ({c.i},{c.j})</div>
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
      const u = unitById[selUnit]; const sc = scenarios(u); const keys: TierKey[] = ["premium", "value", "factory"];
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
    // P4
    return (<>
      <div className="subtabs">
        <div className={"subtab" + (subTab === "on" ? " on" : "")} onClick={() => setSubTab("on")}>🟦 온라인</div>
        <div className={"subtab" + (subTab === "off" ? " on" : "")} onClick={() => setSubTab("off")}>🟧 오프라인</div>
      </div>
      {subTab === "on" ? (
        <div>{insta.map((t, i) => {
          const parts = t.split("\n\n");
          return (
            <div className="gen" key={i}>
              <div className="gh"><span className="pf"><span className="ic" style={{ background: "linear-gradient(135deg,#f58529,#dd2a7b)" }} />인스타 피드 #{i + 1}</span></div>
              <div className="body">{parts.slice(0, -1).join("\n\n")}</div>
              <div className="tags">{parts[parts.length - 1]}</div>
              <div className="meta">예상 도달 <b>{9 + i * 3}K</b> · 감성 매칭 <b>9{2 + i}</b></div>
            </div>
          );
        })}</div>
      ) : (
        <div>{events.map((e) => (
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
