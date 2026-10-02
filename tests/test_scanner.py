"""Tests for the scanner module."""

import pytest
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
