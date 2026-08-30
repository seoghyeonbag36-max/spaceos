---
name: probe-first
description: 문서·기억이 아니라 1콜 실측으로 판단하고 그 결과를 docs/finding-*.md 로 남기는 절차. "이 소스가 되는가 / 이 값이 맞는가"를 확정해야 할 때.
---

# 재고 나서 적는다

이 프로젝트의 주된 실패 양식은 **선언이 낡는 것**이다. `docs/spaceos-vibe-build-sequence.md`
는 Tier1 을 13, 그다음 22 로 적고 있었고 실제는 49였다. 그래서 규칙이 하나다 —
**산출물이 단일 기준이고, 문서는 그 기준을 인용만 한다.**

## 순서

1. **가장 싼 프로브를 고른다.** 고양·파주 확장 판정은 4지점 × 1콜로 끝났다
   (상가정보·V-World·R-ONE 전량). 확장을 위해 새로 짠 코드는 한 줄도 없었다 —
   기존 수집기를 그대로 호출했다.
2. **기존 수집기를 호출한다.** 새 코드를 짜서 재면 "그 코드가 맞나"가 다음 질문이 된다.
   ```bash
   python -c "from data.collectors.building_vacancy import fetch_stores, group_by_building; ..."
   python -c "from data.collectors import vworld_bldg as vw; vw._fetch(key, bbox)"
   ```
3. **수를 적는다.** 판정이 아니라 수를 적는다 — 점포 4,118 / 건물 110 / 건물당 37.4.
   판정은 그 수에서 나온다.
4. **대조군을 같이 잰다.** 서울 가로수길 4.0 이 없으면 37.4 가 큰 값인지 알 수 없다.
5. **남긴다.**
   - 실측 결과 → `docs/finding-<주제>-<날짜>.md`
   - 기계가 읽을 값 → `reports/*.json`
   - 판단이 바뀌면 → 해당 skill·`docs/feature-*.md` 의 근거 줄을 고친다

## 남길 때 지키는 것

- **날짜를 박는다.** `finding-expos-quota-2026-08-09.md` 처럼 파일명에 넣는다.
- **부록에 프로브 명령을 그대로 적는다.** 다음 사람이 다시 재서 반박할 수 있어야 한다.
- **선언 게이트에는 `evidence` 경로를 채운다**(`scripts/pppp_status.py`). 근거 없는 선언은
  낡아도 아무도 모른다.
- 이미 있는 것을 다시 수집 과제로 적지 않는다 — **먼저 센다**(사흘에 네 번 겪었다).

## 예시 (이 절차로 나온 것들)

| 문서 | 잰 것 | 바뀐 판단 |
|---|---|---|
| `finding-expos-quota-2026-08-09.md` | 전유부/표제부 콜 수 | 병목이 전유부임을 확정 |
| `finding-sequence-and-accuracy-2026-08-17.md` | 앵커 격차 전수 | Top-1 70% 게이트 폐기 |
| `plan-gyeonggi-expansion-2026-08-29.md` | 4지점 상가정보·R-ONE 276표본 | 고양·파주 착수 가능, 거점 수 상한 3 |
