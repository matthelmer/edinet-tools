"""
Basic tests for llm_analysis_tools.py - LLM analysis functionality.
"""
import pytest
from unittest.mock import patch, MagicMock

from llm_analysis_tools import (
    OneLinerTool,
    ExecutiveSummaryTool,
    OneLineSummary,
    ExecutiveSummary,
    analyze_document_data,
    TOOL_MAP
)


class TestPydanticSchemas:
    """Basic tests for Pydantic schemas."""

    def test_one_line_summary_creation(self):
        """Test OneLineSummary can be created."""
        summary = OneLineSummary(
            company_name_en="Test Company",
            summary="Test summary"
        )
        assert summary.company_name_en == "Test Company"
        assert summary.summary == "Test summary"

    def test_executive_summary_creation(self):
        """Test ExecutiveSummary can be created."""
        summary = ExecutiveSummary(
            company_name_en="TEST COMPANY",
            summary="Strategic analysis",
            key_highlights=["Point 1", "Point 2"]
        )
        assert summary.company_name_en == "TEST COMPANY"
        assert len(summary.key_highlights) == 2


class TestOneLinerTool:
    """Basic tests for OneLinerTool."""

    def test_tool_initialization(self):
        """Test tool can be initialized."""
        tool = OneLinerTool()
        assert tool.schema_class == OneLineSummary
        assert tool.tool_name == "one_line_summary"

    def test_create_prompt_basic(self, sample_structured_data):
        """Test prompt creation doesn't crash."""
        tool = OneLinerTool()
        prompt = tool.create_prompt(sample_structured_data)

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_format_to_text(self):
        """Test formatting works."""
        tool = OneLinerTool()
        schema_obj = OneLineSummary(
            company_name_en="Test Company",
            summary="Test summary"
        )

        result = tool.format_to_text(schema_obj)
        assert result == "Test summary"


class TestExecutiveSummaryTool:
    """Basic tests for ExecutiveSummaryTool."""

    def test_tool_initialization(self):
        """Test tool can be initialized."""
        tool = ExecutiveSummaryTool()
        assert tool.schema_class == ExecutiveSummary
        assert tool.tool_name == "executive_summary"

    def test_create_prompt_basic(self, sample_structured_data):
        """Test prompt creation doesn't crash."""
        tool = ExecutiveSummaryTool()
        prompt = tool.create_prompt(sample_structured_data)

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_format_to_text_basic(self):
        """Test basic formatting."""
        tool = ExecutiveSummaryTool()
        schema_obj = ExecutiveSummary(
            company_name_en="TEST COMPANY",
            summary="Test analysis",
            key_highlights=["Point 1"]
        )

        result = tool.format_to_text(schema_obj)
        assert "Test analysis" in result
        assert "Point 1" in result


class TestAnalyzeDocumentData:
    """Basic tests for analyze_document_data function."""

    def test_invalid_tool_name(self, sample_structured_data):
        """Test with invalid tool name."""
        result = analyze_document_data(sample_structured_data, "invalid_tool")
        assert "Error: Unknown analysis tool" in result

    def test_valid_tool_names(self):
        """Test that valid tool names exist in TOOL_MAP."""
        assert "one_line_summary" in TOOL_MAP
        assert "executive_summary" in TOOL_MAP

    @patch.dict('llm_analysis_tools.TOOL_MAP')
    def test_tool_instantiation(self, sample_structured_data):
        """Test that tools are instantiated correctly."""
        # Create a mock tool class
        mock_tool_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.generate_formatted_text.return_value = "Test result"
        mock_tool_class.return_value = mock_instance

        # Patch the TOOL_MAP to use our mock
        TOOL_MAP["one_line_summary"] = mock_tool_class

        result = analyze_document_data(sample_structured_data, "one_line_summary")

        mock_tool_class.assert_called_once()
        mock_instance.generate_formatted_text.assert_called_once_with(sample_structured_data)
        assert result == "Test result"


class TestToolMap:
    """Basic tests for TOOL_MAP configuration."""

    def test_tool_map_not_empty(self):
        """Test TOOL_MAP contains tools."""
        assert len(TOOL_MAP) > 0

    def test_expected_tools_present(self):
        """Test expected tools are in TOOL_MAP."""
        expected_tools = ["one_line_summary", "executive_summary"]
        for tool_name in expected_tools:
            assert tool_name in TOOL_MAP

    def test_tools_are_classes(self):
        """Test TOOL_MAP values are classes."""
        for tool_name, tool_class in TOOL_MAP.items():
            assert callable(tool_class)
            # Should be able to instantiate
            instance = tool_class()
            assert hasattr(instance, 'tool_name')


class TestBasicIntegration:
    """Basic integration tests."""

    def test_tools_handle_empty_data(self):
        """Test tools handle empty structured data."""
        empty_data = {}

        for tool_name in TOOL_MAP.keys():
            tool_instance = TOOL_MAP[tool_name]()
            try:
                # Should not crash on empty data
                prompt = tool_instance.create_prompt(empty_data)
                assert isinstance(prompt, str)
            except Exception as e:
                pytest.fail(f"Tool {tool_name} failed with empty data: {e}")

    def test_tools_handle_minimal_data(self):
        """Test tools handle minimal structured data."""
        minimal_data = {"doc_id": "TEST123"}

        for tool_name in TOOL_MAP.keys():
            tool_instance = TOOL_MAP[tool_name]()
            try:
                prompt = tool_instance.create_prompt(minimal_data)
                assert isinstance(prompt, str)
                assert len(prompt) > 0
            except Exception as e:
                pytest.fail(f"Tool {tool_name} failed with minimal data: {e}")
