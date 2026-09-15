# -*- coding: utf-8 -*-
"""GNN 라벨 어휘(`--label-level`) 불변식 — 2026-09-15 노드 소스 교체 후속.

왜 여기에 있나: `ml/` 에는 테스트 디렉터리가 없고, 저장소에서 돌려지는 pytest 진입점은
`data/tests` 와 `apps/backend/tests` 둘뿐이다(.github/workflows/ci.yml). torch 가 없는
환경(CI `data` 잡은 data/requirements.txt 만 설치한다)에서는 통째로 skip 된다.

무엇을 고정하나 — 어느 것도 그래프 데이터를 요구하지 않는다(합성 프레임으로 잰다):
  1. `group_mapped`(어휘 (b)안)가 미사상 노드를 **모집단에서 빼고**, 그 노드를 가리키는
     엣지를 같이 버린다. 안 버리면 id→행번호 사상이 NaN 을 만들어 **엉뚱한 노드끼리**
     메시지가 오간다.
  2. 필터 뒤 라벨에 '미분류' 클래스가 없다.
  3. 저장 게이트가 **허용 목록**으로 동작한다 — group·group_mapped 만 저장하고
     lcls·category2 는 끈다. 이 가드는 서빙 업종명(체크포인트 classes) 보호 장치다.
  4. `lcls`(어휘 (c)안)가 상가정보 대분류(category_group_src)를 라벨로 쓴다.
"""
from __future__ import annotations

import pytest

pytest.importorskip("pandas", reason="GNN 라벨 유틸은 pandas 프레임을 받는다")
pytest.importorskip("torch", reason="train_gnn 은 torch 를 임포트한다")

import pandas as pd  # noqa: E402
import torch  # noqa: E402

from ml.training import train_gnn as tg  # noqa: E402


# 합성 표본은 클래스당 MIN_CLASS_NODES(10) 이상이어야 한다 — 그보다 작으면 _labels 가
# 실제 동작대로 '기타'로 병합해 버려서, 재려는 것(어휘 선택)이 가려진다.
_PER_CLASS = 12

# (node_id 접두, category_group, category_group_src, category)
_SPEC = [
    ("food",  "음식점", "음식", "음식점 > 한식"),
    ("cafe",  "카페",   "음식", "음식점 > 카페"),
    ("phar",  "약국",   "소매", "의료 > 약국"),
    ("shop",  "",       "소매", "소매 > 의류"),      # 7종 미사상
    ("edu",   "",       "교육", "교육 > 학원"),      # 7종 미사상
]


def _nodes() -> pd.DataFrame:
    """7종 사상 3클래스 + 미사상 2종, 클래스당 12노드."""
    rows = []
    for prefix, grp, src, cat in _SPEC:
        for i in range(_PER_CLASS):
            rows.append({"node_id": f"sdsc:{prefix}{i}", "category_group": grp,
                         "category_group_src": src, "category": cat,
                         "district_id": "garosugil"})
    return pd.DataFrame(rows)


def _edges() -> pd.DataFrame:
    """네 경우를 모두 담는다 — 양끝 사상 / 한쪽 미사상 / 양끝 미사상."""
    return pd.DataFrame([
        {"src": "sdsc:food0", "dst": "sdsc:cafe0", "type": "spatial_knn"},
        {"src": "sdsc:cafe0", "dst": "sdsc:phar0", "type": "same_building"},
        {"src": "sdsc:phar0", "dst": "sdsc:shop0", "type": "spatial_knn"},
        {"src": "sdsc:shop0", "dst": "sdsc:edu0", "type": "spatial_knn"},
    ])


_MAPPED_N = 3 * _PER_CLASS
_UNMAPPED_N = 2 * _PER_CLASS


def test_group_mapped_drops_unmapped_nodes_and_their_edges():
    nodes, edges, dropped = tg._label_population(_nodes(), _edges(), "group_mapped")
    assert dropped == _UNMAPPED_N
    assert len(nodes) == _MAPPED_N
    assert nodes["category_group"].str.len().gt(0).all()
    # 양끝이 모두 남은 엣지만 살아남는다 — dangling 2개는 버려진다
    assert len(edges) == 2
    assert set(edges["src"]) | set(edges["dst"]) <= set(nodes["node_id"])
    # 행 순서가 곧 노드 인덱스다 — 재색인이 안 되면 _edge_index 가 어긋난다
    assert list(nodes.index) == list(range(_MAPPED_N))


def test_group_keeps_unmapped_as_a_class_group_mapped_does_not():
    """(a)안과 (b)안의 차이 — 미분류를 클래스로 받느냐, 모집단에서 빼느냐."""
    nodes = _nodes()
    y_a, classes_a = tg._labels(nodes, level="group")
    assert "미분류" in classes_a
    assert len(y_a) == len(nodes)

    kept, _, _ = tg._label_population(nodes, _edges(), "group_mapped")
    y_b, classes_b = tg._labels(kept, level="group_mapped")
    assert "미분류" not in classes_b
    assert len(y_b) == _MAPPED_N
    assert set(classes_b) <= set(tg_group_vocabulary())


