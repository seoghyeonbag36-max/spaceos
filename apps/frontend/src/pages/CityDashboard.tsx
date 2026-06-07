import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { loadNaverMaps } from "@/lib/naverMap";
import { listDistricts } from "@/lib/api";
import { fgHex, vacHex, DISTRICTS as STATIC_DISTRICTS } from "@/lib/districts/summary";
import "./CityDashboard.css";

/**
 * 고양시 9거점 비교 대시보드.
 * 데이터 출처: 백엔드 GET /api/v1/commercial-districts (로딩/에러/재시도).
 * 백엔드 미연결 시 정적 모듈로 폴백 가능.
 */
type Metric = "s" | "v";
interface DD {
  id: string; name: string; gu: string; type: string; center: [number, number];
  sent: number; reviews: number; risk: number; vac: number; vacN: number; note: string; recTop: string;
}

const metricVal = (d: DD, m: Metric) => (m === "s" ? d.sent : d.vac);
const metricColor = (d: DD, m: Metric) => (m === "s" ? fgHex(d.sent) : vacHex(d.vac));

// 백엔드 요약 응답 → 화면 모델
function mapApi(x: any): DD {
  return {
    id: x.id, name: x.name, gu: x.gu, type: x.type, center: x.center,
    sent: x.sentiment, reviews: x.reviews, risk: x.risk_zones,
    vac: x.vacancy_rate, vacN: x.vacant_units, note: x.note, recTop: x.rec_top,
  };
}
// 정적 폴백 (백엔드 동일 집계)
function staticFallback(): DD[] {
  return STATIC_DISTRICTS.map((d) => ({
    id: d.id, name: d.name, gu: d.gu, type: d.type, center: d.center,
    sent: d.sent, reviews: d.reviews, risk: d.risk, vac: d.vac, vacN: d.vacN, note: d.note, recTop: d.recTop,
  }));
}

