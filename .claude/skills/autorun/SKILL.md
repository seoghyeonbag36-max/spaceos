---
name: autorun
description: 사람이 자리에 없는 동안 장시간 작업을 무인으로 돌리는 규칙 — 절전·인코딩·감시·체크포인트·기록. 대장 수집, GNN/LSTM 학습, 전체 검증처럼 몇 시간짜리 작업을 걸어둘 때.
---

# 무인 실행 — 자리를 비운 채 몇 시간을 돌린다

이 프로젝트의 장시간 작업은 셋이다: **건축HUB 대장 수집**(쿼터 소진까지), **GNN/LSTM
학습**, **전체 검증**. 셋 다 사람이 지켜볼 필요가 없지만, 지켜보지 않으면 조용히 죽는
방식이 각각 다르다.

## 1. 재우지 않는다

이 노트북은 **Modern Standby(S0)** 라 전원 설정만으로는 안 잔다고 보장하지 못한다.
앱·드라이버가 유휴로 판정하면 대기로 들어간다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/keep_awake.ps1 -Command "python -u -m ml.training.train_gnn --epochs 600"
```

- 감싸서 실행하면 명령이 끝날 때 자동으로 놓아준다(권장).
- 화면은 붙잡지 않는다 — 덮개를 닫는 것이 목적이다.
- **배터리로는 여전히 느리다.** 대장 수집은 AC 전원에서 약 7배 빠르다. 병목은 CPU 가
  아니라 무선 어댑터 절전(AC 0 / DC 2)이고, 이 작업은 네트워크 바운드라 정확히 거기서 아프다.
- 덮개를 닫고 할 수 있는 작업만 고른다. GUI 가 필요한 자리는 `git push`(GCM 인증창)·
  브라우저 검증·외부 로그인 셋뿐이다.

## 2. 인코딩을 고정한다

```bash
OMP_NUM_THREADS=1 PYTHONIOENCODING=utf-8 python -u -m ml.training.train_gnn --epochs 600 --patience 80
```

Windows 기본 cp949 에는 `—`(em dash)가 없어 **로그를 파일로 리다이렉트하는 순간**
UnicodeEncodeError 로 죽는다(2026-08-19 실측). `-u` 로 버퍼링도 끈다 — 안 그러면
로그가 안 나와서 살아 있는지 알 수 없다.

## 3. 감시한다 — 죽음을 봤으면 로그를 다시 읽는다

```bash
python scripts/watch_collection.py --log data/logs/bldgvac.log --mode bldgvac --expect ikseon,euljiro,hongdae
```

`watch_collection.py` 의 핵심은 **drain-then-check** 다. 프로세스 사망을 감지하면
로그를 **다시 읽어** 남은 완료 이벤트를 처리한 뒤에 실패를 선언한다. 낡은 스냅샷으로
실패를 선언하면 정상 완주를 사망으로 오판한다(2026-07-26 songridan — 446/446동 exit=0
을 "미완료 사망"으로 읽었다).

## 4. 고치지 않는다 — 기록만 한다

```bash
python scripts/run_full_verify.py     # reports/full_verify.json + reports/logs/verify_*.log
```

자리에 없는 사이에 자동으로 고치기 시작하면 **무엇이 왜 바뀌었는지 아무도 모른다.**
무인 실행은 판단이 안 들어가는 작업에만 건다. 실패는 기록하고 돌아왔을 때 사람이 읽는다.

## 4-B. 세션이 끝나면 백그라운드도 끝난다

**에이전트 세션 안에서 띄운 백그라운드 작업은 세션이 내려가면 같이 죽는다.**
2026-08-30 금촌 대장 수집이 그렇게 끊겼다 — 831동 중 300동에서 멈췄고, 로그가
**체크포인트 주기(6분)를 넘겨 11분째 조용한 것**으로 알아챘다. 죽었다는 통보는 없었다.

- 죽음을 알아채는 법: 마지막 체크포인트 시각 + 주기 vs 현재 시각. 프로세스 목록도 본다
  (`Get-CimInstance Win32_Process` 로 명령줄까지 확인 — 이름만 보면 MCP 서버와 섞인다).
- **손실은 체크포인트 단위까지만이다.** 수집기는 완료분을 건너뛰므로 그냥 다시 부르면
  이어받는다(금촌은 "기존완료 298"로 재개했다). `--force` 는 그 재개를 무효로 만든다.
- 몇 시간짜리를 자리 비운 채 돌릴 것이라면 **세션 밖에서** 띄운다 — 별도 터미널 +
  `keep_awake.ps1`. 세션 안 백그라운드는 "자리를 잠깐 비우는" 용도다.

## 5. 산출물로 재개한다

수집기·학습기는 이미 받은 것을 건너뛰거나 체크포인트에서 재개한다. 그래서 무인 실행은
**중단돼도 손해가 작다.** 다시 걸 때 `--force` 를 습관적으로 붙이지 않는다 — 쿼터를
다시 태운다.

## 6. 돌아와서 읽을 자리

- `reports/full_verify.json` · `reports/logs/`
- `python scripts/pppp_status.py` — 산출물을 세어 진행률을 낸다
- `data/gold/*/coverage.json` 의 `tier`

## 선례

`references/platform13-autorun-2026-08.md` — Platform 13거점 LSTM 학습 2시간 자율 런북.
**완주된 이력이라 그대로 다시 돌리지 않는다**(지금 실행하면 54거점 산출물을 13거점본으로
되돌릴 수 있다). 자율 실행의 단계 구성과 중단 규칙을 참고할 때만 읽는다.