def tg_group_vocabulary() -> set[str]:
    """서빙 7종 어휘 — data/config/store_taxonomy 의 CATEGORY_GROUPS 와 같아야 한다."""
    from data.config.store_taxonomy import CATEGORY_GROUPS
    return set(CATEGORY_GROUPS) | {"기타"}


def test_lcls_labels_come_from_store_taxonomy_top_level():
    y, classes = tg._labels(_nodes(), level="lcls")
    assert set(classes) == {"음식", "소매", "교육"}
    assert len(y) == _MAPPED_N + _UNMAPPED_N   # (c)안은 모집단을 자르지 않는다


def test_lcls_requires_the_source_column():
    """카카오 시절 노드 테이블(category_group_src 없음)로는 (c)안을 돌릴 수 없다."""
    old_nodes = _nodes().drop(columns=["category_group_src"])
    with pytest.raises(ValueError, match="category_group_src"):
        tg._labels(old_nodes, level="lcls")


def test_group_mapped_requires_mapped_labels():
    """category_group 이 통째로 빈 노드 테이블이면 (b)안은 돌지 않는다 — 조용히 빈
    그래프를 학습하는 것보다 멈추는 편이 낫다."""
    blank = _nodes().assign(category_group="")
    with pytest.raises(ValueError, match="category_group"):
        tg._label_population(blank, _edges(), "group_mapped")


def test_unknown_label_level_is_rejected():
    with pytest.raises(ValueError, match="label level"):
        tg._labels(_nodes(), level="scls")


def test_save_gate_is_an_allowlist_not_a_single_level():
    """서빙 어휘 보호 장치 — 없애지 말고 허용 목록으로 관리한다.

    group·group_mapped 는 **같은 7종 문자열**을 쓰므로 서빙 업종명이 바뀌지 않는다.
    lcls(대분류 10종)·category2 는 어휘가 달라 저장이 꺼져야 한다.
    """
    assert tg.SAVEABLE_LABEL_LEVELS == ("group", "group_mapped")
    for level in tg.LABEL_LEVELS:
        if level in ("lcls", "category2"):
            assert level not in tg.SAVEABLE_LABEL_LEVELS, (
                f"{level} 은 서빙 어휘와 문자열이 다르다 — 저장을 허용하면 "
                "/recommend-industry 응답의 업종명이 조용히 바뀐다")
    # 가드 자체가 소스에 남아 있는지 — 통째로 지워지면 이 테스트가 잡는다
    src = (tg.__file__ or "")
    with open(src, encoding="utf-8") as fh:
        body = fh.read()
    assert "label_level not in SAVEABLE_LABEL_LEVELS" in body
    assert "if save and class_weight:" in body


def test_edge_index_after_filtering_points_at_real_rows():
    """필터 뒤 엣지 인덱스가 실제 행을 가리키는지 — 이 테스트가 (b)안의 핵심 위험을 잡는다.

    노드를 빼고 엣지를 그대로 두면 `src.map(idx)` 가 NaN 을 만들고, 그 NaN 이 정수로
    캐스팅되면서 **엉뚱한 노드끼리** 메시지가 오간다(조용히 학습이 끝난다).
    """
    nodes, edges, _ = tg._label_population(_nodes(), _edges(), "group_mapped")
    ei = tg._edge_index(nodes, edges, keep=None)
    assert ei.shape[0] == 2
    assert ei.shape[1] == 2 * len(edges)          # 무방향 → 양방향 전개
    assert int(ei.min()) >= 0
    assert int(ei.max()) < len(nodes)             # 범위 밖 인덱스가 없다
    # 남은 두 엣지가 실제로 food0–cafe0, cafe0–phar0 인지 id 로 되짚는다
    ids = nodes["node_id"].to_numpy()
    pairs = {frozenset((ids[int(a)], ids[int(b)])) for a, b in zip(*ei.tolist())}
    assert pairs == {frozenset(("sdsc:food0", "sdsc:cafe0")),
                     frozenset(("sdsc:cafe0", "sdsc:phar0"))}


def test_edge_index_drops_dangling_endpoints_on_its_own():
    """모집단을 줄인 주체가 누구든 — _edge_index 자체가 dangling 을 버린다(이중 방어)."""
    nodes = _nodes().head(_PER_CLASS).reset_index(drop=True)   # food* 만 남긴다
    edges = _edges()                                           # cafe/phar/shop/edu 를 가리킨다
    ei = tg._edge_index(nodes, edges, keep=None)
    assert ei.shape[1] == 0        # 살아남는 엣지가 없다
    assert ei.dtype == torch.long  # 빈 엣지여도 dtype 이 흔들리면 모델이 못 받는다
