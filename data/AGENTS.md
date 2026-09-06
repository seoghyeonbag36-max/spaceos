# AGENTS.md — data (수집 · 파이프라인 · Bronze/Silver/Gold)

루트 [AGENTS.md](../AGENTS.md) 를 먼저 읽는다. 이 문서는 이 디렉터리에만 더 얹는 규칙이다.

## 구조

```
collectors/   외부 소스 수집 (건축HUB · R-ONE · 생활인구 · 인허가 · 네이버 · 카카오)
pipelines/    Bronze → Silver → Gold 빌더
config/       거점·상권 정의 — page_hubs.py 의 ACTIVE_HUBS 가 서빙 목록의 단일 출처
validation/   소스 승격 판정
tests/        pytest
bronze/ silver/ gold/    데이터 레이어 (대부분 .gitignore)
```

## 3계층을 건너뛰지 않는다

소비층(API·ML)은 **Gold 만 읽는다.** 순서를 어기면 결손이 조용히 영구화된다 — 앞 단계가
덜 찬 채로 뒤를 돌리면 그 결손이 "이미 받은 날짜"로 캐시된다.

**알려진 순서 의존:**
- `build_district_zones` 는 `build_page_master` **뒤에** (그 산출물을 읽는다)
- `build_program_trend` · `build_program_demand` 는 `build_gold` **뒤에** —
  셋 다 `gold/{slug}/program_content_context.csv` 를 쓰는데 `build_gold` 는 통째로
  덮어쓰고 나머지 둘은 행을 덧붙인다. 순서가 뒤집히면 트렌드·수요 행이 조용히 사라진다
- `refresh_platform` 은 `config/platform_districts.py` 의 `QUARTERS` 에 새 분기를 넣은 **뒤에**

## 거점 수를 세는 법

서빙 목록은 `config/page_hubs.py` 의 `ACTIVE_HUBS` 다.
**`gold/*/coverage.json` 을 세지 말 것** — 서빙 목록 밖(경기 보류) 산출물이 섞여 다른 값이 나온다.

## Gold 를 런타임에 읽으면 .gitignore 예외가 필요하다

안 넣으면 로컬은 되고 **프로덕션만 조용히 폴백**한다. 확인은 출력이 아니라 **종료코드**로:

```bash
git check-ignore <path>; echo $?     # 0 이면 무시되는 중 = 배포 안 됨
git check-ignore -v --no-index <path>  # 규칙 자체를 검증할 때
```

`check-ignore` 는 **이미 추적 중인 파일을 무시 대상으로 보고하지 않는다.** 그래서 앞 명령은
"지금 배포되는가"에는 답해도 "규칙이 실제로 적용되는가"에는 답하지 않는다 — 이 차이가
garosugil 전체 예외가 `data/gold/*/*` 에 덮여 죽은 것을 2026-08-15 까지 가렸다.

## 수집 금지선

- **기존 Gold 산출물을 덮어쓰지 않는다.** 재실행은 안전하지만 무료가 아니다 —
  수집기는 산출물이 있으면 건너뛰고, `--force` 는 쿼터를 다시 태운다
- 값이 비어 있으면 시드로 채우지 말고 **빈 상태를 보존하고 보고한다**(루트 §0)
- 대장 수집은 **AC 전원 필수** — 배터리 구동 시 약 7배 느려지고 덮개를 닫으면 절전으로 멈춘다
- 로그를 파일로 리다이렉트할 때 **`PYTHONIOENCODING=utf-8`** — Windows 기본 cp949 에는
  `—`(em dash) 가 없어 스크립트가 UnicodeEncodeError 로 죽는다

## 테스트

```powershell
python -m pytest data/tests
python -m pytest data/tests -k <이름>
```
