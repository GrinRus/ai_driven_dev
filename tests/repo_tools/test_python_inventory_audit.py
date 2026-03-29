import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests" / "repo_tools" / "python_inventory_audit.py"


def test_python_inventory_audit_writes_report(tmp_path: Path) -> None:
    out_path = tmp_path / "inventory.json"
    result = subprocess.run(
        ["python3", str(SCRIPT), "--out", str(out_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert out_path.exists()

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload.get("schema") == "aidd.python_inventory.v1"
    assert isinstance(payload.get("files"), list)
    assert payload.get("summary", {}).get("total_files", 0) > 0
