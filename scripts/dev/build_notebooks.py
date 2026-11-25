#!/usr/bin/env python3
"""Generate the Lab V4 Fabric notebooks from readable cell sources.

Two kinds of notebooks are produced:

* provided graders (read-only validators) -> notebooks/
* answer keys for the notebooks that participants generate with GitHub Copilot
  from notebooks/specs/*.md -> reference/notebooks/ (used by `--reference`)

Edit this file, run `python3 scripts/dev/build_notebooks.py`, and commit both
this file and the generated notebooks. tests/validate_repo.py fails when the
committed notebooks drift from this generator.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "notebooks"
REFERENCE_OUT = ROOT / "reference" / "notebooks"
GENERATED = {"nb_02_prepare_trips", "nb_03_prepare_dimensions", "nb_07_prepare_ontology", "nb_08_create_agents"}

RESULT_HELPER = '''import json
from datetime import datetime, timezone

def save_result(name, payload):
    """Persist a run summary that scripts/lab.py reads back from OneLake."""
    payload = {"notebook": name, "finishedAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}
    notebookutils.fs.put(f"Files/lab_results/{name}.json", json.dumps(payload, ensure_ascii=False, default=str), True)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

checks = []

def check(name, expected, actual, tolerance=None):
    if tolerance is None:
        passed = expected == actual
    else:
        passed = actual is not None and abs(float(expected) - float(actual)) <= tolerance
    checks.append({"check": name, "expected": expected, "actual": actual, "passed": bool(passed)})
'''


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": _lines(text)}


def _lines(text: str) -> list[str]:
    lines = text.strip("\n").split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


def notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernel_info": {"name": "synapse_pyspark"},
            "kernelspec": {"display_name": "Synapse PySpark", "language": "Python", "name": "synapse_pyspark"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


NOTEBOOKS: dict[str, list[dict]] = {}

NOTEBOOKS["nb_02_prepare_trips"] = [
    md("""# Lab 02 — 乗車データの取り込みと加工

`Files/raw` の Parquet を読み込み、クレンジングと派生列の追加を行って Delta テーブル `green_tripdata_2026` に保存します。

- 元ファイルは変更しません。書き込むのは `green_tripdata_2026` だけです。
- 重複排除や、乗客数が欠損した行以外の行削除はしません。
- `trip_id` は欠損のない 8 列で並べた連番です。再実行しても同じ値になります。"""),
    code(RESULT_HELPER),
    code('''from pyspark.sql import Window
from pyspark.sql import functions as F

spark.conf.set("spark.sql.session.timeZone", "UTC")
SOURCE = "Files/raw/green_tripdata_2026-04.parquet"
TABLE = "green_tripdata_2026"

raw = spark.read.parquet(SOURCE)
source_rows, source_columns = raw.count(), len(raw.columns)
print(f"Source: {source_rows:,} rows / {source_columns} columns")'''),
    md("""## 加工ルール

