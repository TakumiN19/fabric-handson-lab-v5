#!/usr/bin/env python3
"""Offline checks for the Lab V4 repository (no Azure / Fabric access).

Run: python3 tests/validate_repo.py
Data checks need pandas + pyarrow; they are skipped with a notice otherwise.
"""

from __future__ import annotations

import base64
import hashlib
import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import build_notebooks  # noqa: E402
import lab  # noqa: E402

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def decode(parts: list[dict[str, str]]) -> dict[str, str]:
    return {p["path"]: base64.b64decode(p["payload"]).decode("utf-8") for p in parts}


# --------------------------------------------------------------------------- notebooks


def test_notebooks() -> None:
    for path, content in build_notebooks.render().items():
        check(path.exists() and path.read_text(encoding="utf-8") == content,
              f"{path.relative_to(ROOT)} is out of date; run python3 scripts/dev/build_notebooks.py")
    for name, spec in lab.NOTEBOOKS.items():
        path = lab.notebook_path(name, reference=True)
        check(path.exists(), f"notebook file missing for {name}")
        check(lab.check_notebook(name, reference=True)["passed"], f"{name}: reference notebook fails notebook check")
        if spec["source"] == "generated":
            check((ROOT / lab.SPECS / f"{name}.md").exists(), f"{name}: spec {lab.SPECS}/{name}.md missing")
        if path.suffix != ".ipynb":
            continue
        notebook = json.loads(path.read_text(encoding="utf-8"))
        check(notebook.get("nbformat") == 4, f"{name}: nbformat must be 4")
        for index, cell in enumerate(notebook["cells"]):
            check("metadata" in cell, f"{name} cell {index}: metadata missing")
            source = cell["source"]
            check(all(line.endswith("\n") for line in source[:-1]), f"{name} cell {index}: source lines must end with newline")
            if cell["cell_type"] == "code":
                check(cell.get("outputs") == [] and cell.get("execution_count") is None,
                      f"{name} cell {index}: code cells need outputs [] and execution_count null")
                code = "".join(source)
                if not code.startswith("%"):
                    try:
                        compile(code.replace("{{AGENT_CONFIG_B64}}", "e30="), f"{name}:{index}", "exec")
                    except SyntaxError as error:
                        failures.append(f"{name} cell {index}: syntax error {error}")
        lab_definition = lab.notebook_definition(name, "ws-id", "item-id", "taxi_lakehouse", reference=True)
        decoded = json.loads(base64.b64decode(lab_definition["parts"][0]["payload"]))
        binding = decoded["metadata"]["dependencies"]["lakehouse"]
        check(binding == {"default_lakehouse": "item-id", "default_lakehouse_name": "taxi_lakehouse",
                          "default_lakehouse_workspace_id": "ws-id"}, f"{name}: lakehouse binding not injected")
        text = json.dumps(decoded)
        check("{{" not in text, f"{name}: unresolved placeholder after injection")
        if name == "nb_08_create_agents":
            encoded = re.search(r'b64decode\(\\"([A-Za-z0-9+/=]+)\\"\)', text)
            check(bool(encoded) and json.loads(base64.b64decode(encoded.group(1)))["metricsAgent"]["name"] == "taxi_metrics_agent",
                  "nb_08: agent config not injected")
    sql = lab.notebook_definition("nb_04_build_warehouse", "ws", "wh-guid", "taxi_warehouse", reference=True)
    content = base64.b64decode(sql["parts"][0]["payload"]).decode("utf-8")
    check(sql["parts"][0]["path"] == "notebook-content.sql", "T-SQL notebook part path")
    check(content.count('"wh-guid"') == 2 and "{{" not in content, "T-SQL notebook warehouse id not injected")
    check(content.startswith("-- Fabric notebook source") and '"name": "sqldatawarehouse"' in content, "T-SQL notebook header")
    for table in ["fact_trips", "dim_vendor", "dim_ratecode", "dim_payment_type", "dim_trip_type", "dim_pickup_zone", "dim_dropoff_zone"]:
        check(f"CREATE TABLE dbo.{table} AS" in content, f"T-SQL notebook does not create {table}")
    test_notebook_contract()