export default function CityDashboard({ onOpenDistrict }: { onOpenDistrict?: (id: string) => void }) {
  const [districts, setDistricts] = useState<DD[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metric, setMetric] = useState<Metric>("s");
  const [selId, setSelId] = useState<string>("");
  const [authFailed, setAuthFailed] = useState(false);
  const [mapReady, setMapReady] = useState(0);

  const mapDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const readyRef = useRef(false);

  // 데이터 로드
  const load = () => {
    setLoading(true); setError(null);
    listDistricts()
      .then((rows) => {
        const dd = (rows as any[]).map(mapApi);
        setDistricts(dd);
        setSelId((s) => s || dd[0]?.id || "");
        setLoading(false);
      })
      .catch((e: Error) => { setError(e.message || "불러오기 실패"); setLoading(false); });
  };
  useEffect(load, []);

  // 지도 init (데이터 로드되어 지도 div가 렌더된 후 1회)
  useEffect(() => {
    if (loading || !districts || mapRef.current) return;
    (window as any).navermap_authFailure = () => setAuthFailed(true);
    let cancelled = false;
    loadNaverMaps()
      .then(() => {
        if (cancelled || !mapDivRef.current || mapRef.current) return;
        const naver = (window as any).naver;
        mapRef.current = new naver.maps.Map(mapDivRef.current, {
          center: new naver.maps.LatLng(37.652, 126.808), zoom: 12, minZoom: 11, maxZoom: 16,
          scaleControl: false, mapDataControl: false, zoomControl: true,
          zoomControlOptions: { position: naver.maps.Position.TOP_RIGHT },
        });
        readyRef.current = true;
        setMapReady((n) => n + 1);
      })
      .catch(() => setAuthFailed(true));
    return () => { cancelled = true; };
  }, [loading, districts]);

  const mkSize = (d: DD) => Math.max(20, Math.min(46, metric === "s" ? 20 + d.reviews / 130 : 22 + d.vacN / 9));

  // 마커 그리기
  useEffect(() => {
    if (!readyRef.current || !districts) return;
    const naver = (window as any).naver, map = mapRef.current;
    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];
    districts.forEach((d) => {
      const col = metricColor(d, metric), sz = mkSize(d), val = metricVal(d, metric);
      const sel = d.id === selId ? "outline:3px solid #1f2937;outline-offset:2px;" : "";
      const mk = new naver.maps.Marker({
        map, position: new naver.maps.LatLng(d.center[0], d.center[1]),
        icon: { content: `<div class="dmk" style="width:${sz}px;height:${sz}px;background:${col};${sel}">${val.toFixed(0)}</div>`, anchor: new naver.maps.Point(sz / 2, sz / 2) },
        zIndex: d.id === selId ? 200 : 100,
      });
      naver.maps.Event.addListener(mk, "click", () => setSelId(d.id));
      const lbl = new naver.maps.Marker({ map, position: new naver.maps.LatLng(d.center[0], d.center[1]), icon: { content: `<div class="dlbl">${d.name}</div>`, anchor: new naver.maps.Point(-(sz / 2) - 4, 7) } });
      markersRef.current.push(mk, lbl);
    });
  }, [districts, metric, selId, mapReady]);

  // 선택 카메라 이동
  useEffect(() => {
    if (!readyRef.current || !districts) return;
    const naver = (window as any).naver, d = districts.find((x) => x.id === selId);
    if (d) { mapRef.current.setCenter(new naver.maps.LatLng(d.center[0], d.center[1])); mapRef.current.setZoom(13); }
  }, [selId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ----- 로딩 / 에러 -----
  if (loading) return <Centered>📡 거점 데이터를 불러오는 중…</Centered>;
  if (error || !districts) return (
    <Centered>
      <div style={{ color: "#b23b39", fontWeight: 700, marginBottom: 8 }}>거점 데이터를 불러오지 못했습니다</div>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 14 }}>백엔드(/api/v1) 연결을 확인하세요. {error}</div>
      <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
        <SmallBtn onClick={load}>다시 시도</SmallBtn>
        <SmallBtn onClick={() => { setDistricts(staticFallback()); setSelId((s) => s || "lafesta"); setError(null); }}>정적 데이터로 보기</SmallBtn>
      </div>
    </Centered>
  );

  const sortedD = [...districts].sort((a, b) => (metric === "s" ? b.sent - a.sent : b.vac - a.vac));
  const sel = districts.find((d) => d.id === selId) ?? districts[0];
  const sAvg = districts.reduce((a, d) => a + d.sent, 0) / districts.length;
  const vAvg = districts.reduce((a, d) => a + d.vac, 0) / districts.length;
  const topS = [...districts].sort((a, b) => b.sent - a.sent)[0];
  const worstV = [...districts].sort((a, b) => b.vac - a.vac)[0];
  const totRev = districts.reduce((a, d) => a + d.reviews, 0);
  const totVac = districts.reduce((a, d) => a + d.vacN, 0);
  const maxBar = metric === "s" ? 100 : Math.max(...districts.map((d) => d.vac));

  const kpis: { l: string; v: string | number; suf?: string; c?: string; d: string }[] = [
    { l: "🏙 거점 수", v: districts.length, suf: "개", d: "일산동·서구·덕양구" },
    { l: "😊 평균 감성지수", v: sAvg.toFixed(1), c: fgHex(sAvg), d: "최고 " + topS.name.split("·")[0] },
    { l: "🏢 평균 공실률", v: vAvg.toFixed(1), suf: "%", c: "#c0392b", d: "최고 " + worstV.name.split("·")[0] },
    { l: "🗂 누적 리뷰", v: (totRev / 1000).toFixed(1), suf: "K", d: "9거점 합산" },
    { l: "🪧 총 공실 점포", v: totVac, suf: "곳", d: "입점 솔루션 후보" },
  ];

  return (
    <div className="citydash">
      <div className="wrap">
        <div className="hd">
          <div>
            <div className="ey">SPACEOS · DIGITAL TWIN · 고양시 전체 비교 대시보드</div>
            <h1>고양시 9거점 상권 비교</h1>
            <div className="sub">일산동구·일산서구·덕양구 9개 거점 · API 연동 · 감성지수 vs 공실률 · 거점 클릭 → 상세</div>
          </div>
          <div className="toggle">
            <button className={metric === "s" ? "on" : ""} onClick={() => setMetric("s")}>😊 감성지수</button>
            <button className={metric === "v" ? "on" : ""} onClick={() => setMetric("v")}>🏢 공실률</button>
          </div>
        </div>

        <div className="kpis">
          {kpis.map((x, i) => (
            <div className="kpi" key={i}><div className="l">{x.l}</div>
              <div className="v" style={{ color: x.c || "inherit" }}>{x.v}{x.suf && <small>{x.suf}</small>}</div>
              <div className="d">{x.d}</div>
            </div>
          ))}
        </div>

        <div className="cols">
          <div className="left"><div className="card">
            <div className="ch"><h2>거점별 {metric === "s" ? "감성지수" : "공실률"} 지도</h2><div className="hint">원 크기=리뷰량/공실규모 · 색=지표 · 클릭 → 상세</div></div>
            <div style={{ position: "relative" }}>
              <div className="map" ref={mapDivRef} />
              {authFailed && (
                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(247,246,242,.96)", borderRadius: 12, padding: 24, textAlign: "center", fontSize: 13, color: "#6b7280", lineHeight: 1.7 }}>
                  네이버 지도 인증 실패 — NCP 콘솔 Web 서비스 URL에 <code>http://localhost:5173</code> 등록 후 그 서버에서 열어 주세요.
                </div>
              )}
            </div>
            <div className="legb">
              <span className="lt">{metric === "s" ? "감성" : "공실률"}</span>
              {metric === "s" ? (
                <><span><i style={{ background: "#d9716a" }} />위험</span><span><i style={{ background: "#e3b95e" }} />주의</span><span><i style={{ background: "#9ab85a" }} />양호</span><span><i style={{ background: "#3a5a98" }} />우수</span></>
              ) : (
                <><span><i style={{ background: "#cfe3cf" }} />낮음</span><span><i style={{ background: "#fbe7a6" }} />보통</span><span><i style={{ background: "#e8743b" }} />높음</span><span><i style={{ background: "#c0392b" }} />심각</span></>
              )}
            </div>
          </div></div>

          <div className="right">
            <div className="card">
              <div className="ch"><h2>{metric === "s" ? "감성지수" : "공실률"} 랭킹</h2><div className="hint">클릭 시 지도 이동</div></div>
              <div className="rk">
                {sortedD.map((d, i) => {
                  const val = metricVal(d, metric), col = metricColor(d, metric);
                  return (
                    <div className={"rkr" + (d.id === selId ? " sel" : "")} key={d.id} onClick={() => setSelId(d.id)}>
                      <div className="rn">{i + 1}</div>
                      <div className="rinfo">
                        <div className="rnm">{d.name}</div>
                        <div className="rgu">{d.gu} · {d.type}</div>
                        <div className="rbarw"><i style={{ width: `${(val / maxBar) * 100}%`, background: col }} /></div>
                      </div>
                      <div className="rv" style={{ color: col }}>{val.toFixed(1)}{metric === "v" ? "%" : ""}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="card det">
              <div className="dh"><div><div className="dn">{sel.name}</div><div className="dg">{sel.gu} · {sel.type}</div></div></div>
              <div className="dmet">
                <div className="mc"><div className="mk">😊 감성지수</div><div className="mv" style={{ color: fgHex(sel.sent) }}>{sel.sent.toFixed(1)}</div></div>
                <div className="mc"><div className="mk">🏢 공실률</div><div className="mv" style={{ color: vacHex(sel.vac) }}>{sel.vac.toFixed(1)}%</div></div>
                <div className="mc"><div className="mk">🗂 누적 리뷰</div><div className="mv">{sel.reviews.toLocaleString()}</div></div>
                <div className="mc"><div className="mk">⚠ 위험구역 / 공실</div><div className="mv">{sel.risk}개 · {sel.vacN}곳</div></div>
              </div>
              <div className="note">{sel.note}</div>
              <button className="btn" onClick={() => onOpenDistrict?.(sel.id)}>이 거점 PPPP 심층분석 열기 ↗</button>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="ch"><h2>9거점 종합 비교표</h2><div className="hint">행 클릭 → 상세 · 정렬: 현재 지표</div></div>
          <div style={{ overflowX: "auto" }}>
            <table className="tbl">
              <thead><tr><th className="nm">거점</th><th>감성</th><th>공실률</th><th>리뷰</th><th>위험구역</th><th>공실점포</th><th>추천Tier</th></tr></thead>
              <tbody>
                {sortedD.map((d) => (
                  <tr className={d.id === selId ? "sel" : ""} key={d.id} onClick={() => setSelId(d.id)}>
                    <td className="nm">{d.name}<div style={{ fontSize: 10, color: "#9aa3af", fontWeight: 400 }}>{d.gu}</div></td>
                    <td><span className="pill" style={{ background: fgHex(d.sent) + "22", color: fgHex(d.sent) }}>{d.sent.toFixed(1)}</span></td>
                    <td><span className="pill" style={{ background: vacHex(d.vac) + "22", color: vacHex(d.vac) }}>{d.vac.toFixed(1)}%</span></td>
                    <td>{d.reviews.toLocaleString()}</td>
                    <td style={{ color: d.risk ? "#b23b39" : "#4f7a31" }}>{d.risk}개</td>
                    <td>{d.vacN}곳</td>
                    <td>{d.recTop}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="foot">SpaceOS Digital Twin Platform · 고양시 9거점 비교 · 데이터: /api/v1/commercial-districts. 감성지수=구역 감성의 리뷰가중 평균, 공실률=100m 그리드 합성 평균.</div>
      </div>
    </div>
  );
}

function Centered({ children }: { children: ReactNode }) {
  return <div className="citydash"><div className="wrap"><div className="card" style={{ textAlign: "center", padding: "48px 20px", marginTop: 40 }}>{children}</div></div></div>;
}
function SmallBtn({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button onClick={onClick} style={{ fontFamily: "inherit", fontSize: 13, fontWeight: 700, cursor: "pointer", padding: "8px 14px", borderRadius: 9, border: "1px solid #3a5a98", background: "#3a5a98", color: "#fff" }}>{children}</button>;
}