| 列 | ルール |
|---|---|
| `ehail_fee` | 削除 |
| `passenger_count` | null の行だけを除外 |
| 日時 2 列 | タイムゾーンを持たない値を UTC の timestamp として保存（SQL エンドポイントで日時を扱えるようにする） |
| `pickup_date` / `pickup_hour` / `pickup_month` | 乗車日時から日付・0〜23 時・`yyyy-MM` |
| `trip_duration_minutes` | 降車 − 乗車（分、小数 2 桁）。欠損または負の値は null |
| `fare_per_mile` | `fare_amount / trip_distance`（小数 2 桁）。距離が 0 以下・欠損なら null |
| `passenger_group` | 1 人 = `single`、2 人以上 = `group`、0 以下 = `unknown` |
| `trip_id` | 乗車・降車日時、VendorID、乗降地、距離、運賃、合計金額の順に並べた連番 |"""),
    code('''ORDER_COLUMNS = ["lpep_pickup_datetime", "lpep_dropoff_datetime", "VendorID", "PULocationID",
                 "DOLocationID", "trip_distance", "fare_amount", "total_amount"]

df = (
    raw.drop("ehail_fee")
    .filter(F.col("passenger_count").isNotNull())
    .withColumn("lpep_pickup_datetime", F.col("lpep_pickup_datetime").cast("timestamp"))
    .withColumn("lpep_dropoff_datetime", F.col("lpep_dropoff_datetime").cast("timestamp"))
)
null_order_values = df.select([F.sum(F.col(c).isNull().cast("int")).alias(c) for c in ORDER_COLUMNS]).first().asDict()
if any(null_order_values.values()):
    raise ValueError(f"trip_id の並び替え列に欠損があります: {null_order_values}")

seconds = F.col("lpep_dropoff_datetime").cast("long") - F.col("lpep_pickup_datetime").cast("long")
df = (
    df.withColumn("trip_id", F.row_number().over(Window.orderBy(*ORDER_COLUMNS)).cast("long"))
    .withColumn("pickup_date", F.to_date("lpep_pickup_datetime"))
    .withColumn("pickup_hour", F.hour("lpep_pickup_datetime"))
    .withColumn("pickup_month", F.date_format("lpep_pickup_datetime", "yyyy-MM"))
    .withColumn("trip_duration_minutes", F.when(seconds >= 0, F.round(seconds / 60.0, 2)))
    .withColumn("fare_per_mile", F.when((F.col("trip_distance") > 0) & F.col("fare_amount").isNotNull(),
                                        F.round(F.col("fare_amount") / F.col("trip_distance"), 2)))
    .withColumn("passenger_group", F.when(F.col("passenger_count") == 1, "single")
                .when(F.col("passenger_count") >= 2, "group").otherwise("unknown"))
)
df = df.select("trip_id", *[c for c in df.columns if c != "trip_id"])'''),
    code('''df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(TABLE)

saved = spark.table(TABLE)
saved_rows = saved.count()
save_result("nb_02_prepare_trips", {
    "source": {"path": SOURCE, "rows": source_rows, "columns": source_columns},
    "removedNullPassengerCount": source_rows - saved_rows,
    "droppedColumns": ["ehail_fee"],
    "addedColumns": ["trip_id", "pickup_date", "pickup_hour", "pickup_month", "trip_duration_minutes", "fare_per_mile", "passenger_group"],
    "saved": {"table": TABLE, "rows": saved_rows, "columns": len(saved.columns)},
    "next": "答え合わせは nb_02_validate_trips で実行します。",
})'''),
]

NOTEBOOKS["nb_02_validate_trips"] = [
    md("""# Lab 02 — 加工結果の検証（読み取り専用）

