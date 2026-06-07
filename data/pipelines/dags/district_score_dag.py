"""서울 25구 거점 선정 점수 파이프라인 DAG (Airflow).

수집 3종(SNS/MAP/FOOT) 병렬 → Bronze 적재 → Silver(1~4점) → Gold(점수표/순위).
공실(VAC)은 별도 주기(분기)로 갱신되어 config base 또는 vacancy 수집기에서 결합.

스케줄: 주 1회(@weekly). SNS는 트렌드가 빨라 별도 일간 DAG로 분리 권장(TODO).
"""
from __future__ import annotations

from datetime import datetime

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:  # 골격 단계: airflow 미설치 허용
    DAG = None
    PythonOperator = None


def _collect_and_score(**_):
    """end-to-end: Bronze → Silver → Gold 점수표 저장."""
    from data.pipelines.district_score import build_gold, ingest_bronze, save_gold, transform_silver

    bronze = ingest_bronze()
    silver = transform_silver(bronze)
    rows = build_gold(silver)
    path = save_gold(rows)
    top = ", ".join(f"{r['name']}({r['total']})" for r in rows[:5])
    print(f"[district_score] Gold 저장 → {path} | Top5: {top}")
    return path


if DAG is not None:
    with DAG(
        dag_id="spaceos_seoul_district_score",
        description="서울 25구 SpaceOS 진입 우선순위 점수 산출 (4기준×2대상)",
        start_date=datetime(2026, 1, 1),
        schedule="@weekly",
        catchup=False,
        tags=["spaceos", "scoring", "commercial-district"],
    ) as dag:
        score = PythonOperator(task_id="collect_and_score", python_callable=_collect_and_score)
