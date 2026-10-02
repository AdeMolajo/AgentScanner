"""Tests for the scanner module."""

import pytest
import tempfile
from pathlib import Path
from agentscanner.scanner import AgentScanner, ScanResult


def test_scanner_initialization():
    """Test scanner can be initialized."""
    scanner = AgentScanner()
    assert scanner.provider is None
    assert scanner.results == []


def test_scanner_with_provider():
    """Test scanner initialization with provider."""
    scanner = AgentScanner(provider="openai")
    assert scanner.provider == "openai"


def test_scan_result_model():
    """Test ScanResult model."""
    result = ScanResult(agent_path="/path/to/agent")
    assert result.agent_path == "/path/to/agent"
    assert result.issues == []
    assert result.warnings == []


def test_scan_local_file():
    """Test scanning a local file."""
    scanner = AgentScanner()
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Test content for scanning")
        f.flush()
        temp_path = f.name

    try:
        result = scanner.scan(temp_path)
        assert result.agent_path == temp_path
        assert result.info["type"] == "file"
        assert "size" in result.info
        assert "extension" in result.info
    finally:
        Path(temp_path).unlink()


def test_scan_local_directory():
    """Test scanning a local directory."""
    scanner = AgentScanner()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        Path(temp_dir, "test.py").write_text("print('hello')")
        Path(temp_dir, "test.txt").write_text("test content")

        result = scanner.scan(temp_dir)
        assert result.agent_path == temp_dir
        assert result.info["type"] == "directory"
        assert "files" in result.info


def test_analyze_content_sql_injection():
    """Test detection of SQL injection patterns."""
    scanner = AgentScanner()
    result = ScanResult(agent_path="test")
    content = "SELECT * FROM users WHERE id = '1'"

    scanner._analyze_content(content, result)
    assert len(result.warnings) > 0
    assert any(w["type"] == "sql_injection" for w in result.warnings)


def test_analyze_content_hardcoded_secret():
    """Test detection of hardcoded secrets."""
    scanner = AgentScanner()
    result = ScanResult(agent_path="test")
    content = 'api_key = "sk-1234567890"'

    scanner._analyze_content(content, result)
    assert len(result.warnings) > 0
    assert any(w["type"] == "hardcoded_secret" for w in result.warnings)


def test_analyze_content_eval_usage():
    """Test detection of eval usage."""
    scanner = AgentScanner()
    result = ScanResult(agent_path="test")
    content = "result = eval(user_input)"

    scanner._analyze_content(content, result)
    assert len(result.warnings) > 0
    assert any(w["type"] == "eval_usage" for w in result.warnings)


def test_get_results_json():
    """Test JSON output format."""
    scanner = AgentScanner()
    result = ScanResult(agent_path="/test", warnings=[{"type": "test", "message": "test"}])
    scanner.results = [result]

    output = scanner.get_results(format="json")
    assert "/test" in output
    assert "json" not in output.lower() or "test" in output


def test_get_results_markdown():
    """Test Markdown output format."""
    scanner = AgentScanner()
    result = ScanResult(agent_path="/test/path")
    scanner.results = [result]

    output = scanner.get_results(format="markdown")
    assert "/test/path" in output
    assert "##" in output