保存済みの `green_tripdata_2026` を読み直し、全件の品質、加工ルール、固定レコード、集計を期待値と照合します。
**データは変更しません。** 不一致があっても修正せず、差分を報告します。"""),
    code(RESULT_HELPER),
    code('''from pyspark.sql import functions as F

spark.conf.set("spark.sql.session.timeZone", "UTC")
raw = spark.read.parquet("Files/raw/green_tripdata_2026-04.parquet")
trips = spark.table("green_tripdata_2026")

check("source rows", 44238, raw.count())
check("source columns", 21, len(raw.columns))
check("saved rows", 37948, trips.count())
check("saved columns", 27, len(trips.columns))
check("ehail_fee removed", False, "ehail_fee" in trips.columns)
check("trip_id unique 1..37948", [37948, 1, 37948],
      list(trips.agg(F.countDistinct("trip_id"), F.min("trip_id"), F.max("trip_id")).first()))

quality = trips.agg(
    F.sum(F.col("passenger_count").isNull().cast("int")).alias("null_passenger"),
    F.sum((~F.col("pickup_hour").between(0, 23) | F.col("pickup_hour").isNull()).cast("int")).alias("bad_hour"),
    F.sum((F.col("pickup_month") != "2026-04").cast("int")).alias("other_month"),
    F.round(F.sum("total_amount"), 2).alias("total_amount"),
    F.round(F.avg("fare_amount"), 2).alias("avg_fare"),
).first()
check("passenger_count nulls", 0, quality.null_passenger)
check("pickup_hour out of range", 0, quality.bad_hour)
check("pickup_month other than 2026-04", 0, quality.other_month)
check("total_amount sum", 687602.60, float(quality.total_amount), 0.005)
check("average fare", 11.92, float(quality.avg_fare), 0.005)'''),
    md("## 派生列の計算ルールを全件で照合"),
    code('''seconds = F.col("lpep_dropoff_datetime").cast("long") - F.col("lpep_pickup_datetime").cast("long")
recomputed = trips.select(
    (F.col("pickup_date") != F.to_date("lpep_pickup_datetime")).alias("date"),
    (F.col("pickup_hour") != F.hour("lpep_pickup_datetime")).alias("hour"),
    (~F.col("trip_duration_minutes").eqNullSafe(F.when(seconds >= 0, F.round(seconds / 60.0, 2)))).alias("duration"),
    (~F.col("fare_per_mile").eqNullSafe(F.when(F.col("trip_distance") > 0, F.round(F.col("fare_amount") / F.col("trip_distance"), 2)))).alias("fare_per_mile"),
    (F.col("passenger_group") != F.when(F.col("passenger_count") == 1, "single")
        .when(F.col("passenger_count") >= 2, "group").otherwise("unknown")).alias("group"),
)
mismatches = recomputed.agg(*[F.sum(F.col(c).cast("int")).alias(c) for c in recomputed.columns]).first().asDict()
for column, count in mismatches.items():
    check(f"derived column rule: {column}", 0, count or 0)'''),
    md("## 固定レコード（WHERE 条件で特定し、各条件の該当件数も確認）"),
    code('''EXPECTED = {
    1: dict(VendorID=2, PULocationID=243, DOLocationID=108, passenger_count=5, trip_distance=6.64, fare_amount=23.07,
            total_amount=35.41, trip_duration_minutes=34.0, fare_per_mile=3.47, passenger_group="group",
            pickup="2026-04-01 00:00:02", dropoff="2026-04-01 00:34:02"),
    4: dict(VendorID=1, PULocationID=206, DOLocationID=89, passenger_count=1, trip_distance=5.94, fare_amount=15.83,
            total_amount=19.38, trip_duration_minutes=36.0, fare_per_mile=2.66, passenger_group="single",
            pickup="2026-04-01 00:01:51", dropoff="2026-04-01 00:37:51"),
}
fixed = (
    trips.filter((F.col("pickup_date") == F.lit("2026-04-01").cast("date")) & (F.col("pickup_hour") == 0) & (
        ((F.col("VendorID") == 1) & (F.col("PULocationID") == 206) & (F.col("DOLocationID") == 89))
        | ((F.col("VendorID") == 2) & (F.col("PULocationID") == 243) & (F.col("DOLocationID") == 108))))
    .withColumn("pickup", F.date_format("lpep_pickup_datetime", "yyyy-MM-dd HH:mm:ss"))
    .withColumn("dropoff", F.date_format("lpep_dropoff_datetime", "yyyy-MM-dd HH:mm:ss"))
    .orderBy("trip_id")
)
rows = {row.trip_id: row.asDict() for row in fixed.collect()}
check("fixed records found (trip_id)", sorted(EXPECTED), sorted(rows))
for trip_id, expected in EXPECTED.items():
    actual = rows.get(trip_id, {})
    check(f"trip {trip_id}", expected, {key: actual.get(key) for key in expected})
fixed.select("trip_id", "VendorID", "PULocationID", "DOLocationID", "pickup", "dropoff", "passenger_count",
             "trip_distance", "fare_amount", "trip_duration_minutes", "fare_per_mile", "passenger_group").show(truncate=False)'''),
    md("## 集計（全件から計算）"),
    code('''groups = {r.passenger_group: r["count"] for r in trips.groupBy("passenger_group").count().collect()}
check("passenger_group counts", {"group": 31691, "single": 6257}, groups)
check("passenger_group total", 37948, sum(groups.values()))
hours = trips.groupBy("pickup_hour").agg(F.count("*").alias("trips"), F.round(F.avg("fare_amount"), 2).alias("avg_fare"))
check("hourly total", 37948, hours.agg(F.sum("trips")).first()[0])
hour0 = hours.filter("pickup_hour = 0").first()
check("hour 0", {"trips": 1615, "avg_fare": 11.94}, {"trips": hour0.trips, "avg_fare": float(hour0.avg_fare)})

failed = [c for c in checks if not c["passed"]]
save_result("nb_02_validate_trips", {"passed": not failed, "failed": len(failed), "checks": checks})'''),
]

NOTEBOOKS["nb_03_prepare_dimensions"] = [
    md("""# Lab 03 — ゾーンとコードのマスターを整備

