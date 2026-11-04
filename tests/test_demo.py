import importlib.util
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo.py"


def load_demo():
    spec = importlib.util.spec_from_file_location("demo", DEMO)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_reads_waits_on_publish_refuses_delete(tmp_path):
    log = load_demo().main(tmp_path)
    assert log[0].startswith("DONE      read")
    assert log[1].startswith("WAITING   click 'Publish'")
    assert log[2].startswith("REFUSED   click 'Delete title'")
    assert log[3].startswith("REFUSED   the model approving its own publish")
    assert log[4].startswith("APPROVED  the human pressed the button")
    assert log[5] == "DONE      click 'Publish'"
    assert len(log) == 6
