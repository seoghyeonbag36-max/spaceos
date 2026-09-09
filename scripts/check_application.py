"""[Apply] 신청서 원고 근거 검사 — `docs/apply/claims.json` 밖의 수치를 잡는다.

왜 필요한가: 신청서 작성은 "잘 썼는가"를 판정하는 테스트가 없어서 Codex 로 내보낼 수
없었다(`AGENTS.md` 의 핸드오프 4항목 중 3번 '통과 조건'을 못 채운다). 이 스크립트가
통과 조건을 **기계가 판정할 수 있는 것**으로 좁혀 그 항목을 채운다.

판정하는 것은 딱 하나 — **거짓이 아닌가**. 설득력·구성·부문 선택은 보지 않는다.
그건 판단이고 판단은 위임 대상이 아니다(`.claude/skills/codex-handoff`).

검사 항목:
  1. 금지 패턴 — 폐기된 스택·모집단이 다른 옛 수치·미평가 주장 (claims.json 의 forbid)
  2. 미등재 수치 — 원고의 퍼센트·4자리 이상 수치가 claims.json 의 allow 에 있는가
  3. 조건 누락 — 등재된 수치를 썼는데 그 수치가 요구하는 한정 문구가 같은 절에 없는가
     (예: '66거점' 을 쓰면서 '건축물대장' 을 안 쓰면 실측 정확도 주장으로 읽힌다)
  4. 빈 절 — `<!-- FILL -->` 만 지우고 내용을 안 채운 자리
  5. FILL 잔여 — 제출 직전에는 0 이어야 한다 (`--require-complete`)

HTML 주석과 코드펜스는 근거 검사(1~3)에서 제외한다. FILL 마커 자체가 금지어와 수치를
지시문으로 담고 있어서, 주석까지 세면 지시문이 위반으로 잡힌다. 다만 '빈 절'(4) 은
코드·표를 **내용으로 센다** — 근거에서 빼는 것과 절이 비었는지 세는 것은 다른 판정이다.

산출: reports/application_check.json
종료코드: 위반 0 이면 0, 아니면 1

사용:
    python scripts/check_application.py
    python scripts/check_application.py --doc docs/apply/01-spatial-info/draft.md
    python scripts/check_application.py --doc <경로> --require-complete
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "docs" / "apply" / "claims.json"
APPLY_DIR = ROOT / "docs" / "apply"
OUT = ROOT / "reports" / "application_check.json"

# 검사 대상에서 빼는 파일 — 규칙 문서와 목차는 원고가 아니다.
SKIP_NAMES = {"AGENTS.md", "README.md", "claims.json"}

# 등재 대조 대상 수치: 퍼센트 · 천단위 콤마 · 4자리 이상 정수.
# 2~3자리 맨숫자(배점 20점·절 번호)까지 잡으면 오탐이 실제 위반을 덮는다.
NUM_RE = re.compile(r"\d+(?:\.\d+)?\s*%|\d{1,3}(?:,\d{3})+|\d{4,}")
HEADING_RE = re.compile(r"^#{1,6}[ \t]+.*$", re.MULTILINE)
FILL_RE = re.compile(r"<!--\s*FILL")


def _mask(text: str, *, code: bool = True) -> str:
    """HTML 주석(과 선택적으로 코드)을 같은 길이의 공백으로 덮는다.

    길이를 보존해야 위반 위치의 줄 번호가 원문과 맞는다.

    `code=False` 는 '빈 절' 판정 전용이다. 코드블록·표는 **내용**이라서, 근거 스캔에서
    빼는 것과 절이 비었는지 세는 것은 서로 다른 판정이다. 한 마스크로 둘 다 하면
    코드블록만 든 절이 빈 절로 잡힌다(2026-09-09 테스트가 잡아낸 자리).
    """
    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    text = re.sub(r"<!--.*?-->", blank, text, flags=re.DOTALL)
    if code:
        text = re.sub(r"```.*?```", blank, text, flags=re.DOTALL)
        text = re.sub(r"`[^`\n]*`", blank, text)
    return text


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _rel(path: Path) -> str:
    """저장소 기준 상대경로. 저장소 밖(임시 파일 등)이면 절대경로 그대로 쓴다."""
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _sections(masked: str) -> list[tuple[str, int, int, int]]:
    """(제목, 본문시작, 절끝, 헤딩레벨) 목록. 헤딩이 없으면 문서 전체가 한 절이다."""
    heads = list(HEADING_RE.finditer(masked))
    if not heads:
        return [("(문서 전체)", 0, len(masked), 0)]
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(masked)
        level = len(h.group(0)) - len(h.group(0).lstrip("#"))
        out.append((h.group(0).strip(), h.end(), end, level))
    return out


def _load_claims() -> dict:
    if not CLAIMS.exists():
        raise SystemExit(f"[apply] 대장이 없다: {_rel(CLAIMS)}")
    return json.loads(CLAIMS.read_text(encoding="utf-8"))


def check_doc(path: Path, claims: dict, require_complete: bool) -> dict:
    raw = path.read_text(encoding="utf-8")
    masked = _mask(raw)
    # 빈 절 판정용 — 코드·표는 내용이므로 남긴다.
    masked_body = _mask(raw, code=False)
    violations: list[dict] = []

    allowed: set[str] = set()
    for a in claims.get("allow", []):
        allowed.add(_norm(a["value"]))
        for al in a.get("aliases", []):
            allowed.add(_norm(al))

    # ── 1. 금지 패턴 ────────────────────────────────────────────
    for f in claims.get("forbid", []):
        for m in re.finditer(f["pattern"], masked):
            violations.append({
                "kind": "금지",
                "id": f["id"],
                "line": _line_of(masked, m.start()),
                "found": m.group(0).strip(),
                "why": f["why"],
                "instead": f.get("instead", ""),
            })

    # ── 2. 미등재 수치 ──────────────────────────────────────────
    # ignore 패턴이 덮는 구간(연도·전화번호·상금액)은 대조에서 뺀다.
    skip_spans: list[tuple[int, int]] = []
    for pat in claims.get("ignore", []):
        skip_spans.extend((m.start(), m.end()) for m in re.finditer(pat, masked))

    for m in NUM_RE.finditer(masked):
        if any(s <= m.start() and m.end() <= e for s, e in skip_spans):
            continue
        if _norm(m.group(0)) in allowed:
            continue
        violations.append({
            "kind": "미등재",
            "id": "",
            "line": _line_of(masked, m.start()),
            "found": m.group(0).strip(),
            "why": "claims.json 의 allow 에 없는 수치다. 먼저 출처·재현 경로와 함께 등재한 뒤 본문에 쓴다",
            "instead": "",
        })

    # ── 3. 조건 누락 ────────────────────────────────────────────
    secs = _sections(masked)
    for a in claims.get("allow", []):
        cond = a.get("condition", "")
        if not cond:
            continue
        needles = [a["value"]] + list(a.get("aliases", []))
        for title, s, e, _lvl in secs:
            body = masked[s:e]
            if not any(n in body for n in needles):
                continue
            # 조건 문구는 코드 표기(`unresolved`)로 적어도 인정한다 — 독자에게는 보이는
            # 글자다. 주석은 여전히 안 센다(그건 안 보인다). 2026-09-09 실제로 걸린 자리.
            if cond in masked_body[s:e]:
                continue
            hit = next(n for n in needles if n in body)
            violations.append({
                "kind": "조건누락",
                "id": a["id"],
                "line": _line_of(masked, s + body.index(hit)),
                "found": f"{hit} — 절 '{title}' 안에 '{cond}' 가 없다",
                "why": a["why"],
                "instead": f"같은 절에 '{cond}' 를 함께 쓴다",
            })

    # ── 4. 빈 절 ────────────────────────────────────────────────
    for i, (title, s, e, lvl) in enumerate(secs):
        if lvl == 0:
            continue
        # 바로 다음 헤딩이 더 깊으면 이 제목은 하위 절을 담는 그릇이다 — 본문이 짧아도 정상.
        if i + 1 < len(secs) and secs[i + 1][3] > lvl:
            continue
        if FILL_RE.search(raw[s:e]):
            continue  # 아직 안 채운 자리 — 5번에서 센다
        if len(masked_body[s:e].strip()) >= 30:
            continue
        violations.append({
            "kind": "빈절",
            "id": "",
            "line": _line_of(masked, s),
            "found": title,
            "why": "FILL 마커만 지우고 내용을 채우지 않았다",
            "instead": "마커를 되살리거나 본문을 쓴다",
        })

    # ── 5. FILL 잔여 ────────────────────────────────────────────
    fill_left = len(FILL_RE.findall(raw))
    if require_complete and fill_left:
        violations.append({
            "kind": "미완",
            "id": "",
            "line": _line_of(raw, FILL_RE.search(raw).start()),
            "found": f"FILL 마커 {fill_left}개 남음",
            "why": "제출 직전 검사(--require-complete)에서는 0 이어야 한다",
            "instead": "",
        })

    return {
        "doc": _rel(path),
        "fill_remaining": fill_left,
        "violations": violations,
        "ok": not violations,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="신청서 원고 근거 검사")
    ap.add_argument("--doc", action="append", default=None,
                    help="검사할 원고 (여러 번 지정 가능). 생략하면 docs/apply/ 전체")
    ap.add_argument("--require-complete", action="store_true",
                    help="FILL 마커가 남아 있으면 실패로 본다 (제출 직전용)")
    args = ap.parse_args()

    claims = _load_claims()

    if args.doc:
        docs = [Path(d) if Path(d).is_absolute() else ROOT / d for d in args.doc]
        missing = [d for d in docs if not d.exists()]
        if missing:
            for d in missing:
                print(f"[apply] 파일 없음: {d}", flush=True)
            return 1
    else:
        docs = sorted(p for p in APPLY_DIR.rglob("*.md") if p.name not in SKIP_NAMES)

    if not docs:
        print("[apply] 검사할 원고가 없다 — docs/apply/ 가 비어 있다", flush=True)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"started": datetime.now().isoformat(timespec="seconds"),
                                   "docs": [], "ok": True}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        return 0

    results = [check_doc(p, claims, args.require_complete) for p in docs]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "started": datetime.now().isoformat(timespec="seconds"),
        "claims": _rel(CLAIMS),
        "require_complete": args.require_complete,
        "docs": results,
        "ok": all(r["ok"] for r in results),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    total = 0
    for r in results:
        n = len(r["violations"])
        total += n
        mark = "OK  " if r["ok"] else "실패"
        print(f"[{mark}] {r['doc']}  (위반 {n} · FILL 잔여 {r['fill_remaining']})", flush=True)
        for v in r["violations"]:
            head = f"  L{v['line']:>4} [{v['kind']}]"
            if v["id"]:
                head += f" {v['id']}"
            print(f"{head}  {v['found']}", flush=True)
            print(f"        └ {v['why']}", flush=True)
            if v["instead"]:
                print(f"        → {v['instead']}", flush=True)

    print(f"[apply] 끝 — 원고 {len(results)}건 · 위반 {total}건 "
          f"· 기록 {_rel(OUT)}", flush=True)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
