/**
 * 화면당 텍스트 노드 수를 센다 — "결론 1줄 + 근거 3줄" 작업의 전/후 계측기.
 *
 * 세는 기준(작업 전후로 같은 자를 대야 비교가 성립한다):
 *   · 텍스트 노드 = JSX 자식 자리에 오는 것 중
 *       (a) 공백만이 아닌 JsxText
 *       (b) 텍스트로 렌더되는 JsxExpression — `{v}` `{cond && <…>}` `{a.map(…)}`
 *           (`{" "}` 처럼 공백뿐인 문자열 리터럴, 주석 전용 표현식은 뺀다)
 *       속성값(title=… placeholder=… hint=…)은 텍스트 노드가 아니라 세지 않는다.
 *   · **접힘** = `<details>` 안이면서 `<summary>` 밖 = 클릭해야 보이는 자리
 *   · **펼침** = 전체 − 접힘 = 화면을 열자마자 깔리는 글자
 *
 * 접힘은 컴포넌트 경계를 넘어 전파한다 — `<details><SiteCard/></details>` 면
 * `SiteCard` 본문의 글자도 접힌 것이다. 파일 안 컴포넌트의 모든 사용처가 접힌 자리일
 * 때만 그 본문을 접힘으로 본다(한 군데라도 펼쳐져 있으면 펼침으로 센다).
 *
 * 목표는 *펼침*을 줄이는 것이다. *전체*가 줄면 데이터를 지운 것이니 두 숫자를
 * 같이 낸다 — 접은 것과 지운 것은 다르다.
 *
 * 한계: 정적 계측이다. `{err && <…>}` 같은 조건부 블록은 실제로 안 보여도 펼침으로
 * 센다. 그래서 이 수치는 실제 화면 글자 수의 **상한**이다.
 *
 * 사용: node scripts/count-text-nodes.mjs [--detail] src/pages/PlatformConsole.tsx …
 */
import { readFileSync } from "node:fs";
import ts from "typescript";

/** `{" "}` · `{/* 주석 *\/}` 처럼 화면에 글자를 내지 않는 표현식은 세지 않는다 */
function rendersText(expr) {
  if (!expr) return false;                                   // {/* 주석 */}
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) {
    return expr.text.trim() !== "";
  }
  return true;
}

/** 이 노드가 컴포넌트 선언이면 그 이름 — `function Foo()` · `const Foo = () => …` */
function componentNameOf(node) {
  if (ts.isFunctionDeclaration(node) && node.name) return node.name.text;
  if ((ts.isArrowFunction(node) || ts.isFunctionExpression(node))
      && ts.isVariableDeclaration(node.parent) && ts.isIdentifier(node.parent.name)) {
    return node.parent.name.text;
  }
  return null;
}

/** 접는 자리를 여는 태그. `Fold`(components/Verdict.tsx)는 `<details>` 를 그대로 낸다 —
 *  다른 파일이라 AST 로는 안 보이므로 여기에 이름으로 적어 둔다. */
const FOLD_TAGS = new Set(["details", "Fold"]);

/** 접는 태그/`<summary>` 로 국소 접힘 상태를 갱신한다 */
function scopeFor(node, src, folded) {
  if (!ts.isJsxElement(node)) return folded;
  const tag = node.openingElement.tagName.getText(src);
  if (FOLD_TAGS.has(tag)) return true;
  if (tag === "summary") return false;                       // 요약줄은 늘 보인다
  return folded;
}

function analyse(file) {
  const src = ts.createSourceFile(
    file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX,
  );

  /* ── 1) 파일 안 컴포넌트의 사용처를 모은다: {안은 컴포넌트, 국소 접힘} ── */
  const declared = new Set();
  (function collect(node) {
    const n = componentNameOf(node);
    if (n && /^[A-Z]/.test(n)) declared.add(n);
    ts.forEachChild(node, collect);
  })(src);

  const uses = [];                       // {name, host, localFolded}
  (function walk(node, folded, host) {
    const scope = scopeFor(node, src, folded);
    const self = componentNameOf(node);
    const nextHost = self && declared.has(self) ? self : host;
    // 컴포넌트 본문에 들어가면 국소 접힘은 리셋된다(본문의 접힘은 본문이 정한다)
    const nextFolded = self && declared.has(self) ? false : scope;

    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const open = ts.isJsxElement(node) ? node.openingElement : node;
      const tag = open.tagName.getText(src);
      if (declared.has(tag)) uses.push({ name: tag, host, localFolded: folded });
    }
    ts.forEachChild(node, (c) => walk(c, nextFolded, nextHost));
  })(src, false, null);

  /* ── 2) 최대 고정점: "모든 사용처가 접혀 있는" 컴포넌트만 접힘으로 둔다 ── */
  const used = new Set(uses.map((u) => u.name));
  const bodyFolded = new Map();
  for (const n of declared) bodyFolded.set(n, used.has(n));   // 안 쓰이면 펼침(보수적)
  for (let i = 0; i < declared.size + 2; i++) {
    let changed = false;
    for (const u of uses) {
      const hostFolded = u.host ? bodyFolded.get(u.host) === true : false;
      if (!(u.localFolded || hostFolded) && bodyFolded.get(u.name) !== false) {
        bodyFolded.set(u.name, false); changed = true;
      }
    }
    if (!changed) break;
  }

  /* ── 3) 텍스트 노드를 센다 ── */
  let total = 0, folded = 0;
  const rows = [];
  (function walk(node, local, host) {
    const scope = scopeFor(node, src, local);
    const self = componentNameOf(node);
    const nextHost = self && declared.has(self) ? self : host;
    const nextLocal = self && declared.has(self) ? false : scope;

    if (ts.isJsxElement(node) || ts.isJsxFragment(node)) {
      const hostFolded = host ? bodyFolded.get(host) === true : false;
      for (const child of node.children) {
        const isText = ts.isJsxText(child) && child.getText(src).trim() !== "";
        const isExpr = ts.isJsxExpression(child) && rendersText(child.expression);
        if (!isText && !isExpr) continue;
        const hidden = scope || hostFolded;
        total++; if (hidden) folded++;
        const { line } = src.getLineAndCharacterOfPosition(child.getStart(src));
        rows.push({ line: line + 1, hidden, host: host ?? "(module)",
                    text: child.getText(src).trim().replace(/\s+/g, " ").slice(0, 58) });
      }
    }
    ts.forEachChild(node, (c) => walk(c, nextLocal, nextHost));
  })(src, false, null);

  return { file, total, folded, open: total - folded, rows };
}

const args = process.argv.slice(2);
const detail = args.includes("--detail");
const files = args.filter((a) => !a.startsWith("--"));
if (!files.length) { console.error("usage: node scripts/count-text-nodes.mjs [--detail] <file.tsx…>"); process.exit(1); }

const pad = (s, n) => String(s).padStart(n);
console.log("파일".padEnd(40) + pad("펼침", 8) + pad("접힘", 8) + pad("전체", 8));
console.log("─".repeat(64));
for (const f of files) {
  const r = analyse(f);
  console.log(r.file.padEnd(40) + pad(r.open, 8) + pad(r.folded, 8) + pad(r.total, 8));
  if (detail) {
    for (const row of r.rows) {
      console.log(`   ${row.hidden ? "접" : "펼"} ${pad(row.line, 4)}  ${row.host.padEnd(20)} ${row.text}`);
    }
  }
}
