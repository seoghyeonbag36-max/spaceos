"""data/.env 의 키 값을 안전하게 채운다 — 값을 화면·셸 히스토리·로그에 남기지 않는다.

    python scripts/set_env_key.py SGIS_CONSUMER_KEY SGIS_CONSUMER_SECRET

인자로 준 이름마다 가려진 입력(getpass)을 받아 그 자리에 넣는다.

왜 손편집 대신 이걸 쓰나:
  ① **덮어쓰기 사고 방지** — 이미 있는 줄이면 그 줄을 바꾸고, 없을 때만 끝에 붙인다.
     같은 이름을 두 줄 만들면 로더(run_collection._load_env)가 **뒤엣것을 채택**해서,
     위에 멀쩡한 키를 두고도 아래 빈 줄 때문에… 은 아니고(빈 값은 건너뛴다) 아래의
     오래된 값이 조용히 이긴다. 눈으로 찾기 어려운 종류의 고장이다.
  ② **인코딩 보존** — 이 저장소의 .env 는 utf-8 / cp949 / 메모장 ANSI 가 섞여 들어온다
     (로더가 그래서 관대하다). 읽은 인코딩 그대로 다시 쓴다.
  ③ **값을 안 찍는다** — 확인은 길이와 앞 2글자까지만 보여준다.

⚠ 이 스크립트는 값이 맞는지 **검증하지 않는다.** 넣은 뒤 반드시:
      python scripts/check_api_keys.py
   실제 호출로 PASS/FAIL 이 나오는 것이 유일한 확인이다.
"""
from __future__ import annotations

import codecs
import re
import shutil
import sys
from getpass import getpass
from pathlib import Path

# Windows 기본 콘솔은 cp949 라 em dash 하나에 print 가 죽는다 — 그러면 백업만 남고
# 값은 안 들어간 채 끝난다(2026-08-24 실측). 출력 때문에 작업이 실패하면 안 되므로
# 못 찍는 문자는 대체하고 계속 간다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "data" / ".env"
ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr")


def _read() -> tuple[str, str]:
    """(본문, 인코딩) — 로더와 같은 순서로 시도한다."""
    raw = ENV.read_bytes()
    # utf-8-sig 디코더는 BOM 이 **없어도** 성공한다. 그대로 쓰면 BOM 없던 파일에
    # BOM 을 새로 붙이게 된다 — 로더는 견디지만, 남의 파일 형식을 조용히 바꾸는 건
    # 이 스크립트가 할 일이 아니다. 그래서 BOM 은 바이트로 판정한다.
    if not raw.startswith(codecs.BOM_UTF8):
        ENCODINGS_TRY = tuple(e for e in ENCODINGS if e != "utf-8-sig")
    else:
        ENCODINGS_TRY = ENCODINGS
    for enc in ENCODINGS_TRY:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore"), "utf-8"


def _mask(v: str) -> str:
    return f"{v[:2]}…({len(v)}자)" if len(v) > 4 else f"({len(v)}자)"


def main(names: list[str]) -> int:
    if not names:
        print(__doc__)
        return 2
    if not ENV.exists():
        print(f"[!] {ENV.relative_to(ROOT)} 없음 — data/.env.example 을 복사한 뒤 다시 실행")
        return 1

    text, enc = _read()
    nl = "\r\n" if "\r\n" in text else "\n"
    # ⚠ with_suffix 는 못 쓴다 — 점파일이라 Path(".env").suffix 가 빈 문자열이고
    #   with_suffix(".env.bak") 는 `.env.env.bak` 을 만든다(2026-08-24 실측).
    backup = ENV.with_name(".env.bak")
    lines = text.splitlines()
    changed = False
    for name in names:
        val = getpass(f"{name} 값 붙여넣기(화면에 안 보임): ").strip().strip('"').strip("'")
        if not val:
            print(f"  [건너뜀] {name} — 빈 입력")
            continue
        pat = re.compile(rf"^\s*{re.escape(name)}\s*=")
        hit = [i for i, ln in enumerate(lines) if pat.match(ln)]
        if hit:
            # 여러 줄이면 마지막 줄이 로더에서 이기므로, 이기는 줄을 고친다.
            lines[hit[-1]] = f"{name}={val}"
            where = f"{len(hit)}번째 줄 중 마지막(줄 {hit[-1] + 1}) 교체"
        else:
            lines.append(f"{name}={val}")
            where = "파일 끝에 추가"
        changed = True
        print(f"  [설정] {name} = {_mask(val)} — {where}")

    if not changed:
        print("[중단] 바꾼 값이 없다 — 파일을 건드리지 않는다")
        return 1
    shutil.copy2(ENV, backup)          # 되돌릴 수 있게 — 키 파일은 다시 못 만든다
    ENV.write_bytes((nl.join(lines) + nl).encode(enc))  # 읽은 인코딩 그대로(BOM 포함) 되쓴다
    print(f"\n[완료] {ENV.relative_to(ROOT)} ({enc}) · 백업 {backup.name}")
    print("다음: python scripts/check_api_keys.py   ← 실호출로 확인")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