OneLake ショートカット `Files/taxi_zone` の CSV（共有 ADLS Gen2 上に残ったまま）を読み込み、
ゾーンマスター `taxi_zone_lookup` と、ベンダー・料金コード・支払方法・乗車種別のコード表を Delta に保存します。"""),
    code(RESULT_HELPER),
    code('''from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

ZONE_FILE = "Files/taxi_zone/Taxi_zone_lookup.csv"
zones = (
    spark.read.option("header", "true").csv(ZONE_FILE)
    .select(F.col("LocationID").cast("int").alias("LocationID"), F.trim("Borough").alias("Borough"),
            F.trim("Zone").alias("Zone"), F.trim("service_zone").alias("service_zone"))
)
zones.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("taxi_zone_lookup")

schema = StructType([StructField("code", IntegerType(), False), StructField("name", StringType(), False)])
LOOKUPS = {
    "vendor_lookup": ("VendorID", "vendor_name", [(1, "Creative Mobile Technologies, LLC"), (2, "VeriFone Inc.")]),
    "ratecode_lookup": ("RatecodeID", "ratecode_name", [(1, "Standard rate"), (2, "JFK"), (3, "Newark"),
                        (4, "Nassau or Westchester"), (5, "Negotiated fare"), (6, "Group ride")]),
    "payment_type_lookup": ("payment_type", "payment_type_name", [(1, "Credit card"), (2, "Cash"), (3, "No charge"),
                            (4, "Dispute"), (5, "Unknown"), (6, "Voided trip")]),
    "trip_type_lookup": ("trip_type", "trip_type_name", [(1, "Street-hail"), (2, "Dispatch")]),
}
saved = {"taxi_zone_lookup": spark.table("taxi_zone_lookup").count()}
for table, (key, label, rows) in LOOKUPS.items():
    (spark.createDataFrame(rows, schema).withColumnRenamed("code", key).withColumnRenamed("name", label)
     .write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table))
    saved[table] = spark.table(table).count()

save_result("nb_03_prepare_dimensions", {"source": ZONE_FILE, "savedTables": saved,
                                          "next": "答え合わせは nb_03_validate_dimensions で実行します。"})'''),
]

NOTEBOOKS["nb_03_validate_dimensions"] = [
    md("""# Lab 03 — マスターと結合の検証（読み取り専用）

ゾーンマスターのキー品質と、乗車・降車の 2 つの役割での結合結果を確認します。データは変更しません。"""),
    code(RESULT_HELPER),
    code('''from pyspark.sql import functions as F

zones = spark.table("taxi_zone_lookup")
trips = spark.table("green_tripdata_2026")
check("zone rows", 265, zones.count())
key_quality = zones.agg(F.countDistinct("LocationID").alias("distinct"),
                        F.sum(F.col("LocationID").isNull().cast("int")).alias("nulls")).first()
check("zone LocationID distinct", 265, key_quality.distinct)
check("zone LocationID nulls", 0, key_quality.nulls)
EXPECTED_ZONES = {1: ("EWR", "Newark Airport", "EWR"), 2: ("Queens", "Jamaica Bay", "Boro Zone"),
                  3: ("Bronx", "Allerton/Pelham Gardens", "Boro Zone"), 4: ("Manhattan", "Alphabet City", "Yellow Zone"),
                  5: ("Staten Island", "Arden Heights", "Boro Zone")}
fixed = {r.LocationID: (r.Borough, r.Zone, r.service_zone)
         for r in zones.filter(F.col("LocationID").isin(*EXPECTED_ZONES)).orderBy("LocationID").collect()}
check("fixed zones 1-5", {str(k): list(v) for k, v in EXPECTED_ZONES.items()}, {str(k): list(v) for k, v in fixed.items()})
for table, rows in {"vendor_lookup": 2, "ratecode_lookup": 6, "payment_type_lookup": 6, "trip_type_lookup": 2}.items():
    check(f"{table} rows", rows, spark.table(table).count())'''),
    md("## 乗車地・降車地の 2 つの役割で結合する"),
    code('''pickup = zones.select(F.col("LocationID").alias("PULocationID"), F.col("Borough").alias("pickup_borough"),
                      F.col("Zone").alias("pickup_zone"))
dropoff = zones.select(F.col("LocationID").alias("DOLocationID"), F.col("Borough").alias("dropoff_borough"),
                       F.col("Zone").alias("dropoff_zone"))
joined = trips.join(pickup, "PULocationID", "inner").join(dropoff, "DOLocationID", "inner")
check("joined rows (no loss, no duplication)", 37948, joined.count())

boroughs = {r.pickup_borough: r["count"] for r in joined.groupBy("pickup_borough").count().collect()}
MAIN = {"Queens": 9957, "Manhattan": 9937, "Brooklyn": 8702, "Bronx": 6151, "Staten Island": 2800, "EWR": 135}
check("pickup borough trips", MAIN, {k: boroughs.get(k) for k in MAIN})
check("pickup borough other (Unknown / N/A)", 266, sum(v for k, v in boroughs.items() if k not in MAIN))

mb = joined.filter((F.col("pickup_borough") == "Manhattan") & (F.col("dropoff_borough") == "Brooklyn"))
summary = mb.agg(F.count("*").alias("trips"), F.round(F.sum("total_amount"), 2).alias("amount")).first()
check("Manhattan -> Brooklyn trips", 2340, summary.trips)
check("Manhattan -> Brooklyn total_amount", 42944.85, float(summary.amount), 0.005)

fixed_trips = {r.trip_id: [r.pickup_zone, r.pickup_borough, r.dropoff_zone, r.dropoff_borough]
               for r in joined.filter(F.col("trip_id").isin(1, 4)).collect()}
check("fixed trip zones", {"1": ["Washington Heights North", "Manhattan", "Gravesend", "Brooklyn"],
                           "4": ["Saint George/New Brighton", "Staten Island", "Flatbush/Ditmas Park", "Brooklyn"]},
      {str(k): v for k, v in sorted(fixed_trips.items())})

failed = [c for c in checks if not c["passed"]]
save_result("nb_03_validate_dimensions", {"passed": not failed, "failed": len(failed), "checks": checks})'''),
]

NOTEBOOKS["nb_04_validate_warehouse"] = [
    md("""# Lab 04 — Warehouse の検証（読み取り専用）

