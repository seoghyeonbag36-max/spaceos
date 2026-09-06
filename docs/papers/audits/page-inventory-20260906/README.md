# Page 원천 스냅샷 인벤토리 실행 보고

**판정: 인벤토리 작성과 무결성 검증 완료. 연구 설계 G0는 부분 충족.** 현재 입력의 해시는 기록했으나 불변 보존 사본을 만들거나 과거 Gold 생성 입력을 입증한 것은 아니다. 전수 구조 감사·독립 판정·실험 재현은 아직 실행하지 않았다.

이 문서의 수량은 아래 manifest에서 산출한 인벤토리 결과다. 논문 본문용 실험 수치가 아니며 원고에 사용하려면 근거 인덱스에 별도 등재한다.

## 산출물과 조사 범위

- [manifest.json](manifest.json): 거점 목록·설정, 입력별 선택·병합 정책, 경로·해시·시점 확인 수준·Git 상태, 누락 목록, 코드·환경 정보.
- [inventory.csv](inventory.csv): 파일별 조회용 표. 원천 행이나 개별 점포 내용은 포함하지 않는다.
- [manifest.sha256](manifest.sha256): manifest 파일 자체의 바이트 해시.
- [생성기](../../build_page_audit_manifest.py): 입력은 읽기 전용으로 조사하고 새로운 실행 폴더에만 기록한다.

범위는 `ACTIVE_HUBS`의 Page 핵심 객체·층·서빙 자료 및 공유 R-ONE 공실 앵커 보조자료다. 유동·밀도 레이어 원천, Posting 비용 원천, 독립 현장 정답 및 저장소의 모든 데이터를 조사한 것은 아니다.

| 항목 | 확인 결과 | 분모·의미 |
|---|---:|---|
| 서빙 거점 | 66 | 실행 시점 레지스트리에서 직접 읽어 manifest에 저장 |
| 조사 파일 | 946 | 위 범위의 보존 스냅샷·중간 산출물·Gold·R-ONE 보조자료 |
| 파일 총 크기 | 5,052,145,111 bytes | 복사한 용량이 아니라 해시를 계산한 입력 크기의 합 |
| Bronze | 496 | 해당 원천들의 모든 보존 날짜별 파일 |
| Silver | 120 | `building_attrs.json`, `expos_units.json`의 존재 파일 |
| Gold | 330 | 거점별 핵심 산출물들의 존재 파일 |
| Git 추적 | 265 | 조사 파일 중 인덱스에서 추적되는 파일 |
| Git 비추적·ignore | 681 | Bronze 496, Silver 120, Gold 65 |
| 마스터·층 속성 보유 거점 | 각각 66 | `page_building_master.geojson`, `building_attrs.json` |
| 핵심 Bronze 파일 종류 모두 보유 | 54 | 지정한 원천 종류의 파일 존재 판정. 내용 완전성·시점 일치는 미검증 |
| 누락 자료군 | 24 | 인허가 원본 12 + Silver 전유부 보조자료 12. 24개 거점이 아님 |

## 누락과 입력 선택의 의미

다음 거점의 기대 경로에서 `licensing_biz.json` 및 `expos_units.json`을 찾지 못했다.

`bulgwang`, `cheonho`, `doksan`, `hwagok`, `kkachisan`, `miasageori`, `mokdong-yc`, `oryudong`, `sangbong`, `sanggye`, `suyu`, `yeonsinnae`.

인허가 원본의 부재는 해당 파일을 이용한 보강 경로를 현재 자료로 감사할 수 없다는 뜻이다. 영업 업소가 없다는 뜻이 아니다. `expos_units.json`은 보조자료로 조사했으며, 이것의 부재를 마스터나 `building_attrs.json` 부재로 취급하지 않는다. 미확인 값을 채우거나 집합건물 제외 규칙을 해제하지 않았다.

점포·폴리곤·인허가·R-ONE 원천은 현재 로더가 선택하는 날짜 폴더의 경로를 기록했다. 대장·층별개요는 전체 보존 스냅샷을 기록했다. 후자의 최신 파일만 선택하면 부분 수집 이전의 자료를 잃을 수 있기 때문이다. 행별 병합 결과와 원천의 실제 완전성은 다음 구조 감사에서 확인해야 한다.

