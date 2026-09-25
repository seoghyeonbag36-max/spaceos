"""합의된 네 문서 검사. 제출 적격 여부는 자동 통과와 별도로 기록한다."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
import pymupdf as fitz
from build_package import PACKAGE_SPECS, DOCUMENTS

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
EXPECTED = {
    "00_README": ["제출 전", "검증"],
    "01_job_fit_analysis": ["채용 조건", "요구사항", "충족"],
    "02_evidence_and_contribution": ["구현 확인", "실행 확인", "기존 결과로만 확인", "향후 제안", "확인 불가", "본인 진술", "Codex"],
    "03_placeos_portfolio": ["본인 역할", "접근 방식", "구현", "확인 결과", "현재 한계", "조직 업무"],
    "04_technical_brief": ["시스템 구조", "데이터", "검증 상태"],
    "05_application_draft": ["지원동기", "직무역량", "문제해결", "입사 후 기여"],
    "06_project_experience_bullets": ["짧은 소개", "역할 중심", "상세 설명"],
    "07_interview_preparation": ["직접 한 일", "추천이 정확", "우리 업무", "Codex"],
    "08_graduate_research_plan": ["기술경영", "AI", "연구 질문", "기준", "평가", "누수", "추가 학습", "채용 제출물과 분리"],
    "09_final_review": ["주장", "분량", "개인정보", "제출 전"],
    "05a_korea_mot_application": ["지원동기", "직무역량", "문제해결 경험", "입사 후 기여", "희망연봉", "토요일"],
    "05b_yonsei_anchor_worksheet": ["300자", "성격 및 장단점", "성장배경", "AI", "작성 필요"],
    "05c_yonsei_uif_worksheet": ["협약·정산", "AI", "2026-09-27", "작성 필요"],
}

def main() -> None:
    results = {}
    errors = []
    texts = {}
    for name, sections in EXPECTED.items():
        p = BASE / f"{name}.md"
        if not p.exists():
            errors.append(f"파일 부재: {name}")
            continue
        t = p.read_text(encoding="utf-8")
        texts[p.name] = t
        for section in sections:
            if section not in t:
                errors.append(f"절 누락: {name}/{section}")
    qa = json.loads((BASE/"internal/pdf_qa.json").read_text(encoding="utf-8"))
    for name in DOCUMENTS:
        row = qa.get(name, {})
        if row.get("visual_review") != "전체 페이지 렌더링 육안 확인 완료":
            errors.append(f"PDF 육안 확인 미완료: {name}")
        path = BASE/"pdf"/f"{name}.pdf"
        if row.get("pdf_sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            errors.append(f"PDF 검토 후 파일 변경: {name}")
        for page in row.get("checks", []):
            if page["replacement_character"] or page["outside_safe_bounds"] or not page["characters"]:
                errors.append(f"PDF 렌더링 이상: {name}/{page['page']}")
    results["문서 필수항목 검사"] = {"passed": not errors, "errors": errors}

    errors = []
    audit = json.loads((BASE/"internal/repository_audit.json").read_text(encoding="utf-8"))
    evidence = texts["02_evidence_and_contribution.md"]
    for eid, source in audit["sources"].items():
        p = ROOT / source["path"]
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != source["sha256"]:
            errors.append(f"근거 변경·부재: {eid}")
        if not source["symbol_present"]:
            errors.append(f"기호 부재: {eid}")
        if eid not in evidence:
            errors.append(f"근거표 누락: {eid}")
    if audit["tests"]["exit_code"] != 0 or audit["heatmap_consistency_failures"]:
        errors.append("저장소 확인 실패")
    for name in ["04_technical_brief.md", "08_graduate_research_plan.md"]:
        t = texts[name]
        if f'{audit["active_hubs"]}개 거점' not in t or f'{audit["timeseries"]["rows"]:,}행' not in t:
            errors.append(f"집계 수치 불일치: {name}")
    for name in ["03_placeos_portfolio.md", "05_application_draft.md", "06_project_experience_bullets.md"]:
        if "150시간" not in texts[name] or not any(w in texts[name] for w in ["본인 진술", "본인 추정", "제 추정"]):
            errors.append(f"자기보고 시간 출처 누락: {name}")
    job_sources = json.loads((BASE/"internal/job_sources.json").read_text(encoding="utf-8"))
    fit = texts["01_job_fit_analysis.md"]
    for jid in ["J01", "J02", "J03", "J04", "J05"]:
        if jid not in job_sources or jid not in fit:
            errors.append(f"채용 출처 누락: {jid}")
    for term in ["2026-09-27", "2026-09-30", "300자", "AI", "행사·서무", "협약·정산"]:
        if term not in fit:
            errors.append(f"공고 확인 항목 누락: {term}")
    if "토요일" not in texts["08_graduate_research_plan.md"] or "충돌" not in texts["08_graduate_research_plan.md"]:
        errors.append("근무·학업 충돌 검토 누락")
    results["주장별 근거 검사"] = {"passed": not errors, "errors": errors,
        "scope": "등록 근거 파일·기호·해시, 로컬 집계 수치, 사용자 진술 표기 확인. 자연어 전체의 참과 개인 이력은 별도 확인."}

    patterns = {
        "email": r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+",
        "phone": r"(?<!\d)01[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)",
        "resident_id": r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)",
        "private_key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        "api_token": r"\b(?:sk-[A-Za-z0-9_-]{18,}|ghp_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b",
        "local_user_path": r"[A-Za-z]:[\\/]Users[\\/][^\s/\\]+",
        "credentials_url": r"\b\w+://[^/\s:]+:[^/\s@]+@",
    }
    errors = []
    scan = dict(texts)
    for p in (BASE/"pdf").glob("*.pdf"):
        doc = fitz.open(p)
        scan["pdf/"+p.name] = "\n".join(page.get_text() for page in doc) + json.dumps(doc.metadata)
    for p in (BASE/"internal").iterdir():
        if p.suffix in {".json", ".txt"}:
            scan["internal/"+p.name] = p.read_text(encoding="utf-8")
    for rel,t in scan.items():
        for label,pattern in patterns.items():
            if re.search(pattern,t):
                errors.append(f"{rel}: {label}")
    results["개인정보·비밀정보 검사"] = {"passed": not errors, "errors": errors,
        "scope": "생성 Markdown 및 PDF 본문·메타데이터의 정형 패턴 검사. 미탐 가능성을 고려해 수동 검토 병행."}

    specs = PACKAGE_SPECS
    errors = []
    listings = {}
    for name,names in specs.items():
        if "research" not in name and "08_graduate_research_plan" in names:
            errors.append(f"채용 ZIP에 연구계획 포함: {name}")
        if "yonsei" in name and any(not doc.endswith("worksheet") for doc in names):
            errors.append(f"연세대 전용 ZIP에 작성표 외 자료 포함: {name}")
        allowed = {"00_README.md", "manifest.json"}
        allowed |= {f"{n}.md" for n in names} | {f"pdf/{n}.pdf" for n in names}
        with zipfile.ZipFile(BASE/"release"/f"{name}.zip") as z:
            listings[name] = z.namelist()
            if set(z.namelist()) != allowed or len(z.namelist()) != len(allowed):
                errors.append(f"허용 목록 불일치: {name}")
            if z.testzip() is not None:
                errors.append(f"압축 손상: {name}")
            manifest = json.loads(z.read("manifest.json"))
            if {row["path"] for row in manifest} != allowed - {"manifest.json"}:
                errors.append(f"manifest 목록 불일치: {name}")
            for row in manifest:
                if hashlib.sha256(z.read(row["path"])).hexdigest() != row["sha256"]:
                    errors.append(f"해시 불일치: {name}/{row['path']}")
                if row["path"].endswith((".md", ".pdf")) and row["path"] != "00_README.md":
                    if z.read(row["path"]) != (BASE/row["path"]).read_bytes():
                        errors.append(f"원본/ZIP 불일치: {name}/{row['path']}")
            if "개인 검토용" not in z.read("00_README.md").decode() and "career" in name:
                errors.append("채용 ZIP 안내 누락")
    results["ZIP 구성 검사"] = {"passed": not errors, "errors": errors, "members": listings}
    application = texts["05a_korea_mot_application.md"]
    lengths = {}
    for title in ["지원동기", "직무역량", "문제해결 경험", "입사 후 기여"]:
        match = re.search(r"^## "+re.escape(title)+r"\n(.*?)(?=^## |\Z)", application, re.M|re.S)
        body = re.sub(r"<!--.*?-->","",match.group(1),flags=re.S).strip()
        lengths[title] = {"including_whitespace":len(body), "excluding_whitespace":len(re.sub(r"\s", "",body)),
                          "official_limit":None, "note":"자리표시자 포함, 최종 입력 시스템의 계산 방식 미확인"}
    lengths = {"korea_mot": lengths, "yonsei_anchor": {"official_questions": 5, "official_limit": "각 300자 내외",
        "answers_written": False, "compliance": "미작성으로 판정 불가", "reason": "AI 금지 공지 적용 범위 확인 필요"},
        "yonsei_uif": {"official_questions": None, "official_limit": None, "answers_written": False,
        "compliance": "미확인", "reason": "전형 AI 사용 금지, 본인 작성 필요"}}
    (BASE/"internal/application_lengths.json").write_text(json.dumps(lengths,ensure_ascii=False,indent=2),encoding="utf-8")
    results["submission_ready"] = False
    results["remaining"] = ["고려대 공식 제출방식·문항·분량", "연세대 AI 제한과 앵커사업단 적용 범위", "지원자 요건 충족과 세부 기여", "자리표시자 교체·포트폴리오 허용"]
    (BASE/"internal/document_checks.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v["passed"] for k,v in results.items() if isinstance(v,dict) and "passed" in v},ensure_ascii=False))
    all_pass = all(v["passed"] for v in results.values() if isinstance(v,dict) and "passed" in v)
    if not all_pass:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