T-SQL Notebook `nb_04_build_warehouse` が作成した Warehouse のテーブルを Spark コネクタで読み取り、
件数・キーの整合性・金額が Lakehouse の値と一致するか確認します。Warehouse は変更しません。"""),
    code(RESULT_HELPER),
    code('''import com.microsoft.spark.fabric
from com.microsoft.spark.fabric.Constants import Constants
from pyspark.sql import functions as F

def wh(table):
    return spark.read.synapsesql(f"taxi_warehouse.dbo.{table}")

EXPECTED_ROWS = {"fact_trips": 37948, "dim_vendor": 2, "dim_ratecode": 6, "dim_payment_type": 6,
                 "dim_trip_type": 2, "dim_pickup_zone": 265, "dim_dropoff_zone": 265}
tables = {name: wh(name).cache() for name in EXPECTED_ROWS}
for name, rows in EXPECTED_ROWS.items():
    check(f"{name} rows", rows, tables[name].count())

fact = tables["fact_trips"]
lakehouse_total = spark.table("green_tripdata_2026").agg(F.round(F.sum("total_amount"), 2)).first()[0]
check("total_amount equals Lakehouse", float(lakehouse_total), float(fact.agg(F.round(F.sum("total_amount"), 2)).first()[0]), 0.005)
check("pickup datetime kept (non-null)", 37948, fact.filter(F.col("lpep_pickup_datetime").isNotNull()).count())

for fact_key, dim, dim_key in [("VendorID", "dim_vendor", "VendorID"), ("RatecodeID", "dim_ratecode", "RatecodeID"),
                               ("payment_type", "dim_payment_type", "payment_type"), ("trip_type", "dim_trip_type", "trip_type"),
                               ("PULocationID", "dim_pickup_zone", "LocationID"), ("DOLocationID", "dim_dropoff_zone", "LocationID")]:
    orphans = fact.join(tables[dim], fact[fact_key] == tables[dim][dim_key], "left_anti").count()
    check(f"orphan keys {fact_key} -> {dim}", 0, orphans)
    duplicates = tables[dim].groupBy(dim_key).count().filter("count > 1").count()
    check(f"duplicate keys in {dim}", 0, duplicates)

mb = (fact.join(tables["dim_pickup_zone"], fact.PULocationID == tables["dim_pickup_zone"].LocationID)
          .join(tables["dim_dropoff_zone"], fact.DOLocationID == tables["dim_dropoff_zone"].LocationID)
          .filter((F.col("pickup_borough") == "Manhattan") & (F.col("dropoff_borough") == "Brooklyn")))
check("Manhattan -> Brooklyn trips", 2340, mb.count())

failed = [c for c in checks if not c["passed"]]
save_result("nb_04_validate_warehouse", {"passed": not failed, "failed": len(failed), "checks": checks})'''),
]

NOTEBOOKS["nb_07_prepare_ontology"] = [
    md("""# Lab 07 — Ontology 用のテーブルを整備

