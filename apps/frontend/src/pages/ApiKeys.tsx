/**
 * 조직 API 키 (#account) — B9 계정 화면 3/3.
 * 계약: GET /auth/me · GET /auth/api-keys · POST /auth/api-keys { name(1~100) } → 201 { …, key }
 *       · DELETE /auth/api-keys/{id} — 발급·폐기는 조직 관리자만(403).
 *
 * ⚠ **원문 키는 발급 직후 한 번만** 보인다. 서버도 원문을 저장하지 않으므로(해시만 남긴다) 목록
 *   응답에는 원문이 아예 없다. 원문은 이 화면의 React 상태에만 있고, 「보관했습니다」를 누르거나
 *   창을 닫으면 사라진다. 브라우저 저장소에 넣지 않는다(lib/session.ts 머리말).
 */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Button } from "@/design/components/Button";
import { Card } from "@/design/components/Card";
import { ACCOUNT_TITLE_ID, type AccountScreenProps } from "@/components/AccountDialog";
import {
  createApiKey, getMe, listApiKeys, revokeApiKey,
  type ApiKeyCreated, type ApiKeyInfo, type AuthMe,
} from "@/lib/api";
import { apiKeyErrorText, isSessionExpired, SESSION_EXPIRED_TEXT } from "@/lib/authText";
import { clearToken, loadToken } from "@/lib/session";
import "./Account.css";

/** 백엔드 API_KEY_PREFIX(core/security.py). 목록에서는 이 앞머리만 보이고 나머지는 가린다 */
const KEY_PREFIX = "sk_placeos_";
const KEY_NAME_MAX = 100;
const ROLE_LABEL: Record<string, string> = { admin: "관리자", member: "멤버" };

const fmtDate = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" });
};
const newestFirst = (keys: ApiKeyInfo[]) => [...keys].sort((a, b) => b.created_at.localeCompare(a.created_at));
const loadAccount = (t: string) => Promise.all([getMe(t), listApiKeys(t)]);

type Load =
  | { state: "signed-out"; note?: string }
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; me: AuthMe; keys: ApiKeyInfo[] };

