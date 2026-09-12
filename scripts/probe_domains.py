# -*- coding: utf-8 -*-
"""도메인 등록 여부를 **레지스트리에 직접** 물어 판정한다 (2026-09-12 개명 재조사용).

왜 검색이 아니라 이것인가: 웹 검색은 *기존 서비스의 존재*를 보여줄 뿐 등록 가능
여부를 말하지 않는다. 반대로 whois/RDAP 는 레지스트리의 답이라 등록 여부만큼은
확정된다(상표는 별개 절차 — docs/finding-placeos-name-2026-09-12.md §4).

⚠ **대조군 없이 음성(미등록)을 믿지 말 것.** 엉뚱한 서버에 물으면 등록된 도메인도
404 로 돌아온다. 실제로 rdap.org 는 .kr·.io·.co 를 모른 채 404 를 줬다. 그래서
TLD 마다 반드시 등록돼 있는 도메인을 같이 물어 프로브가 살아 있는지 먼저 본다.

    python scripts/probe_domains.py            # 표로 출력
    python scripts/probe_domains.py --json <경로>
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.request
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

RDAP = {                       # TLD → (RDAP 기준 URL, 반드시 등록돼 있는 대조군)
    "com": ("https://rdap.verisign.com/com/v1/domain", "google.com"),
    "net": ("https://rdap.verisign.com/net/v1/domain", "example.net"),
    "org": ("https://rdap.publicinterestregistry.org/rdap/domain", "example.org"),
    "io":  ("https://rdap.identitydigital.services/rdap/domain", "github.io"),
    "ai":  ("https://rdap.org/domain", "character.ai"),
}
WHOIS = {                      # 접미사 → (whois 서버, 대조군)
    ".kr": ("whois.kr", "naver.co.kr"),
}
KR_FREE = "등록되어 있지 않"    # KISA 가 미등록일 때 돌려주는 문구


def _rdap(base: str, domain: str) -> str:
    # ⚠ User-Agent 를 안 보내면 일부 RDAP 서버가 403 을 준다 — 대조군이 이걸 잡는다
    req = urllib.request.Request(f"{base}/{domain}", headers={
        "Accept": "application/rdap+json",
        "User-Agent": "placeos-domain-probe/1.0 (+brand rename check)",
    })
    try:
        with urllib.request.urlopen(req, timeout=25):
            return "registered"
    except urllib.error.HTTPError as e:
        return "free" if e.code == 404 else f"error:http{e.code}"
    except Exception as e:                      # 네트워크·DNS 실패는 판정이 아니다
        return f"error:{type(e).__name__}"


def _whois(server: str, domain: str) -> str:
    try:
        s = socket.create_connection((server, 43), timeout=25)
        s.sendall((domain + "\r\n").encode())
        buf = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        s.close()
    except Exception as e:
        return f"error:{type(e).__name__}"
    text = buf.decode("utf-8", "replace")
    if KR_FREE in text or "not registered" in text.lower():
        return "free"
    if "등록인" in text or "Registrant" in text:
        return "registered"
    return "error:unparsed"


def check(domain: str) -> str:
    if domain.endswith(".kr"):
        server, _ = WHOIS[".kr"]
        return _whois(server, domain)
    tld = domain.rsplit(".", 1)[-1]
    if tld not in RDAP:
        return "error:no-probe"
    return _rdap(RDAP[tld][0], domain)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="기계가 읽을 결과를 쓸 경로")
    ap.add_argument("domains", nargs="*", help="비우면 기본 후보 목록")
    args = ap.parse_args()

    targets = args.domains or [
        "placeos.com", "placeos.net", "placeos.org", "placeos.io", "placeos.ai",
        "placeos.kr", "placeos.co.kr", "placeos.or.kr",
        "placetwin.kr", "placetwin.co.kr", "spacetwin.co.kr",
        "streetos.kr", "twinmap.kr", "gongsil.kr", "spaceos.kr",
    ]

    # 1) 대조군 — 프로브가 살아 있는지부터 본다
    controls: dict[str, dict[str, str]] = {}
    for tld, (base, ctl) in RDAP.items():
        controls[tld] = {"domain": ctl, "result": _rdap(base, ctl)}
    server, ctl = WHOIS[".kr"]
    controls["kr"] = {"domain": ctl, "result": _whois(server, ctl)}
    dead = [t for t, c in controls.items() if c["result"] != "registered"]

    results = {d: check(d) for d in targets}

    print(f"프로브 대조군 — 전부 'registered' 여야 한다 ({date.today()})")
    for tld, c in controls.items():
        mark = "OK" if c["result"] == "registered" else "⚠ 판정불가"
        print(f"  .{tld:<4} {c['domain']:<16} {c['result']:<12} {mark}")
    if dead:
        print(f"\n⚠ 대조군이 깨진 TLD: {', '.join('.'+t for t in dead)} — 이 TLD 의 결과는 믿지 말 것\n")

    print("\n도메인 등록 여부")
    for d, r in results.items():
        tld = "kr" if d.endswith(".kr") else d.rsplit(".", 1)[-1]
        suspect = " ⚠대조군깨짐" if tld in dead else ""
        label = {"free": "✅ 미등록", "registered": "❌ 등록됨"}.get(r, f"? {r}")
        print(f"  {d:<18} {label}{suspect}")

    if args.json:
        payload = {
            "probed_at": date.today().isoformat(),
            "method": "registry RDAP (rdap.*) + KISA whois.kr:43",
            "controls": controls,
            "unreliable_tlds": dead,
            "results": results,
            "caveat": "등록 여부만 판정한다. 상표 선등록은 KIPRIS·USPTO·IP Australia 별도 조회.",
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n기록: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