Ontology の各エンティティに対応するテーブルを、加工済みデータから作成します。

| エンティティ | テーブル | キー |
|---|---|---|
| Trip | `onto_trips` | `trip_id` |
| Zone | `onto_zones` | `LocationID` |
| Vendor | `onto_vendors` | `VendorID` |

`onto_trips` は 1 トリップ 1 行のまま、支払方法・乗車種別の名前を付けます。件数・金額は変えません。"""),
    code(RESULT_HELPER),
    code('''from pyspark.sql import functions as F

trips = spark.table("green_tripdata_2026")
onto_trips = (
    trips.join(spark.table("payment_type_lookup"), "payment_type", "left")
    .join(spark.table("trip_type_lookup"), "trip_type", "left")
    .select(
        F.col("trip_id").cast("long"), F.col("VendorID").cast("long"), F.col("PULocationID").cast("long"),
        F.col("DOLocationID").cast("long"), "lpep_pickup_datetime", F.col("pickup_date").cast("timestamp").alias("pickup_date"),
        F.col("pickup_hour").cast("long"), F.col("passenger_count").cast("long"), "passenger_group", "trip_distance",
        "trip_duration_minutes", "fare_amount", "tip_amount", "total_amount", "payment_type_name", "trip_type_name",
    )
)
onto_zones = spark.table("taxi_zone_lookup").select(F.col("LocationID").cast("long"), "Borough", "Zone", "service_zone")
onto_vendors = spark.table("vendor_lookup").select(F.col("VendorID").cast("long"), "vendor_name")

for name, frame in {"onto_trips": onto_trips, "onto_zones": onto_zones, "onto_vendors": onto_vendors}.items():
    frame.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(name)

for name, rows in {"onto_trips": 37948, "onto_zones": 265, "onto_vendors": 2}.items():
    check(f"{name} rows", rows, spark.table(name).count())
for name, column in {"onto_trips": "trip_id", "onto_zones": "LocationID", "onto_vendors": "VendorID"}.items():
    check(f"{name} key unique", spark.table(name).count(), spark.table(name).select(column).distinct().count())
check("onto_trips total_amount unchanged", float(trips.agg(F.round(F.sum("total_amount"), 2)).first()[0]),
      float(spark.table("onto_trips").agg(F.round(F.sum("total_amount"), 2)).first()[0]), 0.005)
check("onto_trips names resolved", 0, spark.table("onto_trips").filter(
    F.col("payment_type_name").isNull() | F.col("trip_type_name").isNull()).count())

failed = [c for c in checks if not c["passed"]]
save_result("nb_07_prepare_ontology", {"passed": not failed, "failed": len(failed), "checks": checks})'''),
]

NOTEBOOKS["nb_08_create_agents"] = [
    md("""# Lab 08 — 2 つの Data Agent を作成・公開

同じ業務定義（指示）で、データソースだけが異なる 2 つの Data Agent を作成します。

| Agent | 接続先 |
|---|---|
| `taxi_metrics_agent` | セマンティックモデル `sm_taxi` |
| `taxi_ontology_agent` | Ontology `onto_taxi`（コンテキストソース） |

