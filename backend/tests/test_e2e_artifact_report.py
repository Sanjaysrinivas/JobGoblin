import importlib.util
from pathlib import Path


def _load_report_module():
    path = Path(__file__).parents[2] / "scripts" / "e2e_artifact_report.py"
    spec = importlib.util.spec_from_file_location("e2e_artifact_report", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_matches_resources_created_by_current_e2e_suite():
    report = _load_report_module()

    assert report._matches("Senior Platform Engineer mu3v44nk")
    assert report._matches("E2E Systems mu3v44nk")
    assert report._matches("Primary Resume analysis-mu46bw4j-xsum")
    assert report._matches("Other Resume analysis-mu46bw4j-xsum")
    assert report._matches("E2E User mu3v44nk")
    assert "profile" in report.KINDS
    assert "profile" in report.SINGLETON_KINDS


def test_report_does_not_match_normal_workspace_records():
    report = _load_report_module()

    assert not report._matches("Senior Platform Engineer")
    assert not report._matches("E2E Systems")
    assert not report._matches("Primary Resume")
    assert not report._matches("Real User")
