#!/usr/bin/env python3
"""Lab V4 helper for Microsoft Fabric.

Copilot runs these subcommands on behalf of participants so every step is
repeatable and always targets the registered account, tenant and workspace.
It uses the Azure CLI sign-in only. Tokens are kept in memory and are never
printed or written to disk.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STUDENT_FILE = ROOT / ".github" / "student.local.md"
FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_RESOURCE = "https://api.fabric.microsoft.com"
STORAGE_RESOURCE = "https://storage.azure.com"
POWERBI_RESOURCE = "https://analysis.windows.net/powerbi/api"
POWERBI_API = "https://api.powerbi.com/v1.0/myorg"
ONELAKE_DFS = "https://onelake.dfs.fabric.microsoft.com"
PORTAL = "https://app.fabric.microsoft.com"
LINEAGE_NAMESPACE = uuid.UUID("6f3c9d0e-3b8b-4b0e-9a63-2f0f4c1f7a11")
RESULTS_FOLDER = "Files/lab_results"

GENERATED_NOTEBOOKS = "work/notebooks"
REFERENCE_NOTEBOOKS = "reference/notebooks"
SPECS = "notebooks/specs"
# source "generated": participants have GitHub Copilot write the notebook from notebooks/specs/<name>.md
#                     into work/notebooks/ (answer key in reference/notebooks/, used with --reference).
# source "provided":  read-only graders shipped in notebooks/.
NOTEBOOKS = {
    "nb_02_prepare_trips": {"file": "nb_02_prepare_trips.ipynb", "binding": "lakehouse", "source": "generated",
                            "outputs": ["green_tripdata_2026"]},
    "nb_02_validate_trips": {"file": "nb_02_validate_trips.ipynb", "binding": "lakehouse", "source": "provided"},
    "nb_03_prepare_dimensions": {"file": "nb_03_prepare_dimensions.ipynb", "binding": "lakehouse", "source": "generated",
                                 "outputs": ["taxi_zone_lookup", "vendor_lookup", "ratecode_lookup", "payment_type_lookup", "trip_type_lookup"]},
    "nb_03_validate_dimensions": {"file": "nb_03_validate_dimensions.ipynb", "binding": "lakehouse", "source": "provided"},
    "nb_04_build_warehouse": {"file": "nb_04_build_warehouse.sql", "binding": "warehouse", "source": "generated",
                              "outputs": ["fact_trips", "dim_vendor", "dim_ratecode", "dim_payment_type", "dim_trip_type",
                                          "dim_pickup_zone", "dim_dropoff_zone"]},
    "nb_04_validate_warehouse": {"file": "nb_04_validate_warehouse.ipynb", "binding": "lakehouse", "source": "provided"},
    "nb_07_prepare_ontology": {"file": "nb_07_prepare_ontology.ipynb", "binding": "lakehouse", "source": "generated",
                               "outputs": ["onto_trips", "onto_zones", "onto_vendors"]},
    "nb_08_create_agents": {"file": "nb_08_create_agents.ipynb", "binding": "lakehouse", "source": "generated",
                            "outputs": [], "pip": True, "requires": ["{{AGENT_CONFIG_B64}}"]},
}
NOTEBOOK_PLACEHOLDERS = {"lakehouse": {"{{WORKSHOP_CONFIG_B64}}", "{{AGENT_CONFIG_B64}}"}, "warehouse": {"{{WAREHOUSE_ID}}"}}


class LabError(Exception):
    """An expected, user-actionable failure."""


# --------------------------------------------------------------------------- config


def load_workshop() -> dict[str, Any]:
    config = json.loads((ROOT / "config" / "workshop.json").read_text(encoding="utf-8"))
    local = ROOT / "config" / "workshop.local.json"
    if local.exists():
        config.update(json.loads(local.read_text(encoding="utf-8")))
    return config


def load_student() -> dict[str, str]:
    if not STUDENT_FILE.exists():
        raise LabError("参加者設定 .github/student.local.md がありません。Lab 00 の student 番号登録を先に実施してください。")
    fields: dict[str, str] = {}
    for line in STUDENT_FILE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*[-*]\s*([^:：]+)[:：]\s*`?([^`]*?)`?\s*$", line)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    number = fields.get("student 番号", "")
    if not re.fullmatch(r"\d+", number):
        raise LabError("参加者設定の student 番号が不正です。Lab 00 の登録をやり直してください。")
    workshop = load_workshop()
    expected_workspace = f"{workshop['workspacePrefix']}{number}"
    expected_account = f"{workshop['accountPrefix']}{number}@{workshop['accountDomain']}"
    student = {
        "number": number,
        "workspace": fields.get("ワークスペース名", ""),
        "account": fields.get("アカウント", ""),
        "tenant": fields.get("テナント ID", ""),
        "workspace_id": fields.get("Workspace ID", ""),
    }
    if (student["workspace"], student["account"].lower(), student["tenant"]) != (
        expected_workspace,
        expected_account.lower(),
        workshop["tenantId"],
    ):
        raise LabError("参加者設定の内容が番号と一致しません。Lab 00 の登録をやり直してください。")
    return student


def save_workspace_id(workspace_id: str) -> None:
    text = STUDENT_FILE.read_text(encoding="utf-8")
    line = f"- Workspace ID: {workspace_id}"
    if re.search(r"^\s*[-*]\s*Workspace ID[:：].*$", text, flags=re.MULTILINE):
        text = re.sub(r"^\s*[-*]\s*Workspace ID[:：].*$", line, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + "\n" + line + "\n"
    STUDENT_FILE.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- auth & http


def az_json(*args: str) -> Any:
    result = subprocess.run(["az", *args, "--only-show-errors", "-o", "json"], capture_output=True, text=True)
    if result.returncode != 0:
        raise LabError("Azure CLI にサインインしていないか、期限切れです。Lab 01 のサインインを実行してください。")
    return json.loads(result.stdout)


_TOKENS: dict[str, tuple[str, float]] = {}


def token(resource: str, tenant: str) -> str:
    cached = _TOKENS.get(resource)
    if cached and cached[1] - time.time() > 300:
        return cached[0]
    data = az_json("account", "get-access-token", "--resource", resource, "--tenant", tenant)
    _TOKENS[resource] = (data["accessToken"], float(data.get("expires_on") or time.time() + 1800))
    return data["accessToken"]


def verify_identity(student: dict[str, str]) -> dict[str, str]:
    account = az_json("account", "show")
    user = account.get("user", {}).get("name", "")
    tenant = account.get("tenantId", "")
    if user.lower() != student["account"].lower() or tenant != student["tenant"]:
        raise LabError(
            "サインイン中のアカウントまたはテナントが参加者設定と一致しません。"
            "登録済みのアカウントで Azure CLI にサインインし直してください。"
        )
    return {"user": user, "tenant": tenant}


class Fabric:
    def __init__(self, student: dict[str, str]):
        self.student = student
        self.tenant = student["tenant"]

    def request(
        self,
        method: str,
        path_or_url: str,
        body: Any = None,
        *,
        resource: str = FABRIC_RESOURCE,
        raw: bytes | None = None,
        headers: dict[str, str] | None = None,
        expect_json: bool = True,
    ) -> tuple[int, dict[str, str], Any]:
        url = path_or_url if path_or_url.startswith("https://") else f"{FABRIC_API}{path_or_url}"
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req_headers = {"Authorization": f"Bearer {token(resource, self.tenant)}"}
        if body is not None:
            req_headers["Content-Type"] = "application/json"
        req_headers.update(headers or {})
        for attempt in range(6):
            request = urllib.request.Request(url, data=data, method=method, headers=req_headers)
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = response.read()
                    parsed = json.loads(payload) if expect_json and payload else payload
                    return response.status, dict(response.headers), parsed
            except urllib.error.HTTPError as error:
                payload = error.read()
                if error.code in (429, 503) and attempt < 5:
                    time.sleep(int(error.headers.get("Retry-After") or 10))
                    continue
                detail = ""
                try:
                    parsed_error = json.loads(payload)
                    detail = f" {parsed_error.get('errorCode', '')}: {parsed_error.get('message', '')}".rstrip()
                except ValueError:
                    pass
                raise LabError(f"Fabric API {method} {urllib.parse.urlparse(url).path} が HTTP {error.code} で失敗しました。{detail}")
        raise LabError("Fabric API の再試行回数を超えました。時間をおいて再実行してください。")

    def lro(self, status: int, headers: dict[str, str], body: Any, *, want_result: bool = False) -> Any:
        if status != 202:
            return body
        location = headers.get("Location") or headers.get("location")
        if not location:
            return body
        while True:
            time.sleep(int(headers.get("Retry-After") or 5))
            _, headers, state = self.request("GET", location)
            current = (state or {}).get("status")
            if current == "Succeeded":
                if want_result:
                    return self.request("GET", location.rstrip("/") + "/result")[2]
                return state
            if current in ("Failed", "Cancelled"):
                error = (state or {}).get("error") or {}
                raise LabError(f"Fabric の非同期処理が {current} になりました: {error.get('errorCode', '')} {error.get('message', '')}")

    def paged(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        url: str | None = path
        while url:
            _, _, page = self.request("GET", url)
            items.extend(page.get("value", []))
            url = page.get("continuationUri")
        return items

    # ---------------------------------------------------------------- resolution

    def workspace_id(self) -> str:
        matches = [w for w in self.paged("/workspaces") if w.get("displayName") == self.student["workspace"]]
        if len(matches) != 1:
            raise LabError(f"ワークスペース {self.student['workspace']} を一意に特定できません（候補 {len(matches)} 件）。講師に確認してください。")
        workspace_id = matches[0]["id"]
        saved = self.student.get("workspace_id")
        if saved and saved != workspace_id:
            raise LabError("保存済みの Workspace ID と API の結果が一致しません。Lab 00 の登録をやり直してください。")
        return workspace_id

    def item(self, workspace_id: str, item_type: str, name: str, *, required: bool = True) -> dict[str, Any] | None:
        matches = [i for i in self.paged(f"/workspaces/{workspace_id}/items?type={item_type}") if i.get("displayName") == name]
        if len(matches) > 1:
            raise LabError(f"{item_type} {name} が複数あります。重複を解消してから再実行してください。")
        if not matches:
            if required:
                raise LabError(f"{item_type} {name} が見つかりません。前の Lab を完了しているか確認してください。")
            return None
        return matches[0]


def context() -> tuple[Fabric, str]:
    student = load_student()
    verify_identity(student)
    fabric = Fabric(student)
    return fabric, fabric.workspace_id()


def portal_link(workspace_id: str, kind: str, item_id: str) -> str:
    return f"{PORTAL}/groups/{workspace_id}/{kind}/{item_id}?experience=fabric-developer"


def b64(text: str | bytes) -> str:
    raw = text.encode("utf-8") if isinstance(text, str) else text
    return base64.b64encode(raw).decode("ascii")


def tag(*parts: str) -> str:
    return str(uuid.uuid5(LINEAGE_NAMESPACE, "/".join(parts)))


# --------------------------------------------------------------------------- commands: setup


def cmd_check(args: argparse.Namespace) -> None:
    student = load_student()
    identity = verify_identity(student)
    fabric = Fabric(student)
    workspace_id = fabric.workspace_id()
    if args.save and student.get("workspace_id") != workspace_id:
        save_workspace_id(workspace_id)
    items = fabric.paged(f"/workspaces/{workspace_id}/items")
    print(json.dumps({
        "user": identity["user"],
        "tenant": identity["tenant"],
        "workspace": student["workspace"],
        "workspaceId": workspace_id,
        "workspaceIdSaved": bool(args.save) or student.get("workspace_id") == workspace_id,
        "items": sorted(f"{i['type']}: {i['displayName']}" for i in items),
    }, ensure_ascii=False, indent=2))


def ensure_item(fabric: Fabric, workspace_id: str, item_type: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    existing = fabric.item(workspace_id, item_type, name, required=False)
    if existing:
        return existing
    status, headers, body = fabric.request("POST", f"/workspaces/{workspace_id}/items", {"displayName": name, "type": item_type, **payload})
    fabric.lro(status, headers, body)
    return fabric.item(workspace_id, item_type, name)  # type: ignore[return-value]


def wait_sql_endpoint(fabric: Fabric, workspace_id: str, lakehouse_id: str) -> dict[str, Any]:
    for _ in range(60):
        _, _, lakehouse = fabric.request("GET", f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}")
        endpoint = (lakehouse.get("properties") or {}).get("sqlEndpointProperties") or {}
        if endpoint.get("provisioningStatus") == "Success":
            return endpoint
        time.sleep(10)
    raise LabError("Lakehouse の SQL 分析エンドポイントの準備が完了しません。数分後に再実行してください。")


def cmd_ensure_lakehouse(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    name = load_workshop()["items"]["lakehouse"]
    lakehouse = ensure_item(fabric, workspace_id, "Lakehouse", name, {})
    endpoint = wait_sql_endpoint(fabric, workspace_id, lakehouse["id"])
    print(json.dumps({"lakehouse": name, "id": lakehouse["id"], "sqlEndpoint": endpoint.get("connectionString"),
                      "link": portal_link(workspace_id, "lakehouses", lakehouse["id"])}, ensure_ascii=False, indent=2))


def cmd_ensure_warehouse(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    name = load_workshop()["items"]["warehouse"]
    warehouse = ensure_item(fabric, workspace_id, "Warehouse", name, {})
    _, _, details = fabric.request("GET", f"/workspaces/{workspace_id}/warehouses/{warehouse['id']}")
    print(json.dumps({"warehouse": name, "id": warehouse["id"], "server": (details.get("properties") or {}).get("connectionString"),
                      "link": portal_link(workspace_id, "datawarehouses", warehouse["id"])}, ensure_ascii=False, indent=2))


def onelake_url(workspace_id: str, item_id: str, path: str) -> str:
    return f"{ONELAKE_DFS}/{workspace_id}/{item_id}/{urllib.parse.quote(path)}"


def cmd_upload_sample(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    lakehouse = fabric.item(workspace_id, "Lakehouse", load_workshop()["items"]["lakehouse"])
    source = ROOT / "data" / "green_tripdata_2026-04.parquet"
    content = source.read_bytes()
    target = "Files/raw/green_tripdata_2026-04.parquet"
    url = onelake_url(workspace_id, lakehouse["id"], target)  # type: ignore[index]
    common = {"x-ms-version": "2021-06-08"}
    fabric.request("PUT", f"{url}?resource=file", raw=b"", resource=STORAGE_RESOURCE, headers=common, expect_json=False)
    fabric.request("PATCH", f"{url}?action=append&position=0", raw=content, resource=STORAGE_RESOURCE,
                   headers={**common, "Content-Type": "application/octet-stream"}, expect_json=False)
    fabric.request("PATCH", f"{url}?action=flush&position={len(content)}", raw=b"", resource=STORAGE_RESOURCE,
                   headers=common, expect_json=False)
    _, headers, _ = fabric.request("HEAD", url, resource=STORAGE_RESOURCE, headers=common, expect_json=False)
    uploaded = int(headers.get("Content-Length") or headers.get("content-length") or -1)
    if uploaded != len(content):
        raise LabError(f"アップロード後のサイズが一致しません（ローカル {len(content)} / OneLake {uploaded}）。")
    print(json.dumps({"uploaded": target, "bytes": uploaded}, ensure_ascii=False, indent=2))


def cmd_shortcut(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    workshop = load_workshop()
    adls = workshop["sharedAdls"]
    lakehouse = fabric.item(workspace_id, "Lakehouse", workshop["items"]["lakehouse"])
    connections = [c for c in fabric.paged("/connections") if c.get("displayName") == adls["connectionName"]]
    if len(connections) != 1:
        raise LabError(f"共有接続 {adls['connectionName']} が見つからないか複数あります。講師に接続の共有（User 権限）を依頼してください。")
    lakehouse_id = lakehouse["id"]  # type: ignore[index]
    existing = fabric.paged(f"/workspaces/{workspace_id}/items/{lakehouse_id}/shortcuts")
    if not any(s.get("name") == "taxi_zone" and s.get("path", "").strip("/") == "Files" for s in existing):
        fabric.request("POST", f"/workspaces/{workspace_id}/items/{lakehouse_id}/shortcuts", {
            "path": "Files",
            "name": "taxi_zone",
            "target": {"adlsGen2": {"location": adls["location"], "subpath": adls["subpath"], "connectionId": connections[0]["id"]}},
        })
    shortcuts = fabric.paged(f"/workspaces/{workspace_id}/items/{lakehouse_id}/shortcuts")
    print(json.dumps([{"name": s.get("name"), "path": s.get("path"), "type": (s.get("target") or {}).get("type", "")}
                      for s in shortcuts], ensure_ascii=False, indent=2))


def cmd_refresh_sql_endpoint(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    lakehouse = fabric.item(workspace_id, "Lakehouse", load_workshop()["items"]["lakehouse"])
    endpoint = wait_sql_endpoint(fabric, workspace_id, lakehouse["id"])  # type: ignore[index]
    status, headers, body = fabric.request("POST", f"/workspaces/{workspace_id}/sqlEndpoints/{endpoint['id']}/refreshMetadata", {})
    result = fabric.lro(status, headers, body, want_result=status == 202)
    tables = result.get("value", result) if isinstance(result, dict) else result
    print(json.dumps({"refreshed": True, "tables": tables}, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- commands: notebooks


def notebook_path(name: str, reference: bool = False) -> Path:
    spec = NOTEBOOKS[name]
    if spec["source"] == "provided":
        return ROOT / "notebooks" / spec["file"]
    return ROOT / (REFERENCE_NOTEBOOKS if reference else GENERATED_NOTEBOOKS) / spec["file"]


def read_notebook_source(name: str, reference: bool = False) -> tuple[Path, str]:
    path = notebook_path(name, reference)
    if not path.exists():
        raise LabError(
            f"{path.relative_to(ROOT)} がありません。{SPECS}/{name}.md の仕様に従って GitHub Copilot で生成してください"
            "（模範解答で進める場合は --reference を付けます）。")
    return path, path.read_text(encoding="utf-8")


def _cell_lines(cell: dict[str, Any]) -> list[str]:
    source = cell.get("source", [])
    return source.splitlines(keepends=True) if isinstance(source, str) else list(source)


GUID_PATTERN = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
SECRET_PATTERNS = [re.compile(p) for p in (r"eyJ[A-Za-z0-9_-]{20,}\.", r"(?i)\bbearer\s+[A-Za-z0-9._-]{20,}",
                                            r"(?i)client_secret", r"(?i)(password|passwd)\s*=")]


def check_notebook(name: str, reference: bool = False) -> dict[str, Any]:
    """Offline contract check for a notebook before it is deployed (no Fabric access)."""
    spec = NOTEBOOKS[name]
    path, text = read_notebook_source(name, reference)
    problems: list[str] = []
    allowed = NOTEBOOK_PLACEHOLDERS[spec["binding"]]
    cells: list[str] = []
    for placeholder in set(re.findall(r"\{\{[^{}]*\}\}", text)) - allowed:
        problems.append(f"使えないプレースホルダー {placeholder}（使えるのは {', '.join(sorted(allowed))}）")
    for required in spec.get("requires", []):
        if required not in text:
            problems.append(f"{required} を使って設定を読み込んでいません")
    if GUID_PATTERN.search(text):
        problems.append("GUID が直書きされています。ID は lab.py が配置時に埋め込みます（既定 Lakehouse / {{WAREHOUSE_ID}}）")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            problems.append("トークン・パスワードのような文字列があります。Notebook に資格情報を書かないでください")
            break
    if spec["binding"] == "warehouse":
        if not text.startswith("-- Fabric notebook source"):
            problems.append("1 行目が '-- Fabric notebook source' ではありません（Fabric の T-SQL Notebook 形式）")
        if '"name": "sqldatawarehouse"' not in text or "{{WAREHOUSE_ID}}" not in text:
            problems.append("ヘッダーの kernel_info（sqldatawarehouse）と default_warehouse の {{WAREHOUSE_ID}} が必要です")
        for table in spec["outputs"]:
            if not re.search(rf"CREATE\s+TABLE\s+dbo\.{table}\s+AS\b", text, flags=re.IGNORECASE):
                problems.append(f"CREATE TABLE dbo.{table} AS（CTAS）がありません")
        cells = [block.strip().splitlines()[0] for block in text.split("-- CELL ********************")[1:] if block.strip()]
        return {"notebook": name, "file": str(path.relative_to(ROOT)), "passed": not problems, "problems": problems, "cells": cells}
    try:
        notebook = json.loads(text)
    except json.JSONDecodeError as error:
        return {"notebook": name, "file": str(path.relative_to(ROOT)), "passed": False, "problems": [f"JSON として読めません: {error}"], "cells": []}
    if notebook.get("nbformat") != 4:
        problems.append("nbformat は 4 にしてください")
    kernel = ((notebook.get("metadata") or {}).get("kernelspec") or {}).get("name") or ((notebook.get("metadata") or {}).get("kernel_info") or {}).get("name")
    if kernel != "synapse_pyspark":
        problems.append(f"カーネルは synapse_pyspark にしてください（現在: {kernel}）")
    code_text = ""
    for index, cell in enumerate(notebook.get("cells", [])):
        lines = _cell_lines(cell)
        first = next((line.strip() for line in lines if line.strip()), "")
        cells.append(f"[{cell.get('cell_type')}] {first[:90]}")
        if cell.get("cell_type") != "code":
            continue
        if cell.get("outputs") or cell.get("execution_count") is not None:
            problems.append(f"セル {index}: 出力を消してください（outputs [] / execution_count null）")
        source = "".join(lines)
        magic = [line for line in lines if line.lstrip().startswith(("%", "!"))]
        if magic and not (spec.get("pip") and all(line.lstrip().startswith("%pip install") for line in magic)):
            problems.append(f"セル {index}: %pip / シェルコマンドはこの Notebook では使えません")
        body = "".join(line for line in lines if not line.lstrip().startswith(("%", "!")))
        for placeholder in allowed:
            body = body.replace(placeholder, "e30=")
        try:
            compile(body, f"{name}:cell{index}", "exec")
        except SyntaxError as error:
            problems.append(f"セル {index}: 構文エラー {error.msg}（{error.lineno} 行目）")
        code_text += source + "\n"
    if "save_result(" not in code_text or not re.search(rf"[\"']{name}[\"']", code_text):
        problems.append(f'save_result("{name}", ...) で Files/lab_results/{name}.json に結果を書いていません')
    if "Files/lab_results/" not in code_text:
        problems.append("結果の保存先 Files/lab_results/ がありません")
    for table in spec.get("outputs", []):
        if table not in code_text:
            problems.append(f"出力テーブル {table} を書いていません")
    return {"notebook": name, "file": str(path.relative_to(ROOT)), "passed": not problems, "problems": problems, "cells": cells}


def notebook_definition(name: str, workspace_id: str, binding_id: str, binding_name: str, reference: bool = False) -> dict[str, Any]:
    spec = NOTEBOOKS[name]
    path, source = read_notebook_source(name, reference)
    label = path.relative_to(ROOT)
    if spec["binding"] == "warehouse":
        content = source.replace("{{WAREHOUSE_ID}}", binding_id)
        if "{{" in content:
            raise LabError(f"{label} に未解決のプレースホルダーがあります。")
        return {"parts": [{"path": "notebook-content.sql", "payload": b64(content), "payloadType": "InlineBase64"}]}
    notebook = json.loads(source)
    injected = {"{{WORKSHOP_CONFIG_B64}}": b64(json.dumps(load_workshop(), ensure_ascii=False)),
                "{{AGENT_CONFIG_B64}}": b64((ROOT / "config" / "agents.json").read_text(encoding="utf-8"))}
    for cell in notebook.get("cells", []):
        cell["source"] = [_inject(line, injected) for line in _cell_lines(cell)]
    if any("{{" in line and "}}" in line for cell in notebook.get("cells", []) for line in cell.get("source", [])):
        raise LabError(f"{label} に未解決のプレースホルダーがあります。")
    notebook.setdefault("metadata", {})["dependencies"] = {
        "lakehouse": {
            "default_lakehouse": binding_id,
            "default_lakehouse_name": binding_name,
            "default_lakehouse_workspace_id": workspace_id,
        }
    }
    return {"format": "ipynb", "parts": [{"path": "notebook-content.ipynb", "payload": b64(json.dumps(notebook, ensure_ascii=False)), "payloadType": "InlineBase64"}]}


def _inject(line: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        line = line.replace(key, value)
    return line


def binding_for(fabric: Fabric, workspace_id: str, name: str) -> tuple[str, str]:
    workshop = load_workshop()["items"]
    if NOTEBOOKS[name]["binding"] == "warehouse":
        item = fabric.item(workspace_id, "Warehouse", workshop["warehouse"])
    else:
        item = fabric.item(workspace_id, "Lakehouse", workshop["lakehouse"])
    return item["id"], item["displayName"]  # type: ignore[index]


def deploy_notebook(fabric: Fabric, workspace_id: str, name: str, reference: bool = False) -> dict[str, Any]:
    if name not in NOTEBOOKS:
        raise LabError(f"未知の Notebook です: {name}")
    checked = check_notebook(name, reference)
    if not checked["passed"]:
        raise LabError(f"{checked['file']} が Notebook の約束を満たしていないため配置しません:\n- " + "\n- ".join(checked["problems"]))
    binding_id, binding_name = binding_for(fabric, workspace_id, name)
    definition = notebook_definition(name, workspace_id, binding_id, binding_name, reference)
    existing = fabric.item(workspace_id, "Notebook", name, required=False)
    if existing:
        status, headers, body = fabric.request("POST", f"/workspaces/{workspace_id}/notebooks/{existing['id']}/updateDefinition", {"definition": definition})
        fabric.lro(status, headers, body)
        return existing
    status, headers, body = fabric.request("POST", f"/workspaces/{workspace_id}/notebooks", {
        "displayName": name, "description": "Fabric Hands-on Lab V4" + notebook_origin(name, reference), "definition": definition})
    fabric.lro(status, headers, body)
    return fabric.item(workspace_id, "Notebook", name)  # type: ignore[return-value]


def notebook_origin(name: str, reference: bool) -> str:
    if NOTEBOOKS[name]["source"] == "provided":
        return "（検証用・教材提供）"
    return "（模範解答）" if reference else "（GitHub Copilot が生成）"


def read_result(fabric: Fabric, workspace_id: str, name: str) -> Any:
    lakehouse = fabric.item(workspace_id, "Lakehouse", load_workshop()["items"]["lakehouse"])
    url = onelake_url(workspace_id, lakehouse["id"], f"{RESULTS_FOLDER}/{name}.json")  # type: ignore[index]
    try:
        _, _, payload = fabric.request("GET", url, resource=STORAGE_RESOURCE, headers={"x-ms-version": "2021-06-08"}, expect_json=False)
    except LabError:
        return None
    return json.loads(payload)


def run_notebook(fabric: Fabric, workspace_id: str, notebook: dict[str, Any], name: str) -> dict[str, Any]:
    base = f"/workspaces/{workspace_id}/items/{notebook['id']}/jobs/instances"
    for job in fabric.paged(base):
        if job.get("status") in ("NotStarted", "InProgress"):
            raise LabError(f"{name} はすでに実行中です（Job {job.get('id')}）。完了を待ってから結果を確認してください。")
    configuration: dict[str, Any] = {}
    if NOTEBOOKS[name]["binding"] == "lakehouse":
        lakehouse_id, lakehouse_name = binding_for(fabric, workspace_id, name)
        configuration = {"defaultLakehouse": {"name": lakehouse_name, "id": lakehouse_id, "workspaceId": workspace_id}}
    body = {"executionData": {"configuration": configuration}} if configuration else None
    submitted = time.time()
    status, headers, _ = fabric.request("POST", f"{base}?jobType=RunNotebook", body or {})
    location = headers.get("Location") or headers.get("location")
    if status != 202 or not location:
        raise LabError("Notebook の実行を開始できませんでした。")
    job_id = location.rstrip("/").split("/")[-1]
    print(f"Notebook {name} を Fabric で実行中です（Job {job_id}）。Spark の起動を含め数分かかります。", file=sys.stderr, flush=True)
    started = time.time()
    while True:
        time.sleep(15)
        _, _, job = fabric.request("GET", location)
        state = job.get("status")
        if state in ("Completed", "Failed", "Cancelled", "Deduped"):
            return {"jobId": job_id, "status": state, "failureReason": (job.get("failureReason") or {}).get("message"),
                    "seconds": round(time.time() - started), "submittedEpoch": submitted}
        if time.time() - started > 3600:
            raise LabError(f"{name} が 60 分以内に完了しません。ポータルの Notebook 実行履歴を確認してください（Job {job_id}）。")


def fresh_result(result: Any, submitted: float) -> tuple[Any, bool]:
    """Ignore a result file left over from an earlier run (it is not deleted before a run)."""
    if not isinstance(result, dict):
        return result, False
    finished = str(result.get("finishedAtUtc") or "")
    try:
        finished_epoch = datetime.fromisoformat(finished.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None, True
    if finished_epoch < submitted - 60:
        return None, True
    return result, False


def cmd_notebook(args: argparse.Namespace) -> None:
    reference = bool(getattr(args, "reference", False))
    if args.action == "check":
        checked = check_notebook(args.name, reference)
        checked["source"] = NOTEBOOKS[args.name]["source"]
        if NOTEBOOKS[args.name]["source"] == "generated":
            checked["spec"] = f"{SPECS}/{args.name}.md"
        print(json.dumps(checked, ensure_ascii=False, indent=2))
        if not checked["passed"]:
            raise LabError("Notebook の約束を満たしていません。problems を直してから、もう一度 check してください。")
        return
    fabric, workspace_id = context()
    output: dict[str, Any] = {"notebook": args.name}
    if args.action in ("deploy", "deploy-run"):
        notebook = deploy_notebook(fabric, workspace_id, args.name, reference)
        output["deployedFrom"] = str(notebook_path(args.name, reference).relative_to(ROOT))
    else:
        notebook = fabric.item(workspace_id, "Notebook", args.name)
    output["link"] = portal_link(workspace_id, "synapsenotebooks", notebook["id"])  # type: ignore[index]
    if args.action in ("run", "deploy-run"):
        run = run_notebook(fabric, workspace_id, notebook, args.name)  # type: ignore[arg-type]
        submitted = run.pop("submittedEpoch")
        output["run"] = run
        if NOTEBOOKS[args.name]["binding"] == "lakehouse":
            output["result"], stale = fresh_result(read_result(fabric, workspace_id, args.name), submitted)
            if stale:
                output["staleResultIgnored"] = "前回の実行の結果ファイルしかないため表示しません（今回の実行は結果を書く前に止まりました）。"
    if args.action == "result":
        output["result"] = read_result(fabric, workspace_id, args.name)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    run = output.get("run") or {}
    result = output.get("result")
    if run and run.get("status") != "Completed":
        hint = ""
        if NOTEBOOKS[args.name]["source"] == "generated":
            hint = (f" result.error（あれば）とリンク先のセル出力でエラーを確認し、work/notebooks の Notebook を直して"
                    f" check → deploy-run をやり直してください。仕様: {SPECS}/{args.name}.md")
        raise LabError(f"Notebook の実行が {run.get('status')} で終了しました。{hint}")
    if isinstance(result, dict) and result.get("passed") is False:
        if NOTEBOOKS[args.name]["source"] == "provided":
            raise LabError("検証 Notebook が期待値との不一致を報告しました。差分は result.checks を参照してください（データは変更していません）。")
        raise LabError("Notebook が自己チェックの失敗を報告しました。result の checks / error を見て、Notebook を直して再実行してください。")


# --------------------------------------------------------------------------- commands: semantic model & ontology


def wh_onelake_expression(name: str, workspace_id: str, warehouse_id: str) -> str:
    return (
        f"expression '{name}' =\n"
        "\t\tlet\n"
        f"\t\t    Source = AzureStorage.DataLake(\"{ONELAKE_DFS}/{workspace_id}/{warehouse_id}\", [HierarchicalNavigation=true])\n"
        "\t\tin\n"
        "\t\t    Source\n"
    )


SM_TABLES: dict[str, list[tuple[str, str, str]]] = {
    # table -> [(column, dataType, extra)] ; extra: "key", "hidden", "date", or ""
    "fact_trips": [
        ("trip_id", "int64", "hidden"), ("VendorID", "int64", "hidden"), ("RatecodeID", "int64", "hidden"),
        ("PULocationID", "int64", "hidden"), ("DOLocationID", "int64", "hidden"), ("payment_type", "int64", "hidden"),
        ("trip_type", "int64", "hidden"), ("lpep_pickup_datetime", "dateTime", ""), ("lpep_dropoff_datetime", "dateTime", ""),
        ("pickup_date", "dateTime", "date"), ("pickup_hour", "int64", ""), ("pickup_month", "string", ""),
        ("passenger_count", "int64", ""), ("passenger_group", "string", ""), ("trip_distance", "double", ""),
        ("trip_duration_minutes", "double", ""), ("fare_amount", "double", ""), ("tip_amount", "double", ""),
        ("tolls_amount", "double", ""), ("total_amount", "double", ""), ("fare_per_mile", "double", ""),
    ],
    "dim_vendor": [("VendorID", "int64", "key"), ("vendor_name", "string", "")],
    "dim_ratecode": [("RatecodeID", "int64", "key"), ("ratecode_name", "string", "")],
    "dim_payment_type": [("payment_type", "int64", "key"), ("payment_type_name", "string", "")],
    "dim_trip_type": [("trip_type", "int64", "key"), ("trip_type_name", "string", "")],
    "dim_pickup_zone": [("LocationID", "int64", "key"), ("pickup_borough", "string", ""), ("pickup_zone", "string", ""), ("pickup_service_zone", "string", "")],
    "dim_dropoff_zone": [("LocationID", "int64", "key"), ("dropoff_borough", "string", ""), ("dropoff_zone", "string", ""), ("dropoff_service_zone", "string", "")],
}
SM_MEASURES = [
    ("Trips", "COUNTROWS(fact_trips)", "#,##0", "Number of trips."),
    ("Total Amount", "SUM(fact_trips[total_amount])", "\\$#,##0.00", "Total amount charged in USD (revenue)."),
    ("Avg Fare", "AVERAGE(fact_trips[fare_amount])", "\\$#,##0.00", "Average metered fare in USD."),
    ("Max Fare", "MAX(fact_trips[fare_amount])", "\\$#,##0.00", "Highest metered fare in USD."),
    ("Avg Trip Distance", "AVERAGE(fact_trips[trip_distance])", "#,##0.00", "Average trip distance in miles."),
]
SM_RELATIONSHIPS = [
    ("fact_trips", "VendorID", "dim_vendor", "VendorID"),
    ("fact_trips", "RatecodeID", "dim_ratecode", "RatecodeID"),
    ("fact_trips", "payment_type", "dim_payment_type", "payment_type"),
    ("fact_trips", "trip_type", "dim_trip_type", "trip_type"),
    ("fact_trips", "PULocationID", "dim_pickup_zone", "LocationID"),
    ("fact_trips", "DOLocationID", "dim_dropoff_zone", "LocationID"),
]


def semantic_model_parts(workspace_id: str, warehouse_id: str) -> list[dict[str, str]]:
    expression = "DirectLake - taxi_warehouse"
    files: dict[str, str] = {
        "definition.pbism": json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2", "settings": {"qnaEnabled": True}}, indent=2),
        "definition/database.tmdl": "database\n\tcompatibilityLevel: 1604\n\tcompatibilityMode: powerBI\n",
        "definition/expressions.tmdl": wh_onelake_expression(expression, workspace_id, warehouse_id) + f"\tlineageTag: {tag('sm', 'expression')}\n",
    }
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3", "\tsourceQueryCulture: en-US", ""]
    for table, columns in SM_TABLES.items():
        model.append(f"ref table {table}")
        lines = [f"table {table}", f"\tlineageTag: {tag('sm', table)}", ""]
        if table == "fact_trips":
            for name, dax, fmt, description in SM_MEASURES:
                lines += [f"\t/// {description}", f"\tmeasure '{name}' = {dax}", f"\t\tformatString: {fmt}",
                          f"\t\tlineageTag: {tag('sm', table, 'measure', name)}", ""]
        for name, data_type, extra in columns:
            lines += [f"\tcolumn {name}", f"\t\tdataType: {data_type}"]
            if extra == "date":
                lines.append("\t\tformatString: yyyy-mm-dd")
            if extra == "hidden":
                lines.append("\t\tisHidden")
            if extra in ("hidden", "key") or data_type == "string" or name in ("pickup_hour",):
                lines.append("\t\tsummarizeBy: none")
            elif data_type in ("int64", "double"):
                lines.append("\t\tsummarizeBy: sum")
            lines += [f"\t\tlineageTag: {tag('sm', table, name)}", f"\t\tsourceColumn: {name}", ""]
        lines += [f"\tpartition {table} = entity", "\t\tmode: directLake", "\t\tsource",
                  f"\t\t\tentityName: {table}", "\t\t\tschemaName: dbo", f"\t\t\texpressionSource: '{expression}'", ""]
        files[f"definition/tables/{table}.tmdl"] = "\n".join(lines)
    files["definition/model.tmdl"] = "\n".join(model) + "\n"
    rels = []
    for from_table, from_col, to_table, to_col in SM_RELATIONSHIPS:
        rels += [f"relationship {tag('sm', 'rel', from_table, from_col)}", f"\tfromColumn: {from_table}.{from_col}",
                 f"\ttoColumn: {to_table}.{to_col}", ""]
    files["definition/relationships.tmdl"] = "\n".join(rels)
    return [{"path": path, "payload": b64(content), "payloadType": "InlineBase64"} for path, content in sorted(files.items())]


ONTOLOGY_TABLES: dict[str, list[tuple[str, str]]] = {
    "onto_trips": [("trip_id", "int64"), ("VendorID", "int64"), ("PULocationID", "int64"), ("DOLocationID", "int64"),
                   ("lpep_pickup_datetime", "dateTime"), ("pickup_date", "dateTime"), ("pickup_hour", "int64"),
                   ("passenger_count", "int64"), ("passenger_group", "string"), ("trip_distance", "double"),
                   ("trip_duration_minutes", "double"), ("fare_amount", "double"), ("tip_amount", "double"),
                   ("total_amount", "double"), ("payment_type_name", "string"), ("trip_type_name", "string")],
    "onto_zones": [("LocationID", "int64"), ("Borough", "string"), ("Zone", "string"), ("service_zone", "string")],
    "onto_vendors": [("VendorID", "int64"), ("vendor_name", "string")],
}
ONTOLOGY_ENTITIES = [
    ("Trip", "onto_trips", "trip_id", "A single NYC green taxi trip in April 2026. total_amount is the revenue in USD."),
    ("Zone", "onto_zones", "LocationID", "A NYC TLC taxi zone. Borough is the NYC borough the zone belongs to."),
    ("Vendor", "onto_vendors", "VendorID", "The technology provider that recorded the trip."),
]
ONTOLOGY_RELATIONSHIPS = [
    # name, from entity, to entity, backing table relationship (from table, col, to table, col), active
    ("pickedUpIn", "Trip", "Zone", ("onto_trips", "PULocationID", "onto_zones", "LocationID"), True),
    ("droppedOffIn", "Trip", "Zone", ("onto_trips", "DOLocationID", "onto_zones", "LocationID"), False),
    ("recordedBy", "Trip", "Vendor", ("onto_trips", "VendorID", "onto_vendors", "VendorID"), True),
]


def ontology_parts(name: str, sql_endpoint: str, sql_endpoint_id: str) -> list[dict[str, str]]:
    files: dict[str, str] = {
        ".platform": json.dumps({
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "Ontology", "displayName": name},
            "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000000"}}, indent=2),
        "database.tmdl": "database\n\tcompatibilityLevel: 1000000\n",
        "expressions.tmdl": (
            "expression DatabaseQuery =\n\t\tlet\n"
            f"\t\t    database = Sql.Database(\"{sql_endpoint}\", \"{sql_endpoint_id}\")\n"
            "\t\tin\n\t\t    database\n"
            f"\tlineageTag: {tag('onto', 'expression')}\n"
        ),
        "namespaces/default.tmdl": "namespace default\n\tlineageTag: default\n",
    }
    model = ["model Model", ""]
    for table, columns in ONTOLOGY_TABLES.items():
        model.append(f"ref table {table}")
        lines = [f"table {table}", f"\tlineageTag: {tag('onto', table)}", ""]
        for column, data_type in columns:
            lines += [f"\tcolumn {column}", f"\t\tdataType: {data_type}", f"\t\tlineageTag: {tag('onto', table, column)}",
                      f"\t\tsourceColumn: {column}", ""]
        lines += [f"\tpartition {table} = entity", "\t\tmode: directLake", "\t\tsource", f"\t\t\tentityName: {table}",
                  "\t\t\tschemaName: dbo", "\t\t\texpressionSource: DatabaseQuery", ""]
        files[f"tables/{table}.tmdl"] = "\n".join(lines)
    model.append("")
    for entity, table, key, description in ONTOLOGY_ENTITIES:
        model.append(f"ref entity {entity}")
        lines = [f"/// {description}", f"entity {entity}", f"\tlineageTag: {tag('onto', 'entity', entity)}",
                 f"\tbackingTable: {table}", f"\tkeyProperty: {key}", ""]
        for column, data_type in ONTOLOGY_TABLES[table]:
            lines += [f"\tproperty {column}", f"\t\tdataType: {data_type}", f"\t\tlineageTag: {tag('onto', entity, column)}", "",
                      "\t\tbackingConfiguration", f"\t\t\tvalueColumn: {table}.{column}", ""]
        files[f"entities/{entity}.tmdl"] = "\n".join(lines)
    model += ["", "ref namespace default", ""]
    files["model.tmdl"] = "\n".join(model)
    relationships, entity_relationships = [], []
    for rel_name, from_entity, to_entity, (from_table, from_col, to_table, to_col), active in ONTOLOGY_RELATIONSHIPS:
        backing = f"rel_{rel_name}"
        relationships += [f"relationship {backing}", f"\tfromColumn: {from_table}.{from_col}", f"\ttoColumn: {to_table}.{to_col}"]
        if not active:
            relationships.append("\tisActive: false")
        relationships.append("")
        entity_relationships += [f"entityRelationship {rel_name}", f"\tlineageTag: {tag('onto', 'relationship', rel_name)}",
                                 f"\tfromEntity: {from_entity}", f"\ttoEntity: {to_entity}", "", "\tbackingConfiguration",
                                 f"\t\trelationship: {backing}", ""]
    files["relationships.tmdl"] = "\n".join(relationships)
    files["entityRelationships.tmdl"] = "\n".join(entity_relationships)
    return [{"path": path, "payload": b64(content), "payloadType": "InlineBase64"} for path, content in sorted(files.items())]


def write_preview(folder: str, parts: list[dict[str, str]]) -> Path:
    target = ROOT / ".lab" / folder
    for part in parts:
        destination = target / part["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(base64.b64decode(part["payload"]))
    return target


def cmd_semantic_model(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    workshop = load_workshop()["items"]
    warehouse = fabric.item(workspace_id, "Warehouse", workshop["warehouse"])
    parts = semantic_model_parts(workspace_id, warehouse["id"])  # type: ignore[index]
    preview = write_preview("semantic-model", parts)
    output: dict[str, Any] = {"preview": str(preview.relative_to(ROOT)), "parts": [p["path"] for p in parts]}
    if args.apply:
        existing = fabric.item(workspace_id, "SemanticModel", workshop["semanticModel"], required=False)
        definition = {"format": "TMDL", "parts": parts}
        if existing:
            status, headers, body = fabric.request("POST", f"/workspaces/{workspace_id}/semanticModels/{existing['id']}/updateDefinition", {"definition": definition})
        else:
            status, headers, body = fabric.request("POST", f"/workspaces/{workspace_id}/semanticModels", {"displayName": workshop["semanticModel"], "definition": definition})
        fabric.lro(status, headers, body)
        model = fabric.item(workspace_id, "SemanticModel", workshop["semanticModel"])
        output["refresh"] = refresh_model(fabric, workspace_id, model["id"])  # type: ignore[index]
        output.update({"semanticModel": workshop["semanticModel"], "id": model["id"],  # type: ignore[index]
                       "link": portal_link(workspace_id, "datasets", model["id"])})  # type: ignore[index]
    print(json.dumps(output, ensure_ascii=False, indent=2))


def refresh_model(fabric: Fabric, workspace_id: str, model_id: str) -> str:
    """Reframe the Direct Lake model so it reads the current Delta tables."""
    base = f"{POWERBI_API}/groups/{workspace_id}/datasets/{model_id}/refreshes"
    fabric.request("POST", base, {"type": "full"}, resource=POWERBI_RESOURCE, expect_json=False)
    for _ in range(60):
        time.sleep(10)
        _, _, history = fabric.request("GET", f"{base}?$top=1", resource=POWERBI_RESOURCE)
        latest = (history.get("value") or [{}])[0]
        if latest.get("status") in ("Completed", "Failed", "Disabled", "Cancelled"):
            if latest["status"] != "Completed":
                raise LabError(f"セマンティックモデルの更新が {latest['status']} になりました。ポータルの更新履歴を確認してください。")
            return "Completed"
    raise LabError("セマンティックモデルの更新が 10 分以内に完了しません。")


MODEL_QUERIES = {
    "kpi": 'EVALUATE ROW("Trips", [Trips], "TotalAmount", [Total Amount], "AvgFare", [Avg Fare], "MaxFare", [Max Fare], "AvgTripDistance", [Avg Trip Distance])',
    "manhattanToBrooklyn": 'EVALUATE CALCULATETABLE(ROW("Trips", [Trips], "TotalAmount", [Total Amount]), dim_pickup_zone[pickup_borough] = "Manhattan", dim_dropoff_zone[dropoff_borough] = "Brooklyn")',
    "byVendor": 'EVALUATE SUMMARIZECOLUMNS(dim_vendor[VendorID], "Trips", [Trips])',
    "byPaymentType": 'EVALUATE SUMMARIZECOLUMNS(dim_payment_type[payment_type], "Trips", [Trips])',
}


def dax(fabric: Fabric, workspace_id: str, model_id: str, query: str) -> list[dict[str, Any]]:
    _, _, body = fabric.request("POST", f"{POWERBI_API}/groups/{workspace_id}/datasets/{model_id}/executeQueries",
                                {"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}},
                                resource=POWERBI_RESOURCE)
    rows = body["results"][0]["tables"][0]["rows"]
    return [{re.sub(r"^.*\[|\]$", "", key): value for key, value in row.items()} for row in rows]


def cmd_model_check(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    expected = json.loads((ROOT / "tests" / "expected" / "expected.json").read_text(encoding="utf-8"))
    model = fabric.item(workspace_id, "SemanticModel", load_workshop()["items"]["semanticModel"])
    results = {name: dax(fabric, workspace_id, model["id"], query) for name, query in MODEL_QUERIES.items()}  # type: ignore[index]
    trips, zones = expected["trips"], expected["zones"]
    kpi, mb = results["kpi"][0], results["manhattanToBrooklyn"][0]
    checks = [
        ("Trips", trips["rows"], kpi["Trips"]),
        ("Total Amount", trips["totalAmount"], round(kpi["TotalAmount"], 2)),
        ("Avg Fare", trips["avgFare"], round(kpi["AvgFare"], 2)),
        ("Max Fare", trips["maxFare"], round(kpi["MaxFare"], 2)),
        ("Avg Trip Distance", trips["avgTripDistance"], round(kpi["AvgTripDistance"], 2)),
        ("Manhattan -> Brooklyn trips", zones["manhattanToBrooklyn"]["trips"], mb["Trips"]),
        ("Manhattan -> Brooklyn amount", zones["manhattanToBrooklyn"]["totalAmount"], round(mb["TotalAmount"], 2)),
        ("Trips by vendor", trips["vendors"], {str(r["VendorID"]): r["Trips"] for r in results["byVendor"]}),
        ("Trips by payment type", trips["paymentTypes"], {str(r["payment_type"]): r["Trips"] for r in results["byPaymentType"] if r["Trips"]}),
    ]
    rows = [{"check": name, "expected": exp, "actual": act, "passed": exp == act} for name, exp, act in checks]
    print(json.dumps({"semanticModel": model["displayName"], "passed": all(r["passed"] for r in rows), "checks": rows},  # type: ignore[index]
                     ensure_ascii=False, indent=2))
    if not all(r["passed"] for r in rows):
        raise LabError("モデルの数値が期待値と一致しません。差分は checks を参照してください。")


def cmd_ontology(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    workshop = load_workshop()["items"]
    lakehouse = fabric.item(workspace_id, "Lakehouse", workshop["lakehouse"])
    endpoint = wait_sql_endpoint(fabric, workspace_id, lakehouse["id"])  # type: ignore[index]
    parts = ontology_parts(workshop["ontology"], endpoint["connectionString"], endpoint["id"])  # type: ignore[index]
    preview = write_preview("ontology", parts)
    output: dict[str, Any] = {"preview": str(preview.relative_to(ROOT)), "parts": [p["path"] for p in parts]}
    if args.apply:
        existing = fabric.item(workspace_id, "Ontology", workshop["ontology"], required=False)
        if existing:
            status, headers, body = fabric.request("POST", f"/workspaces/{workspace_id}/ontologies/{existing['id']}/updateDefinition?updateMetadata=true", {"definition": {"parts": parts}})
        else:
            status, headers, body = fabric.request("POST", f"/workspaces/{workspace_id}/ontologies", {
                "displayName": workshop["ontology"], "description": "NYC green taxi trips, zones and vendors (Lab V4)", "definition": {"parts": parts}})
        fabric.lro(status, headers, body)
        ontology = fabric.item(workspace_id, "Ontology", workshop["ontology"])
        status, headers, body = fabric.request("POST", f"/workspaces/{workspace_id}/ontologies/{ontology['id']}/getDefinition", {})  # type: ignore[index]
        definition = fabric.lro(status, headers, body, want_result=True) or {}
        returned = sorted(p["path"] for p in (definition.get("definition") or {}).get("parts", []))
        output.update({"ontology": workshop["ontology"], "id": ontology["id"], "returnedParts": returned,  # type: ignore[index]
                       "link": portal_link(workspace_id, "ontologies", ontology["id"])})  # type: ignore[index]
    print(json.dumps(output, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- commands: data agents


def mcp_post(url: str, bearer: str, payload: dict[str, Any], session: str | None) -> tuple[dict[str, Any] | None, str | None]:
    headers = {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-03-26"}
    if session:
        headers["Mcp-Session-Id"] = session
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            session = response.headers.get("Mcp-Session-Id") or session
            content_type = (response.headers.get("Content-Type") or "").lower()
            text = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        raise LabError(f"Data Agent MCP が HTTP {error.code} を返しました。Agent が公開済みか、データへのアクセス権があるか確認してください。")
    if "id" not in payload or not ("json" in content_type or "event-stream" in content_type):
        return None, session
    data_lines = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
    messages = [json.loads(line) for line in data_lines if line] if data_lines else [json.loads(text)]
    message = next((m for m in messages if m.get("id") == payload["id"]), messages[-1])
    if message.get("error"):
        raise LabError(f"Data Agent MCP エラー: {message['error'].get('message', '')}")
    return message.get("result") or {}, session


def ask_agent(fabric: Fabric, workspace_id: str, agent_name: str, question: str) -> dict[str, Any]:
    agent = fabric.item(workspace_id, "DataAgent", agent_name)
    url = f"{FABRIC_API}/mcp/workspaces/{workspace_id}/dataagents/{agent['id']}/agent"  # type: ignore[index]
    bearer = token(FABRIC_RESOURCE, fabric.tenant)
    _, session = mcp_post(url, bearer, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "fabric-handson-lab-v4", "version": "4.0"}}}, None)
    mcp_post(url, bearer, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    listed, session = mcp_post(url, bearer, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, session)
    tools = (listed or {}).get("tools") or []
    if not tools:
        raise LabError(f"{agent_name} の MCP ツールが見つかりません。Agent を公開してから再実行してください。")
    tool = tools[0]
    argument = next(iter((tool.get("inputSchema") or {}).get("properties") or {}), None)
    if not argument:
        raise LabError("Data Agent ツールの質問引数を特定できません。")
    started = time.time()
    called, _ = mcp_post(url, bearer, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                       "params": {"name": tool["name"], "arguments": {argument: question}}}, session)
    answer = "\n".join(block.get("text", "") for block in (called or {}).get("content", []) if block.get("type") == "text").strip()
    return {"agent": agent_name, "question": question, "answer": answer, "isError": bool((called or {}).get("isError")),
            "seconds": round(time.time() - started)}


def cmd_agent_ask(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    print(json.dumps(ask_agent(fabric, workspace_id, args.agent, args.question), ensure_ascii=False, indent=2))


def cmd_agent_compare(args: argparse.Namespace) -> None:
    fabric, workspace_id = context()
    workshop = load_workshop()["items"]
    questions = json.loads((ROOT / "tests" / "expected" / "agent_questions.json").read_text(encoding="utf-8"))
    rows = []
    for item in questions:
        row = {"id": item["id"], "question": item["question"], "expected": item["expected"], "answers": {}}
        for agent in (workshop["metricsAgent"], workshop["ontologyAgent"]):
            try:
                result = ask_agent(fabric, workspace_id, agent, item["question"])
                row["answers"][agent] = result["answer"]
            except LabError as error:
                row["answers"][agent] = f"(取得できませんでした: {error})"
        rows.append(row)
    target = ROOT / ".lab" / "agent-comparison.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved": str(target.relative_to(ROOT)), "results": rows}, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description="Fabric Hands-on Lab V4 helper")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Verify sign-in, tenant and workspace; list items")
    check.add_argument("--save", action="store_true", help="Save the verified Workspace ID to the participant file")
    check.set_defaults(func=cmd_check)
    sub.add_parser("ensure-lakehouse").set_defaults(func=cmd_ensure_lakehouse)
    sub.add_parser("ensure-warehouse").set_defaults(func=cmd_ensure_warehouse)
    sub.add_parser("upload-sample").set_defaults(func=cmd_upload_sample)
    sub.add_parser("shortcut").set_defaults(func=cmd_shortcut)
    sub.add_parser("refresh-sql-endpoint").set_defaults(func=cmd_refresh_sql_endpoint)
    notebook = sub.add_parser("notebook", help="Deploy/run a lab notebook as a Fabric item")
    notebook.add_argument("action", choices=["check", "deploy", "run", "deploy-run", "result"],
                          help="check = offline contract check of the notebook file before deploying")
    notebook.add_argument("name", choices=sorted(NOTEBOOKS))
    notebook.add_argument("--reference", action="store_true",
                          help=f"use the answer key in {REFERENCE_NOTEBOOKS}/ instead of the Copilot-generated {GENERATED_NOTEBOOKS}/")
    notebook.set_defaults(func=cmd_notebook)
    model = sub.add_parser("semantic-model", help="Generate (and with --apply deploy) the Direct Lake model")
    model.add_argument("--apply", action="store_true")
    model.set_defaults(func=cmd_semantic_model)
    sub.add_parser("model-check", help="Compare semantic model numbers with tests/expected").set_defaults(func=cmd_model_check)
    ontology = sub.add_parser("ontology", help="Generate (and with --apply deploy) the new-experience ontology")
    ontology.add_argument("--apply", action="store_true")
    ontology.set_defaults(func=cmd_ontology)
    ask = sub.add_parser("agent-ask", help="Ask a published Data Agent through MCP")
    ask.add_argument("agent")
    ask.add_argument("question")
    ask.set_defaults(func=cmd_agent_ask)
    sub.add_parser("agent-compare", help="Ask both agents the standard questions").set_defaults(func=cmd_agent_compare)
    args = parser.parse_args()
    try:
        args.func(args)
    except LabError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