設定内容はリポジトリの `config/agents.json` から `scripts/lab.py` が埋め込みます。何度実行しても同じ構成になります。"""),
    code('''%pip install -q "fabric-data-agent-sdk==0.1.36a0"'''),
    code(RESULT_HELPER),
    code('''import base64
import json
import time
import warnings

from fabric.dataagent.client import create_data_agent

AGENTS = json.loads(base64.b64decode("{{AGENT_CONFIG_B64}}").decode("utf-8"))
warnings.filterwarnings("ignore", category=FutureWarning)

def select_all(datasource, root_id=None):
    """Select every element (tables, columns, measures) so the agent can query them."""
    token = None
    while True:
        page = datasource.get_elements(root_id=root_id, continuation_token=token)
        for element in page.get("value", []):
            if element.get("isSelected") is False:
                datasource.update_element(element["id"], is_selected=True)
            if element.get("hasChildren") or element.get("children"):
                select_all(datasource, element["id"])
        token = page.get("continuationToken")
        if not token:
            break'''),
    code('''summary = {}

def find_source(list_sources, name, attempts=6, wait_seconds=10):
    """A just-added source can take a few seconds to appear in the list (eventual consistency)."""
    for attempt in range(attempts):
        found = [s for s in list_sources() if s.get_configuration().get("displayName") == name]
        if found:
            return found[0]
        time.sleep(wait_seconds)
    raise RuntimeError(f"data source {name} did not appear after {attempts} attempts")

def build_agent(config, attach):
    try:
        agent = create_data_agent(config["name"])
        agent.update_settings(ai_instructions="\\n".join(config["instructions"]))
        attach(agent, config)
        agent.publish_staging(description=config["description"])
        summary[config["name"]] = {"source": config["source"], "published": True}
    except Exception as error:  # keep going so the other agent is still created
        summary[config["name"]] = {"source": config["source"], "published": False,
                                   "error": f"{type(error).__name__}: {error}"[:500]}

def attach_semantic_model(agent, config):
    name = config["source"]["item"]
    if not [s for s in agent.list_datasources() if s.get_configuration().get("displayName") == name]:
        agent.add_staging_datasource(name, type=config["source"]["type"])
    datasource = find_source(agent.list_datasources, name)
    select_all(datasource)
    datasource.update_configuration(description="NYC green taxi trips April 2026: fact_trips with vendor, payment, trip type, pickup and dropoff zone dimensions.")

build_agent(AGENTS["metricsAgent"], attach_semantic_model)'''),
    code('''def attach_ontology(agent, config):
    name = config["source"]["item"]
    attached = [o for o in agent.list_ontologies() if o.get_configuration().get("displayName") == name]
    ontology = attached[0] if attached else agent.add_staging_ontology(name)
    ontology.select_entities()

build_agent(AGENTS["ontologyAgent"], attach_ontology)

save_result("nb_08_create_agents", {"passed": all(a["published"] for a in summary.values()), "agents": summary,
                                     "next": "scripts/lab.py agent-compare で 2 つの Agent に同じ質問をして比較します。"})'''),
]


TSQL_HEADER = """-- Fabric notebook source

-- METADATA ********************

-- META {
-- META   "kernel_info": {
-- META     "name": "sqldatawarehouse"
-- META   },
-- META   "dependencies": {
-- META     "warehouse": {
-- META       "default_warehouse": "{{WAREHOUSE_ID}}",
-- META       "known_warehouses": [
-- META         {
-- META           "id": "{{WAREHOUSE_ID}}",
-- META           "type": "Datawarehouse"
-- META         }
-- META       ]
-- META     }
-- META   }
-- META }
"""
TSQL_CELL_META = """
-- METADATA ********************

-- META {
-- META   "language": "sql",
-- META   "language_group": "sqldatawarehouse"
-- META }
"""

TSQL_CELLS: list[tuple[str, str]] = [
    ("markdown", """# Lab 04 — Warehouse のディメンションとファクトを作成（T-SQL Notebook）

Lakehouse `taxi_lakehouse` の加工済みテーブルを 3 部構成名で参照し、CTAS で Warehouse に書き込みます。
再実行すると同じ 7 テーブルだけを作り直します。"""),
    ("sql", """DROP TABLE IF EXISTS dbo.dim_vendor;
CREATE TABLE dbo.dim_vendor AS
SELECT CAST(VendorID AS INT) AS VendorID, CAST(vendor_name AS VARCHAR(100)) AS vendor_name
FROM taxi_lakehouse.dbo.vendor_lookup;

DROP TABLE IF EXISTS dbo.dim_ratecode;
CREATE TABLE dbo.dim_ratecode AS
SELECT CAST(RatecodeID AS INT) AS RatecodeID, CAST(ratecode_name AS VARCHAR(100)) AS ratecode_name
FROM taxi_lakehouse.dbo.ratecode_lookup;

DROP TABLE IF EXISTS dbo.dim_payment_type;
CREATE TABLE dbo.dim_payment_type AS
SELECT CAST(payment_type AS INT) AS payment_type, CAST(payment_type_name AS VARCHAR(100)) AS payment_type_name
FROM taxi_lakehouse.dbo.payment_type_lookup;

DROP TABLE IF EXISTS dbo.dim_trip_type;
CREATE TABLE dbo.dim_trip_type AS
SELECT CAST(trip_type AS INT) AS trip_type, CAST(trip_type_name AS VARCHAR(100)) AS trip_type_name
FROM taxi_lakehouse.dbo.trip_type_lookup;"""),
    ("markdown", "## 乗車地と降車地は役割の異なる 2 つのディメンションにする"),
    ("sql", """DROP TABLE IF EXISTS dbo.dim_pickup_zone;