def test_notebook_contract() -> None:
    """notebook check must reject the typical mistakes of a generated notebook, and stale results must be ignored."""
    temp = ROOT / ".lab" / "notebook-check-test"
    (temp / "nb").mkdir(parents=True, exist_ok=True)
    original = lab.GENERATED_NOTEBOOKS
    good = json.loads(lab.notebook_path("nb_02_prepare_trips", reference=True).read_text(encoding="utf-8"))
    try:
        lab.GENERATED_NOTEBOOKS = str((temp / "nb").relative_to(ROOT))
        target = temp / "nb" / "nb_02_prepare_trips.ipynb"
        try:
            lab.check_notebook("nb_02_prepare_trips")
            failures.append("check must fail with a clear message when the generated notebook is missing")
        except lab.LabError as error:
            check("notebooks/specs/nb_02_prepare_trips.md" in str(error), "missing-notebook message must point to the spec")
        target.write_text(json.dumps(good), encoding="utf-8")
        check(lab.check_notebook("nb_02_prepare_trips")["passed"], "a correct generated notebook must pass")
        bad = json.loads(json.dumps(good))
        bad["metadata"]["kernelspec"]["name"] = bad["metadata"]["kernel_info"]["name"] = "python3"
        bad["cells"].append({"cell_type": "code", "metadata": {}, "execution_count": 3, "outputs": [{"output_type": "stream"}],
                             "source": "%pip install pandas\nws = '11111111-2222-3333-4444-555555555555'\nx = {{LAKEHOUSE_ID}}\nif True print(1)\n"})
        for cell in bad["cells"]:
            cell["source"] = [line.replace('save_result("nb_02_prepare_trips"', 'save_result("other"') for line in lab._cell_lines(cell)]
        target.write_text(json.dumps(bad), encoding="utf-8")
        problems = " / ".join(lab.check_notebook("nb_02_prepare_trips")["problems"])
        for expected in ["synapse_pyspark", "出力を消して", "%pip", "構文エラー", "GUID", "{{LAKEHOUSE_ID}}", "save_result"]:
            check(expected in problems, f"notebook check must report '{expected}' (got: {problems})")
    finally:
        lab.GENERATED_NOTEBOOKS = original
        for path in sorted(temp.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        temp.rmdir()
    submitted = 1_800_000_000.0
    check(lab.fresh_result({"finishedAtUtc": "2027-01-15T08:00:00+00:00"}, submitted)[0] is not None, "fresh result kept")
    check(lab.fresh_result({"finishedAtUtc": "2020-01-01T00:00:00+00:00"}, submitted) == (None, True), "stale result ignored")


# --------------------------------------------------------------------------- TMDL generators


def tmdl_columns(text: str) -> list[str]:
    return re.findall(r"^\tcolumn (\S+)", text, flags=re.MULTILINE)


def test_semantic_model() -> None:
    parts = lab.semantic_model_parts("ws", "wh")
    check(parts == lab.semantic_model_parts("ws", "wh"), "semantic model generation must be deterministic")
    files = decode(parts)
    for required in ["definition.pbism", "definition/database.tmdl", "definition/model.tmdl", "definition/relationships.tmdl", "definition/expressions.tmdl"]:
        check(required in files, f"semantic model part missing: {required}")
    check("AzureStorage.DataLake(\"https://onelake.dfs.fabric.microsoft.com/ws/wh\"" in files["definition/expressions.tmdl"], "Direct Lake expression")
    for table, columns in lab.SM_TABLES.items():
        text = files.get(f"definition/tables/{table}.tmdl", "")
        check(tmdl_columns(text) == [c[0] for c in columns], f"semantic model table {table} columns")
        check("mode: directLake" in text and f"entityName: {table}" in text, f"semantic model table {table} partition")
        check(f"ref table {table}" in files["definition/model.tmdl"], f"model.tmdl missing ref {table}")
    for from_table, from_col, to_table, to_col in lab.SM_RELATIONSHIPS:
        check(f"fromColumn: {from_table}.{from_col}\n\ttoColumn: {to_table}.{to_col}" in files["definition/relationships.tmdl"],
              f"relationship {from_table}.{from_col}")
        check(from_col in [c[0] for c in lab.SM_TABLES[from_table]] and to_col in [c[0] for c in lab.SM_TABLES[to_table]],
              f"relationship column missing {from_table}.{from_col} -> {to_table}.{to_col}")
    measures = re.findall(r"measure '([^']+)'", files["definition/tables/fact_trips.tmdl"])
    check(measures == ["Trips", "Total Amount", "Avg Fare", "Max Fare", "Avg Trip Distance"], f"measures {measures}")
    for name, query in lab.MODEL_QUERIES.items():
        for ref in re.findall(r"\[([^\]]+)\]", query):
            known = set(measures) | {c[0] for cols in lab.SM_TABLES.values() for c in cols}
            check(ref in known, f"model-check query {name} references unknown [{ref}]")
    tsql = lab.notebook_path("nb_04_build_warehouse", reference=True).read_text(encoding="utf-8")
    for table, columns in lab.SM_TABLES.items():
        block = tsql.split(f"CREATE TABLE dbo.{table} AS", 1)[1].split("FROM", 1)[0]
        for column, _, _ in columns:
            check(re.search(rf"\b{re.escape(column)}\b", block) is not None, f"Warehouse {table} lacks column {column} used by the model")


def test_ontology() -> None:
    parts = lab.ontology_parts("onto_taxi", "server.datawarehouse.fabric.microsoft.com", "sql-endpoint-id")
    check(parts == lab.ontology_parts("onto_taxi", "server.datawarehouse.fabric.microsoft.com", "sql-endpoint-id"), "ontology generation must be deterministic")
    files = decode(parts)
    check(json.loads(files[".platform"])["config"]["version"] == "2.0", "ontology must use the new experience (2.0)")
    check(files["database.tmdl"].startswith("database\n\tcompatibilityLevel: 1000000"), "ontology database.tmdl")
    check("ref namespace default" in files["model.tmdl"] and "namespaces/default.tmdl" in files, "default namespace")
    check('Sql.Database("server.datawarehouse.fabric.microsoft.com", "sql-endpoint-id")' in files["expressions.tmdl"], "ontology expression")
    for entity, table, key, _ in lab.ONTOLOGY_ENTITIES:
        text = files.get(f"entities/{entity}.tmdl", "")
        columns = [c for c, _ in lab.ONTOLOGY_TABLES[table]]
        check(f"backingTable: {table}" in text and f"keyProperty: {key}" in text and key in columns, f"entity {entity} backing/key")
        for column in re.findall(r"valueColumn: (\S+)\.(\S+)", text):
            check(column[0] == table and column[1] in columns, f"entity {entity} binds unknown column {column}")
        check(f"ref entity {entity}" in files["model.tmdl"], f"model.tmdl missing ref entity {entity}")
    for name, from_entity, to_entity, (from_table, from_col, to_table, to_col), active in lab.ONTOLOGY_RELATIONSHIPS:
        check(f"entityRelationship {name}\n" in files["entityRelationships.tmdl"], f"entity relationship {name}")
        block = files["relationships.tmdl"].split(f"relationship rel_{name}\n", 1)[1].split("\n\n", 1)[0]
        check(f"fromColumn: {from_table}.{from_col}" in block and f"toColumn: {to_table}.{to_col}" in block, f"relationship rel_{name}")
        check(("isActive: false" in block) == (not active), f"relationship rel_{name} active flag")
    notebook = lab.notebook_path("nb_07_prepare_ontology", reference=True).read_text(encoding="utf-8")
    for table, columns in lab.ONTOLOGY_TABLES.items():
        check(f'\\"{table}\\"' in notebook, f"nb_07 does not create {table}")


# --------------------------------------------------------------------------- config & expected values


def test_config() -> None:
    workshop = lab.load_workshop()
    agents = json.loads((ROOT / "config" / "agents.json").read_text(encoding="utf-8"))
    check(agents["metricsAgent"]["name"] == workshop["items"]["metricsAgent"], "metrics agent name mismatch")
    check(agents["ontologyAgent"]["name"] == workshop["items"]["ontologyAgent"], "ontology agent name mismatch")
    check(agents["metricsAgent"]["source"]["item"] == workshop["items"]["semanticModel"], "metrics agent source")
    check(agents["ontologyAgent"]["source"]["item"] == workshop["items"]["ontology"], "ontology agent source")
    check(set(workshop["notebooks"].values()) <= set(lab.NOTEBOOKS), "workshop.json notebooks must exist in lab.NOTEBOOKS")
    versions = (ROOT / "config" / "versions.env").read_text(encoding="utf-8")
    check("RAYFIN_CLI_VERSION=2.0.1" in versions, "Rayfin version pin")
    readme_lab09 = (ROOT / "labs" / "09-rayfin-app.md").read_text(encoding="utf-8")
    check("@microsoft/create-rayfin@2.0.1" in readme_lab09, "Lab 09 must use the pinned Rayfin version")


def test_expected_values() -> None:
    expected = json.loads((ROOT / "tests" / "expected" / "expected.json").read_text(encoding="utf-8"))
    sample = ROOT / expected["sample"]["file"]
    content = sample.read_bytes()
    check(hashlib.sha256(content).hexdigest() == expected["sample"]["sha256"], "sample sha256 changed")
    check(len(content) == expected["sample"]["bytes"], "sample size changed")
    try:
        import pandas as pd  # noqa: F401
    except ImportError:
        print("NOTICE: pandas/pyarrow not installed; data checks skipped")
        return
    import pandas as pd

    raw = pd.read_parquet(sample)
    trips = expected["trips"]
    check(raw.shape == (expected["sample"]["rows"], expected["sample"]["columns"]), "sample shape")
    df = raw.drop(columns=["ehail_fee"])
    df = df[df.passenger_count.notna()].copy()
    order = ["lpep_pickup_datetime", "lpep_dropoff_datetime", "VendorID", "PULocationID", "DOLocationID", "trip_distance", "fare_amount", "total_amount"]
    check(not df[order].isna().any().any() and not df.duplicated(order).any(), "trip_id ordering columns must be non-null and unique")
    df = df.sort_values(order).reset_index(drop=True)
    df["trip_id"] = range(1, len(df) + 1)
    check(len(df) == trips["rows"], "trip rows")
    check(len(raw) - len(df) == trips["removedNullPassengerCount"], "removed rows")
    check(len(df.columns) + 6 == trips["columns"], "trip columns (20 kept + trip_id + 6 derived)")
    check(round(df.total_amount.sum(), 2) == trips["totalAmount"], "total amount")
    check(round(df.fare_amount.sum(), 2) == trips["fareAmount"], "fare amount")
    check(round(df.fare_amount.mean(), 2) == trips["avgFare"], "avg fare")
    check(round(df.fare_amount.max(), 2) == trips["maxFare"], "max fare")
    check(round(df.trip_distance.mean(), 2) == trips["avgTripDistance"], "avg distance")
    pc = df.passenger_count
    check({"single": int((pc == 1).sum()), "group": int((pc >= 2).sum()), "unknown": int((pc <= 0).sum())} == trips["passengerGroups"], "passenger groups")
    hour0 = df[df.lpep_pickup_datetime.dt.hour == 0]
    check({"trips": len(hour0), "avgFare": round(hour0.fare_amount.mean(), 2)} == trips["hour0"], "hour 0")
    for column, key in [("VendorID", "vendors"), ("trip_type", "tripTypes"), ("payment_type", "paymentTypes"), ("RatecodeID", "ratecodes")]:
        check({str(k): int(v) for k, v in df[column].value_counts().items()} == trips[key], f"{key} counts")
    for record in trips["fixedRecords"]:
        row = df[df.trip_id == record["trip_id"]].iloc[0]
        minutes = round((row.lpep_dropoff_datetime - row.lpep_pickup_datetime).total_seconds() / 60, 2)
        actual = {"VendorID": int(row.VendorID), "PULocationID": int(row.PULocationID), "DOLocationID": int(row.DOLocationID),
                  "pickup": str(row.lpep_pickup_datetime), "dropoff": str(row.lpep_dropoff_datetime), "passenger_count": int(row.passenger_count),
                  "trip_distance": row.trip_distance, "fare_amount": row.fare_amount, "total_amount": row.total_amount,
                  "trip_duration_minutes": minutes, "fare_per_mile": round(row.fare_amount / row.trip_distance, 2)}
        for key, value in actual.items():
            check(record[key] == value, f"fixed record {record['trip_id']} {key}: expected {record[key]} actual {value}")


# --------------------------------------------------------------------------- docs & hygiene


def slug(heading: str) -> str:
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def test_markdown() -> None:
    markdown_files = [p for p in ROOT.rglob("*.md") if ".git" not in p.parts and "node_modules" not in p.parts and ".lab" not in p.parts]
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)\s]+)\)", text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file_part, _, anchor = target.partition("#")
            destination = (path.parent / file_part).resolve() if file_part else path
            check(destination.exists(), f"{path.relative_to(ROOT)}: broken link {target}")
            if anchor and destination.exists() and destination.suffix == ".md":
                headings = {slug(h) for h in re.findall(r"^#{1,6} (.+)$", destination.read_text(encoding="utf-8"), flags=re.MULTILINE)}
                check(anchor in headings, f"{path.relative_to(ROOT)}: missing anchor #{anchor} in {destination.relative_to(ROOT)}")
    stale = ["sm_taxi_warehouse", "fact_greentrip", "00-prerequisites", "01-login-and-connect", "taxi_ride_agent", "VITE_AGENT_PROXY_URL"]
    for path in markdown_files:
        if path.relative_to(ROOT).parts[0] in ("labs", "instructor", "reference") or path.name == "README.md":
            text = path.read_text(encoding="utf-8")
            for word in stale:
                check(word not in text, f"{path.relative_to(ROOT)}: stale V3 reference '{word}'")


