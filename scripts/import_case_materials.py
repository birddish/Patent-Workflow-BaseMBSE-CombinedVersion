"""Import explicitly selected materials into the master case JSON.

The importer stores extracted text/structure and, for binary inputs, a base64
artifact inside the JSON. Later JSON-only operations never use source_path.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from _case_utils import new_case, now_iso
from validate_case_json import validate as validate_case
from commit_case_patch import apply_one


TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm"}


def docx_extract(path: Path) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    paragraphs: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for index, paragraph in enumerate(root.findall(".//w:body/w:p", ns), start=1):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append({"id": f"PAR-{index:04d}", "text": text, "source": {"file": path.name, "paragraph": index}})
    for table_index, table in enumerate(root.findall(".//w:tbl", ns), start=1):
        rows: list[list[str]] = []
        for row in table.findall("./w:tr", ns):
            rows.append(["".join(node.text or "" for node in cell.findall(".//w:t", ns)).strip() for cell in row.findall("./w:tc", ns)])
        tables.append({"id": f"TBL-{table_index:04d}", "rows": rows, "source": {"file": path.name, "table": table_index}})
    return "\n".join(item["text"] for item in paragraphs), paragraphs, tables


def pdf_extract(path: Path) -> tuple[str, list[dict[str, Any]], str]:
    try:
        import pypdf  # type: ignore
    except ImportError:
        return "", [], "raw_only_pdf_extractor_unavailable"
    reader = pypdf.PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"id": f"PAGE-{index:04d}", "page": index, "text": text, "source": {"file": path.name, "page": index}})
    return "\n".join(item["text"] for item in pages), pages, "extracted"


def read_material(path: Path) -> dict[str, Any]:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    raw = path.read_bytes()
    record: dict[str, Any] = {
        "document_id": f"DOC-{uuid.uuid4().hex[:10].upper()}",
        "name": path.name,
        "media_type": mime,
        "source_path": str(path),
        "imported_at": now_iso(),
        "paragraphs": [],
        "tables": [],
        "figures": [],
        "extraction_status": "raw_only",
    }
    if path.suffix.lower() in TEXT_EXTENSIONS:
        text = raw.decode("utf-8", errors="replace")
        record["text"] = text
        record["extraction_status"] = "extracted"
        record["paragraphs"] = [{"id": "PAR-0001", "text": text, "source": {"file": path.name}}]
        if path.suffix.lower() == ".json":
            try:
                record["structured_payload"] = json.loads(text)
            except json.JSONDecodeError:
                record["structured_payload_error"] = "invalid_json_text"
    elif path.suffix.lower() == ".docx":
        text, paragraphs, tables = docx_extract(path)
        record["text"] = text
        record["paragraphs"] = paragraphs
        record["tables"] = tables
        record["extraction_status"] = "extracted"
    elif path.suffix.lower() == ".pdf":
        text, pages, status = pdf_extract(path)
        record["text"] = text
        record["paragraphs"] = pages
        record["extraction_status"] = status
    else:
        record["figures"] = [{"id": "FIG-0001", "media_type": mime, "source": {"file": path.name}, "ocr_status": "pending"}]
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        record["raw_artifact_ref"] = f"RAW-{uuid.uuid4().hex[:10].upper()}"
        record["raw_artifact_base64"] = base64.b64encode(raw).decode("ascii")
    for collection_name in ("paragraphs", "tables", "figures"):
        for item in record.get(collection_name, []):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                item["id"] = str(record.get("document_id")) + "-" + str(item.get("id"))
    return record


def create_case_exclusive(path: Path, candidate: dict[str, Any]) -> None:
    """Flush a validated new case, then atomically create its name without overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(candidate, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # A hard link has exclusive-create semantics: an existing case.json is
        # never replaced, even if a second importer races after the first check.
        os.link(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--mode", choices=["bootstrap_import"], required=True)
    parser.add_argument("--case-id", default="CASE-001")
    parser.add_argument("--title", default="")
    parser.add_argument("--strategy", choices=["append", "parallel", "replace"], required=True)
    parser.add_argument("--actor", default="user")
    parser.add_argument("--materials-listed", action="store_true", required=True)
    parser.add_argument("--writeback-confirmed", action="store_true", required=True)
    args = parser.parse_args()
    case_path = Path(args.case)
    if case_path.exists():
        print(json.dumps({"committed": False, "status": "blocked", "errors": ["已有 case.json；请使用 reimport_case_materials.py 并提交当前 revision 的权威确认。"]}, ensure_ascii=False, indent=2))
        return 1
    else:
        if args.mode != "bootstrap_import":
            print(json.dumps({"committed": False, "status": "blocked", "errors": ["reimport_material 要求案件主 JSON 已存在。"]}, ensure_ascii=False, indent=2))
            return 1
        case = new_case(args.case_id, args.title)
    control = case.setdefault("control", {})
    batch_number = len(case.setdefault("source_materials", {}).setdefault("import_batches", [])) + 1
    batch_id = f"BATCH-{batch_number:04d}"
    documents = [read_material(Path(file_name)) for file_name in args.files]
    batch = {
        "batch_id": batch_id,
        "transaction_id": f"TX-IMPORT-{uuid.uuid4().hex[:10].upper()}",
        "kind": args.mode,
        "strategy": args.strategy,
        "actor": args.actor,
        "source_files": [str(Path(file_name)) for file_name in args.files],
        "document_ids": [item["document_id"] for item in documents],
        "imported_at": now_iso(),
        "status": "committed",
    }
    source = case.setdefault("source_materials", {})
    source.setdefault("import_batches", []).append(batch)
    source.setdefault("documents", []).extend(documents)
    source.setdefault("raw_artifacts", []).extend([
        {"artifact_id": item["raw_artifact_ref"], "document_id": item["document_id"], "base64": item["raw_artifact_base64"], "media_type": item["media_type"]}
        for item in documents if "raw_artifact_ref" in item
    ])
    for item in documents:
        item.pop("raw_artifact_base64", None)
    case.setdefault("normalized", {}).setdefault("documents", []).extend([
        {
            "id": "NORM-" + item["document_id"],
            "title": item["name"],
            "source_refs": [item["document_id"]],
            "evidence_state": "pending_review",
            "confirmation_state": "unconfirmed",
            "extraction_status": item["extraction_status"],
        }
        for item in documents
    ])
    for item in documents:
        if item["extraction_status"] != "extracted" or any(
            figure.get("ocr_status") == "pending"
            for figure in item.get("figures", [])
            if isinstance(figure, dict)
        ):
            control.setdefault("open_gates", []).append({
                "id": f"GATE-EXTRACT-{item['document_id']}",
                "status": "blocked",
                "document_id": item["document_id"],
                "reason": "材料已保存到主 JSON，但可计算的文本、图形或 OCR 结构尚未完整导入",
                "next_action": "用户明确选择 reimport_material 后补充结构化内容；JSON-only 阶段不得回读原始文件",
            })
    revision = control.get("current_revision", 0) + 1
    control["current_revision"] = revision
    envelope = {
        "patch_id": f"PATCH-BOOTSTRAP-{uuid.uuid4().hex[:10].upper()}",
        "case_id": args.case_id,
        "base_revision": 0,
        "target_absent": True,
        "transaction": "bootstrap_import",
        "view": "import",
        "operation": "create_case_from_materials",
        "actor": args.actor,
        "reason": "用户明文确认首次导入",
        "confirmation_id": f"CONF-BOOTSTRAP-{uuid.uuid4().hex[:10].upper()}",
        "confirmation": {
            "materials_listed": args.materials_listed,
            "writeback_confirmed": args.writeback_confirmed,
            "strategy": args.strategy,
            "source_files": [str(Path(name)) for name in args.files],
            "confirmed_at": now_iso(),
        },
        "expected_affected_entities": [batch_id] + batch["document_ids"] + ["NORM-" + item["document_id"] for item in documents],
        "operations": [
            {"op": "add", "path": "/source_materials/import_batches/-", "value": batch},
            *({"op": "add", "path": "/source_materials/documents/-", "value": item} for item in documents),
            *({"op": "add", "path": "/source_materials/raw_artifacts/-", "value": item} for item in source["raw_artifacts"]),
            *({"op": "add", "path": "/normalized/documents/-", "value": item} for item in case["normalized"]["documents"]),
            *({"op": "add", "path": "/control/open_gates/-", "value": item} for item in control["open_gates"]),
        ],
    }
    # The creation exception still derives its business state from a Patch.
    # Prove the Patch applied to a blank template reproduces the candidate.
    replay = new_case(args.case_id, args.title)
    for operation in envelope["operations"]:
        apply_one(replay, operation)
    if any(replay[key] != case[key] for key in ("source_materials", "normalized")) or replay["control"]["open_gates"] != control["open_gates"]:
        print(json.dumps({"committed": False, "status": "blocked", "errors": ["bootstrap Patch 与候选案件内容不一致"]}, ensure_ascii=False, indent=2))
        return 1
    control.setdefault("transactions", []).append({"transaction_id": batch["transaction_id"], "kind": args.mode, "status": "committed", "base_revision": revision - 1, "result_revision": revision, "batch_id": batch_id, "finished_at": now_iso()})
    control.setdefault("change_log", []).append({"transaction_id": batch["transaction_id"], "revision": revision, "view": "import", "operation": "import_materials", "actor": args.actor, "reason": "用户明确选择外部材料导入", "affected_entities": [batch_id] + batch["document_ids"], "timestamp": now_iso()})
    control["transactions"][-1]["patch_id"] = envelope["patch_id"]
    control["transactions"][-1]["confirmation"] = envelope["confirmation"]
    control["transactions"][-1]["confirmation_id"] = envelope["confirmation_id"]
    control["transactions"][-1]["target_absent"] = True
    control["transactions"][-1]["patch_operation_paths"] = [item["path"] for item in envelope["operations"]]
    control["change_log"][-1]["patch_id"] = envelope["patch_id"]
    errors = validate_case(case)
    if errors:
        print(json.dumps({"committed": False, "status": "blocked", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    try:
        create_case_exclusive(case_path, case)
    except FileExistsError:
        print(json.dumps({"committed": False, "status": "conflict", "errors": ["案件主 JSON 已由另一导入事务创建；拒绝覆盖"]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"committed": True, "status": "committed", "batch_id": batch_id, "document_ids": batch["document_ids"], "result_revision": revision, "extraction_statuses": {item["name"]: item["extraction_status"] for item in documents}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
