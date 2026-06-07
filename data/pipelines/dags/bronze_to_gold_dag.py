"""SpaceOS 데이터 레이크 ETL DAG (Airflow 골격).

Bronze(원본) → Silver(정제) → Gold(분석/학습용) 3계층 파이프라인.
거점 상권: 라페스타·웨스턴돔 → 성수동 → 용봉동.
"""
from __future__ import annotations

from datetime import datetime

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
except ImportError:  # 골격 단계 미설치 허용
    DAG = None
    PythonOperator = None


def ingest_bronze(**_):
    """크롤링/공공API 원본 수집 → S3 Bronze 적재 (TODO)."""
    print("[bronze] ingest raw: 공실/리뷰/유동인구/사업자 이력")


def transform_silver(**_):
    """결측치·중복 처리, 주소 정규화, Parquet 변환 (TODO)."""
    print("[silver] clean & normalize → Parquet")


def build_gold(**_):
    """피처 엔지니어링 → PostgreSQL/PostGIS 적재 (TODO)."""
    print("[gold] feature engineering → PostGIS")


if DAG is not None:
    with DAG(
        dag_id="spaceos_bronze_to_gold",
        start_date=datetime(2026, 1, 1),
        schedule="@weekly",
        catchup=False,
        tags=["spaceos", "etl"],
    ) as dag:
        t1 = PythonOperator(task_id="ingest_bronze", python_callable=ingest_bronze)
        t2 = PythonOperator(task_id="transform_silver", python_callable=transform_silver)
        t3 = PythonOperator(task_id="build_gold", python_callable=build_gold)
        t1 >> t2 >> t3