def test_scripts_and_secrets() -> None:
    for path in list((ROOT / "scripts").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            failures.append(f"{path.relative_to(ROOT)}: {error}")
    result = subprocess.run(["bash", "-n", str(ROOT / ".devcontainer" / "scripts" / "setup.sh")], capture_output=True, text=True)
    check(result.returncode == 0, f"setup.sh syntax: {result.stderr}")
    secret_patterns = [r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{30,}",
                       r"(?i)client_secret\s*[:=]\s*['\"][^'\"]{8,}"]
    for path in ROOT.rglob("*"):
        if path.is_file() and ".git" not in path.parts and "node_modules" not in path.parts and path.suffix in {".md", ".py", ".json", ".ts", ".mts", ".sql", ".ipynb", ".sh", ".env", ".yml"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in secret_patterns:
                check(re.search(pattern, text) is None, f"{path.relative_to(ROOT)}: looks like a secret ({pattern})")


def test_student_parser() -> None:
    original = lab.STUDENT_FILE
    temp = ROOT / ".lab" / "student-test.md"
    temp.parent.mkdir(exist_ok=True)
    workshop = lab.load_workshop()
    temp.write_text(
        "# 参加者設定\n- student 番号: 03\n"
        f"- アカウント: student03@{workshop['accountDomain']}\n- ワークスペース名: student03\n"
        f"- テナント ID: {workshop['tenantId']}\n", encoding="utf-8")
    try:
        lab.STUDENT_FILE = temp
        student = lab.load_student()
        check(student["number"] == "03" and student["workspace"] == "student03", "student parser keeps leading zeros")
        lab.save_workspace_id("11111111-1111-1111-1111-111111111111")
        lab.save_workspace_id("22222222-2222-2222-2222-222222222222")
        text = temp.read_text(encoding="utf-8")
        check(text.count("Workspace ID") == 1 and "2222" in text, "Workspace ID is saved once and updated")
        temp.write_text(text.replace("student03@", "student04@"), encoding="utf-8")
        try:
            lab.load_student()
            failures.append("mismatched account must be rejected")
        except lab.LabError:
            pass
    finally:
        lab.STUDENT_FILE = original
        temp.unlink(missing_ok=True)


def main() -> int:
    for test in [test_notebooks, test_semantic_model, test_ontology, test_config, test_expected_values, test_markdown,
                 test_scripts_and_secrets, test_student_parser]:
        before = len(failures)
        test()
        print(f"{'PASS' if len(failures) == before else 'FAIL'} {test.__name__}")
    for failure in failures:
        print(f"  - {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
