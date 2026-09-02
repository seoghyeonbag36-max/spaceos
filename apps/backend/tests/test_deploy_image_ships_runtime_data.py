"""배포 이미지가 **서빙이 런타임에 읽는 것**을 전부 싣는가.

## 왜 필요한가 — 2026-09-02 실측

프로덕션이 조용히 **54거점만** 서빙하고 있었다. 원인은 수집도 Gold 도 아니었다:

    Dockerfile 이 `apps/backend/` 와 `data/gold/` 만 COPY 하고 `data/config/` 를 뺐다.

`data/` 는 백엔드 패키지 밖이라 두 모듈이 **경로로** 읽는다:

    app/data/measured_pages.py     → data/config/page_hubs.py
    app/services/posting_inputs.py → data/config/rone_districts.py

둘 다 "파일이 없으면 빈 값으로 눕는" 폴백이라 아무 데도 안 터졌다. 결과:
서울 2차 12거점 + 경기 7거점이 화면에서 통째로 사라지고, `rone-shared`(앵커 공유)
라벨이 `rone` 으로 눕어 **공유 사실이 감춰졌다**. `posting_inputs._load_shared_rone`
의 독스트링은 이미 "Dockerfile 가드가 data/ 를 싣는지 함께 확인할 것"이라고 적고
있었는데, 그 가드가 없었다.

Dockerfile 에도 빌드 시점 가드를 넣었지만 그것만으로는 부족하다 — 이미지를 실제로
빌드해야 걸리므로 로컬·CI 에서 먼저 못 본다. 이 테스트는 **소스만 읽고** 판정한다.

## 무엇을 검사하는가

백엔드 소스가 `parents[N] / "data" / "<하위>"` 로 참조하는 하위 디렉터리를 전부 모아,
Dockerfile 이 각각을 COPY 하는지 본다. 새 하위 디렉터리를 읽기 시작했는데 COPY 를
안 더하면 여기서 걸린다 — 다음번을 막는 것이 이 파일의 목적이다.
"""
from __future__ import annotations

import re
from pathlib import Path

# tests/ → backend → apps → 저장소 루트
_REPO = Path(__file__).resolve().parents[3]
_BACKEND_APP = _REPO / "apps" / "backend" / "app"
_DOCKERFILE = _REPO / "Dockerfile"

# `parents[4] / "data" / "gold"` · `_REPO / "data" / "config" / "page_hubs.py"`
#
# ⚠ `parents[N]` 을 앵커로 쓰면 안 된다. measured_pages 는 `_REPO = ...parents[4]` 를
#   먼저 변수에 담고 `_REPO / "data" / "config"` 로 쓴다 — 앵커를 붙였다가 이 파일을
#   놓쳤고, 그러면 이 테스트가 정작 사고를 낸 자리를 못 본다. `"data" / "<하위>"`
#   자체를 찾는다(변수 이름이 무엇이든 걸린다).
_DATA_REF = re.compile(r'"data"\s*/\s*"([A-Za-z0-9_\-]+)"')
# `COPY data/gold/ ./data/gold/`
_COPY = re.compile(r'^COPY\s+data/([A-Za-z0-9_\-]+)/', re.MULTILINE)


def _referenced_subdirs() -> dict[str, set[str]]:
    """백엔드가 런타임에 읽는 `data/<하위>` → 그렇게 읽는 파일들."""
    out: dict[str, set[str]] = {}
    for py in _BACKEND_APP.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        for sub in _DATA_REF.findall(py.read_text(encoding="utf-8")):
            out.setdefault(sub, set()).add(str(py.relative_to(_REPO)).replace("\\", "/"))
    return out


def test_dockerfile_copies_every_data_dir_the_backend_reads():
    """서빙이 읽는 `data/<하위>` 는 전부 이미지에 실려야 한다.

    빠지면 **조용히** 눕는다(폴백이 예외를 안 낸다) — 그래서 화면이 멀쩡해 보이는 채로
    거점이 사라진다. 2026-09-02 에 `data/config` 가 정확히 그랬다.
    """
    referenced = _referenced_subdirs()
    assert referenced, "백엔드가 data/ 를 하나도 안 읽는다 — 패턴이 낡았는지 확인할 것"

    copied = set(_COPY.findall(_DOCKERFILE.read_text(encoding="utf-8")))
    missing = {sub: sorted(src) for sub, src in referenced.items() if sub not in copied}
    assert not missing, (
        "배포 이미지에 안 실리는 런타임 데이터가 있다 — Dockerfile 에 "
        f"`COPY data/<하위>/ ./data/<하위>/` 를 더할 것: {missing}")


def test_the_two_known_config_loaders_are_still_the_reason():
    """`data/config` 를 읽는 자리를 이름으로 고정한다.

    새로 생기면 여기서 걸린다 — 폴백으로 눕는 로더가 늘어나는 것 자체가 신호다.
    (늘어나도 괜찮다. 다만 그때 위 가드가 여전히 그것을 덮는지 사람이 한 번 본다.)
    """
    readers = _referenced_subdirs().get("config", set())
    assert readers == {
        "apps/backend/app/data/measured_pages.py",
        "apps/backend/app/services/posting_inputs.py",
    }, f"data/config 를 읽는 자리가 바뀌었다: {sorted(readers)}"


def test_config_loaders_are_not_silent_when_the_file_is_missing():
    """파일이 없을 때 **경고를 남겨야** 한다 — 조용한 폴백이 이 사고의 원인이었다.

    값을 비우는 것 자체는 맞다(예외를 내면 앱이 안 뜬다). 막아야 하는 것은 그 사실이
    아무 데도 안 남는 것이다.
    """
    for rel in ("app/data/measured_pages.py", "app/services/posting_inputs.py"):
        src = (_REPO / "apps" / "backend" / rel).read_text(encoding="utf-8")
        assert ".warning(" in src, f"{rel}: 파일 부재 폴백이 조용하다 — 경고를 남길 것"