export default function ApiKeys({ go }: AccountScreenProps) {
  const [token, setToken] = useState(loadToken);
  const [load, setLoad] = useState<Load>(() => (token ? { state: "loading" } : { state: "signed-out" }));
  const [name, setName] = useState("");
  const [issuing, setIssuing] = useState(false);
  const [issued, setIssued] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState<"" | "ok" | "fail">("");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [revoking, setRevoking] = useState(false);
  const [actionError, setActionError] = useState("");

  /** 401 은 어느 호출에서 오든 같은 뜻이다 — 토큰을 버리고 로그인 안내로 돌아간다. */
  const expire = useCallback(() => {
    clearToken();
    setToken(null);
    setIssued(null);
    setLoad({ state: "signed-out", note: SESSION_EXPIRED_TEXT });
  }, []);

  const onLoaded = useCallback(([me, keys]: [AuthMe, ApiKeyInfo[]]) => {
    setLoad({ state: "ready", me, keys: newestFirst(keys) });
  }, []);
  const onLoadError = useCallback((err: unknown) => {
    if (isSessionExpired(err)) expire();
    else setLoad({ state: "error", message: apiKeyErrorText(err, "불러오지") });
  }, [expire]);
  const refresh = (t: string) => loadAccount(t).then(onLoaded, onLoadError);

  // 토큰이 바뀔 때만 다시 부른다(발급·폐기는 목록을 제자리에서 고친다). 응답이 오기 전에 창을
  // 닫으면 결과를 버린다 — 닫힌 화면의 상태를 고치지 않는다.
  useEffect(() => {
    if (!token) return;
    let alive = true;
    loadAccount(token).then((r) => { if (alive) onLoaded(r); }, (err) => { if (alive) onLoadError(err); });
    return () => { alive = false; };
  }, [token, onLoaded, onLoadError]);

  function logout() {
    clearToken();
    go("login");
  }

  async function issue(e: FormEvent) {
    e.preventDefault();
    if (!token || issuing || load.state !== "ready") return;
    const trimmed = name.trim();
    if (!trimmed) {
      setActionError("키 이름을 적어 주세요. 어디에 쓰는 키인지 나중에 알아보는 이름입니다.");
      return;
    }
    setIssuing(true);
    setActionError("");
    setCopied("");
    try {
      const created = await createApiKey(token, trimmed);
      setIssued(created);
      setName("");
      const { key: _raw, ...info } = created;   // 목록에는 원문을 싣지 않는다
      setLoad((cur) => (cur.state === "ready" ? { ...cur, keys: newestFirst([info, ...cur.keys]) } : cur));
    } catch (err) {
      if (isSessionExpired(err)) expire();
      else setActionError(apiKeyErrorText(err, "발급하지"));
    } finally {
      setIssuing(false);
    }
  }

  async function revoke(id: string) {
    if (!token || revoking || load.state !== "ready") return;
    setRevoking(true);
    setActionError("");
    try {
      const updated = await revokeApiKey(token, id);
      setLoad((cur) => (cur.state === "ready"
        ? { ...cur, keys: cur.keys.map((k) => (k.id === id ? updated : k)) } : cur));
      setConfirmId(null);
    } catch (err) {
      if (isSessionExpired(err)) { expire(); return; }
      setActionError(apiKeyErrorText(err, "폐기하지"));
      setConfirmId(null);
      await refresh(token);   // 404 = 누가 먼저 지웠다 — 목록을 서버 기준으로 되돌린다
    } finally {
      setRevoking(false);
    }
  }

  async function copy(key: string) {
    try {
      await navigator.clipboard.writeText(key);
      setCopied("ok");
    } catch {
      setCopied("fail");   // 권한이 없는 브라우저 — 입력칸을 눌러 직접 복사하게 안내한다
    }
  }

  if (load.state === "signed-out") {
    return (
      <div className="acct">
        <p className="acct-eyebrow">PlaceOS 계정</p>
        <h2 id={ACCOUNT_TITLE_ID}>API 키</h2>
        {load.note && <p className="caveat-note caveat-withheld acct-error" role="alert">{load.note}</p>}
        <p className="acct-lede">조직 API 키를 보려면 로그인해 주세요. 키는 외부 시스템이 분석 API 를 부를 때(X-API-Key 헤더) 조직을 밝히는 데 씁니다.</p>
        <div className="acct-actions">
          <Button onClick={() => go("login")}>로그인</Button>
          <Button variant="ghost" onClick={() => go("signup")}>조직 가입</Button>
        </div>
      </div>
    );
  }

  if (load.state === "loading") {
    return (
      <div className="acct" aria-busy="true">
        <p className="acct-eyebrow">PlaceOS 계정</p>
        <h2 id={ACCOUNT_TITLE_ID}>API 키</h2>
        <p className="acct-lede">계정과 키 목록을 불러오는 중…</p>
      </div>
    );
  }

  if (load.state === "error") {
    return (
      <div className="acct">
        <p className="acct-eyebrow">PlaceOS 계정</p>
        <h2 id={ACCOUNT_TITLE_ID}>API 키</h2>
        <p className="caveat-note caveat-withheld acct-error" role="alert">{load.message}</p>
        <div className="acct-actions">
          <Button onClick={() => { if (token) { setLoad({ state: "loading" }); void refresh(token); } }}>다시 불러오기</Button>
          <Button variant="ghost" onClick={logout}>로그아웃</Button>
        </div>
      </div>
    );
  }

  const { me, keys } = load;
  const isAdmin = me.role === "admin";
  return (
    <div className="acct acct-wide">
      <p className="acct-eyebrow">PlaceOS 계정</p>
      <h2 id={ACCOUNT_TITLE_ID}>API 키</h2>
      <div className="acct-whoami">
        <div>
          <strong>{me.org.name}</strong>
          <span className="acct-muted">{me.email} · {ROLE_LABEL[me.role] ?? me.role}</span>
        </div>
        <Button variant="ghost" onClick={logout}>로그아웃</Button>
      </div>

      {issued && (
        <Card className="acct-reveal">
          <p className="acct-reveal-title" role="status">「{issued.name}」 키를 발급했습니다</p>
          <p className="acct-reveal-warn">
            <strong>이 키는 지금 한 번만 보입니다.</strong> 서버도 원문을 보관하지 않아, 이 상자를 닫거나 창을
            닫으면 다시 볼 수 없습니다. 안전한 곳에 복사해 두세요.
          </p>
          <div className="acct-reveal-row">
            <input className="acct-key" readOnly value={issued.key} aria-label="발급된 API 키 원문"
              autoComplete="off" spellCheck={false} onFocus={(e) => e.currentTarget.select()} />
            <Button type="button" onClick={() => void copy(issued.key)}>복사</Button>
          </div>
          {copied === "ok" && <p className="acct-muted" role="status">클립보드에 복사했습니다.</p>}
          {copied === "fail" && (
            <p className="acct-muted" role="status">자동 복사가 막혀 있습니다. 위 칸을 눌러 전체 선택한 뒤 직접 복사해 주세요.</p>
          )}
          <Button variant="ghost" type="button" onClick={() => { setIssued(null); setCopied(""); }}>
            보관했습니다 · 닫기
          </Button>
        </Card>
      )}

      {isAdmin ? (
        <form className="acct-form acct-issue" noValidate onSubmit={issue}>
          <div className="acct-field">
            <label htmlFor="key-name">새 키 이름</label>
            <input id="key-name" name="key-name" autoComplete="off" maxLength={KEY_NAME_MAX} required
              placeholder="예: 본사 BI 연동" aria-describedby="key-name-hint"
              value={name} onChange={(e) => setName(e.target.value)} />
            <small id="key-name-hint">어디에 쓴 키인지 나중에 알아보는 이름입니다(1~{KEY_NAME_MAX}자).</small>
          </div>
          <Button type="submit" disabled={issuing} aria-busy={issuing}>{issuing ? "발급 중…" : "키 발급"}</Button>
        </form>
      ) : (
        <p className="caveat-note acct-note">키 발급·폐기는 조직 관리자만 할 수 있습니다. 필요하면 관리자에게 요청해 주세요.</p>
      )}

      {actionError && <p className="caveat-note caveat-withheld acct-error" role="alert">{actionError}</p>}

      <Card className="acct-keys">
        <h3>발급된 키 {keys.length ? <span className="acct-muted num">{keys.length}개</span> : null}</h3>
        {keys.length === 0 ? (
          <p className="acct-muted">아직 발급한 키가 없습니다.</p>
        ) : (
          <ul className="acct-keylist">
            {keys.map((k) => {
              const revoked = k.revoked_at !== null;
              return (
                <li key={k.id} className={revoked ? "is-revoked" : undefined}>
                  <div className="acct-keyinfo">
                    <strong>{k.name}</strong>
                    <code aria-label="가려진 키">{KEY_PREFIX}••••••••</code>
                    <span className="acct-muted">
                      발급 {fmtDate(k.created_at)}
                      {revoked ? ` · 폐기 ${fmtDate(k.revoked_at as string)}` : " · 사용 중"}
                    </span>
                  </div>
                  {isAdmin && !revoked && (confirmId === k.id ? (
                    <div className="caveat-note caveat-withheld acct-confirm" role="group" aria-label={`${k.name} 폐기 확인`}>
                      <p>이 키로 부르던 연동은 즉시 거절(401)됩니다. 되돌릴 수 없습니다.</p>
                      <div className="acct-actions">
                        <Button type="button" disabled={revoking} onClick={() => void revoke(k.id)}>
                          {revoking ? "폐기 중…" : "폐기 확정"}
                        </Button>
                        <Button type="button" variant="ghost" disabled={revoking} onClick={() => setConfirmId(null)}>취소</Button>
                      </div>
                    </div>
                  ) : (
                    <Button type="button" variant="ghost" aria-label={`${k.name} 폐기`}
                      onClick={() => { setConfirmId(k.id); setActionError(""); }}>폐기</Button>
                  ))}
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
