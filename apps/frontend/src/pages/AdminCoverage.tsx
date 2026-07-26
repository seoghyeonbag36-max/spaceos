import { useEffect, useState } from "react";

/**
 * 관리자 전용 커버리지 패널 — 지도에 표시되지 않는 '제외 건물' 을 여기서만 본다.
 *
 * 공개 지도(MapShell)는 건축물대장으로 capacity 를 확인한 건물만 그린다. 대장 미확인
 * 건물은 빠지는데(연남동 433동), 그 사실을 사용자 화면에 섞으면 근거가 다른 데이터가
 * 한 지도에 오게 된다. 그래서 제외 현황은 이 패널에만 노출한다(2026-07-26).
 *
 * 진입: URL 해시 #admin. 네비게이션에 링크를 두지 않는다 — 아는 사람만 들어온다.
 * 데이터는 X-Admin-Token 헤더가 있어야 오므로, 토큰 없이는 화면만 열리고 값은 안 나온다.
 */
type Hub = {
  slug: string;
  hub_name: string;
  tier: string;
  built_at: string;
  shown: number;
  excluded_unknown: number;
  excluded_non_commercial: number;
  coverage_pct: number | null;
  reference_vacancy_pct: number | null;
};
type Payload = {
  hubs: Hub[];
  totals: {
    hubs: number; shown: number; excluded_unknown: number;
    excluded_non_commercial: number; coverage_pct: number | null;
  };
};

const TOKEN_KEY = "spaceos.adminToken";

export default function AdminCoverage() {
  // 토큰은 세션 스토리지에만 둔다 — 새 탭·재시작이면 다시 입력한다.
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) ?? "");
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function load(t: string) {
    if (!t) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/admin/coverage", { headers: { "X-Admin-Token": t } });
      if (!res.ok) {
        setData(null);
        setError(res.status === 403
          ? "토큰이 올바르지 않거나 서버에 ADMIN_TOKEN 이 설정되지 않았습니다."
          : `요청 실패 (${res.status})`);
        return;
      }
      setData(await res.json());
      sessionStorage.setItem(TOKEN_KEY, t);
    } catch {
      setData(null);
      setError("서버에 연결하지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (token) load(token); }, []);   // 저장된 토큰이 있으면 자동 조회

  const t = data?.totals;
  return (
    <div style={{ padding: "24px 28px", maxWidth: 1000, margin: "0 auto", fontSize: 13 }}>
      <h1 style={{ fontSize: 18, margin: "0 0 4px" }}>지도 커버리지 (관리자)</h1>
      <p style={{ color: "#6b7280", margin: "0 0 18px" }}>
        공개 지도에는 <strong>건축물대장으로 capacity 를 확인한 건물만</strong> 표시됩니다.
        아래 제외 동수는 이 화면에서만 확인할 수 있습니다.
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input
          type="password" value={token} placeholder="ADMIN_TOKEN"
          onChange={(e) => setToken(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") load(token); }}
          style={{ flex: "0 0 260px", padding: "7px 10px", fontSize: 13,
                   border: "1px solid #e5e7eb", borderRadius: 8 }}
        />
        <button onClick={() => load(token)} disabled={!token || loading}
          style={{ padding: "7px 14px", fontSize: 13, fontWeight: 700, borderRadius: 8,
                   border: "1px solid #3a5a98", background: "#3a5a98", color: "#fff",
                   cursor: token ? "pointer" : "not-allowed", opacity: token ? 1 : .5 }}>
          {loading ? "조회 중…" : "조회"}
        </button>
      </div>

      {error && (
        <div style={{ padding: "10px 12px", borderRadius: 8, marginBottom: 16,
                      background: "#fef2f2", color: "#b91c1c", border: "1px solid #fecaca" }}>
          {error}
        </div>
      )}

      {t && (
        <div style={{ display: "flex", gap: 10, marginBottom: 18, flexWrap: "wrap" }}>
          <Tile label="거점" value={`${t.hubs}곳`} />
          <Tile label="지도 표시" value={`${t.shown.toLocaleString()}동`} />
          <Tile label="대장 미확인 제외" value={`${t.excluded_unknown.toLocaleString()}동`} warn />
          <Tile label="비상업 제외" value={`${t.excluded_non_commercial.toLocaleString()}동`} />
          <Tile label="커버리지" value={t.coverage_pct != null ? `${t.coverage_pct}%` : "—"} />
        </div>
      )}

      {data && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", whiteSpace: "nowrap" }}>
            <thead>
              <tr style={{ textAlign: "right", color: "#6b7280", borderBottom: "1px solid #e5e7eb" }}>
                <th style={{ textAlign: "left", padding: "8px 10px" }}>거점</th>
                <th style={{ padding: "8px 10px" }}>표시</th>
                <th style={{ padding: "8px 10px" }}>대장 미확인</th>
                <th style={{ padding: "8px 10px" }}>비상업</th>
                <th style={{ padding: "8px 10px" }}>커버리지</th>
                <th style={{ padding: "8px 10px" }}>참고 공실률</th>
                <th style={{ textAlign: "left", padding: "8px 10px" }}>빌드</th>
              </tr>
            </thead>
            <tbody>
              {data.hubs.map((h) => (
                <tr key={h.slug} style={{ textAlign: "right", borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ textAlign: "left", padding: "8px 10px", fontWeight: 700 }}>
                    {h.hub_name} <span style={{ color: "#9ca3af", fontWeight: 400 }}>{h.slug}</span>
                  </td>
                  <td style={{ padding: "8px 10px" }}>{h.shown.toLocaleString()}</td>
                  <td style={{ padding: "8px 10px", color: h.excluded_unknown > 300 ? "#b91c1c" : "#111" }}>
                    {h.excluded_unknown.toLocaleString()}
                  </td>
                  <td style={{ padding: "8px 10px", color: "#6b7280" }}>
                    {h.excluded_non_commercial.toLocaleString()}
                  </td>
                  <td style={{ padding: "8px 10px" }}>{h.coverage_pct != null ? `${h.coverage_pct}%` : "—"}</td>
                  <td style={{ padding: "8px 10px" }}>
                    {h.reference_vacancy_pct != null ? `${h.reference_vacancy_pct}%` : "—"}
                  </td>
                  <td style={{ textAlign: "left", padding: "8px 10px", color: "#9ca3af" }}>
                    {h.built_at.replace("T", " ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Tile({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div style={{ padding: "10px 14px", borderRadius: 10, minWidth: 120,
                  border: "1px solid " + (warn ? "#fecaca" : "#e5e7eb"),
                  background: warn ? "#fef2f2" : "#fafbfc" }}>
      <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 800, color: warn ? "#b91c1c" : "#111" }}>{value}</div>
    </div>
  );
}
