"""Read-only verification of rule extraction and preserved source artifacts."""
from pathlib import Path
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET
from docx import Document

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
protocol = json.loads((OUT / "protocol.json").read_text())
for row in protocol["sources"]:
    assert sha(Path(row["path"])) == row["sha256"]
counts = []
for source, name in [("01.body", "implementation"), ("02.body", "transition")]:
    path = BASE / "public-02-sse-rules04" / source
    copy = OUT / "qa-source-copies" / f"{name}.docx"
    assert sha(path) == sha(copy)
    with zipfile.ZipFile(path) as z:
        tree = ET.fromstring(z.read("word/document.xml"))
    paragraphs = ["".join(n.text or "" for n in p.findall(".//w:t", NS)) for p in tree.findall(".//w:body/w:p", NS)]
    assert paragraphs == [p.text for p in Document(copy).paragraphs]
    saved = json.loads((OUT / f"{name}-paragraphs.json").read_text())
    assert paragraphs == [p["text"] for p in saved]
    assert [p["paragraph"] for p in saved] == list(range(1, len(paragraphs) + 1))
    counts.append(len(paragraphs))
    if name == "implementation":
        for r in json.loads((OUT / "rule-evidence.json").read_text()):
            assert r["text"] == paragraphs[r["ooxml_body_paragraph"] - 1]
old_manifest = json.loads((BASE / "sse-chain-v1/output-manifest.json").read_text())
for row in old_manifest["files"]:
    assert sha(BASE / "sse-chain-v1" / row["file"]) == row["sha256"]
policy = json.loads((OUT / "field-admission.json").read_text())
assert policy["known_at"] is None and policy["announced_at"] is None
assert policy["economic_account_admission"] is False
assert policy["official_effective_date_and_route_state"]["admissible_for_development"] is True
assert policy["rule_version"]["effective_from"] == "2024-06-14"
assert policy["rule_version"]["older_version_text_read"] is False
assert policy["account_runs"] == policy["algorithm_changes"] == 0
print(json.dumps({"source_hashes": len(protocol["sources"]), "two_extractor_paragraph_counts": counts, "prior_chain_files_unchanged": len(old_manifest["files"]), "unknown_precise_times_preserved": True, "passed": True}, ensure_ascii=False))
