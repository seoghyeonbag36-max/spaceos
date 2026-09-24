/**
 * 로그인 (#login) — B9 계정 화면 1/3.
 * 계약: POST /api/v1/auth/login { email, password } → { access_token } · 401 불일치.
 */
import { useState, type FormEvent } from "react";
import { Button } from "@/design/components/Button";
import { ACCOUNT_TITLE_ID, type AccountScreenProps } from "@/components/AccountDialog";
import { login } from "@/lib/api";
import { loginErrorText } from "@/lib/authText";
import { saveToken } from "@/lib/session";
import "./Account.css";

export default function Login({ go }: AccountScreenProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    if (!email.trim() || !password) {
      setError("이메일과 비밀번호를 모두 적어 주세요.");
      return;
    }
    setPending(true);
    setError("");
    try {
      const token = await login({ email: email.trim(), password });
      saveToken(token.access_token);
      go("account");
    } catch (err) {
      setError(loginErrorText(err));
      setPending(false);
    }
  }

  return (
    <div className="acct">
      <p className="acct-eyebrow">PlaceOS 계정</p>
      <h2 id={ACCOUNT_TITLE_ID}>로그인</h2>
      <p className="acct-lede">조직 계정으로 로그인하면 API 키를 발급·관리할 수 있습니다.</p>

      {/* method="post" — 스크립트가 죽어 브라우저 기본 제출로 떨어져도 비밀번호가 URL 에 실리지 않게 한다 */}
      <form className="acct-form" method="post" noValidate onSubmit={submit}>
        <label className="acct-field">
          <span>이메일</span>
          <input type="email" name="email" autoComplete="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="acct-field">
          <span>비밀번호</span>
          <input type="password" name="password" autoComplete="current-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="caveat-note caveat-withheld acct-error" role="alert">{error}</p>}
        <Button type="submit" disabled={pending} aria-busy={pending}>{pending ? "로그인 중…" : "로그인"}</Button>
      </form>

      <p className="acct-switch">
        처음이신가요?{" "}
        <button type="button" className="acct-link" onClick={() => go("signup")}>조직 가입</button>
      </p>
    </div>
  );
}