manifest의 `current_rebuild_inputs`는 **지금 재실행하면 선택될 입력**이다. 기존 Gold가 그 입력으로 생성됐다는 뜻이 아니다. 과거 빌드 이력과 일치하는지는 모든 행에 미검증으로 표시했다. 관측 시점이 추출되지 않은 자료는 그대로 남겼고, 폴더명·파일 수정 시각을 관측일로 대체하지 않았다. R-ONE의 `quarter`는 원문 필드값으로 기록하되 독립 확인값으로 승격하지 않았다.

## 로컬·Git·클라우드 판정

로컬에서는 모든 거점의 Gold 마스터와 층 속성 파일을 확인했다. 따라서 해당 입력을 대상으로 읽기 전용 구조 검사를 시작할 수 있다. 일부 원천 연결은 누락 또는 시점 미확인으로 `not_evaluable`가 될 수 있다.

조사한 Bronze와 Silver는 모두 Git 비추적 상태다. **GitHub 저장소를 연결하는 것만으로 이 원천들이 클라우드에 전달되지는 않는다.** 별도 자료 제공이 있었는지는 이 세션에서 확인하지 않았으므로 실제 클라우드 접근 상태는 `not_checked`다. 추적되는 Gold 파일도 로컬 추적 사실만으로 특정 원격 브랜치에 같은 바이트가 있다는 것을 보증하지 않는다.

이번에 원천을 업로드하거나 `.gitignore`를 변경하지 않았다. 클라우드에서 원천 감사를 실행하려면 필요한 입력을 별도로 제공하고 동일 해시를 확인해야 한다. 현재 단계에서는 로컬 자료로 다음 구조 감사를 진행할 수 있다.

## 수행한 검수

| 검수 | 결과 | 실제 확인 범위 |
|---|---|---|
| `manifest_digest_matches` | PASS | 저장된 manifest 바이트와 동봉 SHA-256 비교 |
| `manifest_file_fingerprints_match` | PASS | 자료 946개와 포착한 코드·요구사항 164개의 바이트 재해시·크기 대조 |
| `manifest_selector_matches_loader` | PASS | 최신 선택을 실제 `latest_bronze`와 대조; 병합 입력은 전체 날짜별 경로와 대조 |
| `manifest_inventory_matches` | PASS | CSV와 JSON의 경로·해시 일치 및 중복 경로 없음 |
| `manifest_cohort_matches_registry` | PASS | manifest 거점 목록과 현재 `ACTIVE_HUBS` 일치 |
| `manifest_unknowns_preserved` | PASS | 불변 사본 미생성, 과거 계보 미검증, 클라우드 미확인 표시 유지 |

생성 중 파일 크기·수정 시각과 입력 경로 집합을 재확인했고 이후 바이트 해시를 다시 대조했다. 검증 시점 이후 파일 변경까지 방지하는 잠금은 아니다. 전체 환경 잠금·코드 스냅샷 복사도 수행하지 않았다. 새 실행에 들어가기 전에 manifest의 해시를 재확인해야 한다.

## 재실행과 다음 작업

저장소 루트의 `chore/*` 또는 `fix/*` 브랜치에서 아래 명령으로 새 실행을 만든다. 같은 run-id가 이미 있으면 덮어쓰지 않고 실패한다. 새 자료 포착에는 다른 run-id를 사용한다.

```powershell
python docs/papers/build_page_audit_manifest.py --run-id page-inventory-next
```

다음은 [감사 설계](../../page-data-quality-protocol.md)의 **B. 전수 구조 감사**다. 동결한 파일 경로를 읽고 원천→마스터→집계의 식별키·측정 단위·출처·제외 사유를 검사한다. API 재호출이나 Gold 재빌드는 필요하지 않으며, 검사에서 발견한 의심을 독립 확인 오류로 바로 바꾸지 않는다.

[전체 단계](../../research-roadmap.md)에서 후속 독립 표본 감사·영향·재현성 분석·근거 등재·절별 원고 작성으로 이어진다.