CREATE TABLE dbo.dim_pickup_zone AS
SELECT CAST(LocationID AS INT) AS LocationID,
       CAST(Borough AS VARCHAR(50)) AS pickup_borough,
       CAST(Zone AS VARCHAR(100)) AS pickup_zone,
       CAST(service_zone AS VARCHAR(50)) AS pickup_service_zone
FROM taxi_lakehouse.dbo.taxi_zone_lookup;

DROP TABLE IF EXISTS dbo.dim_dropoff_zone;
CREATE TABLE dbo.dim_dropoff_zone AS
SELECT CAST(LocationID AS INT) AS LocationID,
       CAST(Borough AS VARCHAR(50)) AS dropoff_borough,
       CAST(Zone AS VARCHAR(100)) AS dropoff_zone,
       CAST(service_zone AS VARCHAR(50)) AS dropoff_service_zone
FROM taxi_lakehouse.dbo.taxi_zone_lookup;"""),
    ("markdown", "## ファクト（1 トリップ 1 行・乗車日時を保持）"),
    ("sql", """DROP TABLE IF EXISTS dbo.fact_trips;
CREATE TABLE dbo.fact_trips AS
SELECT
    CAST(trip_id AS BIGINT) AS trip_id,
    CAST(VendorID AS INT) AS VendorID,
    CAST(RatecodeID AS INT) AS RatecodeID,
    CAST(PULocationID AS INT) AS PULocationID,
    CAST(DOLocationID AS INT) AS DOLocationID,
    CAST(payment_type AS INT) AS payment_type,
    CAST(COALESCE(trip_type, 0) AS INT) AS trip_type,
    CAST(lpep_pickup_datetime AS DATETIME2(6)) AS lpep_pickup_datetime,
    CAST(lpep_dropoff_datetime AS DATETIME2(6)) AS lpep_dropoff_datetime,
    CAST(pickup_date AS DATE) AS pickup_date,
    CAST(pickup_hour AS INT) AS pickup_hour,
    CAST(pickup_month AS VARCHAR(7)) AS pickup_month,
    CAST(passenger_count AS INT) AS passenger_count,
    CAST(passenger_group AS VARCHAR(10)) AS passenger_group,
    trip_distance,
    trip_duration_minutes,
    fare_amount,
    tip_amount,
    tolls_amount,
    total_amount,
    fare_per_mile
FROM taxi_lakehouse.dbo.green_tripdata_2026;"""),
    ("sql", """SELECT 'fact_trips' AS table_name, COUNT_BIG(*) AS row_count FROM dbo.fact_trips
UNION ALL SELECT 'dim_vendor', COUNT_BIG(*) FROM dbo.dim_vendor
UNION ALL SELECT 'dim_ratecode', COUNT_BIG(*) FROM dbo.dim_ratecode
UNION ALL SELECT 'dim_payment_type', COUNT_BIG(*) FROM dbo.dim_payment_type
UNION ALL SELECT 'dim_trip_type', COUNT_BIG(*) FROM dbo.dim_trip_type
UNION ALL SELECT 'dim_pickup_zone', COUNT_BIG(*) FROM dbo.dim_pickup_zone
UNION ALL SELECT 'dim_dropoff_zone', COUNT_BIG(*) FROM dbo.dim_dropoff_zone
ORDER BY table_name;"""),
]


def tsql_notebook() -> str:
    parts = [TSQL_HEADER]
    for kind, text in TSQL_CELLS:
        if kind == "markdown":
            parts.append("\n-- MARKDOWN ********************\n\n" + "\n".join(f"-- {line}".rstrip() for line in text.split("\n")) + "\n")
        else:
            parts.append("\n-- CELL ********************\n\n" + text + "\n" + TSQL_CELL_META)
    return "".join(parts)


def render() -> dict[Path, str]:
    files = {(REFERENCE_OUT if name in GENERATED else OUT) / f"{name}.ipynb": json.dumps(notebook(cells), ensure_ascii=False, indent=1) + "\n"
             for name, cells in NOTEBOOKS.items()}
    files[REFERENCE_OUT / "nb_04_build_warehouse.sql"] = tsql_notebook()
    return files


if __name__ == "__main__":
    for path, content in render().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
