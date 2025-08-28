"""
Tests for edinet_tools.analysis module - Schema validation only.

Tests the Pydantic schemas used for structured LLM output without
actual LLM calls or token generation.
"""

import pytest
from pydantic import ValidationError

from edinet_tools.analysis import (
    OneLineSummary,
    ExecutiveSummary,
    OneLinerTool, 
    ExecutiveSummaryTool,
    TOOL_MAP
)


class TestPydanticSchemas:
    """Test Pydantic schema validation for LLM responses."""
    
    def test_one_line_summary_valid_data(self):
        """Test OneLineSummary schema with valid data."""
        valid_data = {
            "company_name_en": "TOYOTA MOTOR CORP",
            "summary": "Company reported strong Q4 results with 15% revenue growth."
        }
        summary = OneLineSummary(**valid_data)
        assert summary.company_name_en == "TOYOTA MOTOR CORP"
        assert summary.summary == "Company reported strong Q4 results with 15% revenue growth."
        
        # Test serialization
        json_data = summary.model_dump()
        assert json_data == valid_data
    
    def test_one_line_summary_missing_fields(self):
        """Test OneLineSummary with missing required fields."""
        # Missing company_name_en
        with pytest.raises(ValidationError):
            OneLineSummary(summary="Some summary")
        
        # Missing summary
        with pytest.raises(ValidationError):
            OneLineSummary(company_name_en="TOYOTA MOTOR CORP")
        
        # Both missing
        with pytest.raises(ValidationError):
            OneLineSummary()
    
    def test_one_line_summary_wrong_types(self):
        """Test OneLineSummary with wrong field types."""
        with pytest.raises(ValidationError):
            OneLineSummary(company_name_en=123, summary="Valid summary")
        
        with pytest.raises(ValidationError):
            OneLineSummary(company_name_en="Valid company", summary=456)
    
    def test_one_line_summary_empty_fields(self):
        """Test OneLineSummary with empty string fields - should be allowed."""
        # Empty strings should be allowed by the current schema
        summary1 = OneLineSummary(company_name_en="", summary="Valid summary")
        assert summary1.company_name_en == ""
        
        summary2 = OneLineSummary(company_name_en="Valid company", summary="")
        assert summary2.summary == ""


class TestExecutiveSummarySchema:
    """Test ExecutiveSummary schema validation."""
    
    def test_executive_summary_valid_minimal(self):
        """Test ExecutiveSummary with minimal required fields."""
        valid_data = {
            "company_name_en": "TOYOTA MOTOR CORP",
            "summary": "Toyota announced major EV investment plan.",
            "key_highlights": [
                "¥2 trillion investment over 5 years",
                "20 new EV models by 2030", 
                "Partnership with battery suppliers"
            ]
        }
        
        summary = ExecutiveSummary(**valid_data)
        assert summary.company_name_en == "TOYOTA MOTOR CORP"
        assert summary.summary == "Toyota announced major EV investment plan."
        assert len(summary.key_highlights) == 3
        assert summary.company_description_short is None
        assert summary.potential_impact_rationale is None
    
    def test_executive_summary_with_optional_fields(self):
        """Test ExecutiveSummary with all fields including optional ones."""
        full_data = {
            "company_name_en": "SONY GROUP CORP",
            "company_description_short": "Technology and entertainment conglomerate",
            "summary": "Sony reports strong gaming division growth",
            "key_highlights": [
                "PlayStation revenue up 25%",
                "New console launch successful"
            ],
            "potential_impact_rationale": "Strengthens market position in gaming"
        }
        
        summary = ExecutiveSummary(**full_data)
        assert summary.company_name_en == "SONY GROUP CORP"
        assert summary.company_description_short == "Technology and entertainment conglomerate"
        assert summary.summary == "Sony reports strong gaming division growth"
        assert len(summary.key_highlights) == 2
        assert summary.potential_impact_rationale == "Strengthens market position in gaming"
    
    def test_executive_summary_empty_highlights(self):
        """Test ExecutiveSummary with empty key_highlights list."""
        valid_data = {
            "company_name_en": "TEST CORP",
            "summary": "Summary text",
            "key_highlights": []
        }
        
        summary = ExecutiveSummary(**valid_data)
        assert len(summary.key_highlights) == 0
    
    def test_executive_summary_missing_required_fields(self):
        """Test ExecutiveSummary with missing required fields."""
        # Missing company_name_en
        with pytest.raises(ValidationError):
            ExecutiveSummary(summary="Summary", key_highlights=["Point 1"])
        
        # Missing summary
        with pytest.raises(ValidationError):
            ExecutiveSummary(company_name_en="TEST CORP", key_highlights=["Point 1"])
        
        # Missing key_highlights
        with pytest.raises(ValidationError):
            ExecutiveSummary(company_name_en="TEST CORP", summary="Summary")
    
    def test_executive_summary_key_highlights_validator(self):
        """Test key_highlights field validator that converts strings to lists."""
        # Test string with bullet points gets converted to list
        data_with_string_highlights = {
            "company_name_en": "TEST CORP",
            "summary": "Summary",
            "key_highlights": "\n• Point 1\n• Point 2\n• Point 3"  # Added newline at start for validator
        }
        
        summary = ExecutiveSummary(**data_with_string_highlights)
        assert isinstance(summary.key_highlights, list)
        assert len(summary.key_highlights) >= 2  # Should parse bullet points
        
        # Test string with dashes
        data_with_dashes = {
            "company_name_en": "TEST CORP", 
            "summary": "Summary",
            "key_highlights": "\n- First point\n- Second point"  # Added newline at start for validator
        }
        
        summary2 = ExecutiveSummary(**data_with_dashes)
        assert isinstance(summary2.key_highlights, list)
        assert len(summary2.key_highlights) >= 2
    
    def test_executive_summary_wrong_types(self):
        """Test ExecutiveSummary with wrong field types."""
        base_valid = {
            "company_name_en": "TEST CORP",
            "summary": "Valid summary",
            "key_highlights": ["Point 1"]
        }
        
        # Wrong type for company_name_en
        with pytest.raises(ValidationError):
            ExecutiveSummary(**{**base_valid, "company_name_en": 123})
        
        # Wrong type for summary
        with pytest.raises(ValidationError):
            ExecutiveSummary(**{**base_valid, "summary": 456})
        
        # Wrong type for key_highlights (not string or list)
        with pytest.raises(ValidationError):
            ExecutiveSummary(**{**base_valid, "key_highlights": 789})


class TestToolConfiguration:
    """Test tool class configuration and mapping."""
    
    def test_tool_mapping(self):
        """Test that tools are properly mapped in TOOL_MAP."""
        assert 'one_line_summary' in TOOL_MAP
        assert 'executive_summary' in TOOL_MAP
        
        assert TOOL_MAP['one_line_summary'] == OneLinerTool
        assert TOOL_MAP['executive_summary'] == ExecutiveSummaryTool
    
    def test_one_liner_tool_config(self):
        """Test OneLinerTool configuration."""
        tool = OneLinerTool()
        assert tool.schema_class == OneLineSummary
        assert tool.tool_name == "one_line_summary"
    
    def test_executive_summary_tool_config(self):
        """Test ExecutiveSummaryTool configuration."""
        tool = ExecutiveSummaryTool()
        assert tool.schema_class == ExecutiveSummary
        assert tool.tool_name == "executive_summary"
    
    def test_tool_instantiation(self):
        """Test that tools can be instantiated from TOOL_MAP."""
        for tool_name, tool_class in TOOL_MAP.items():
            tool_instance = tool_class()
            assert hasattr(tool_instance, 'schema_class')
            assert hasattr(tool_instance, 'tool_name')
            assert tool_instance.tool_name == tool_name


class TestSchemaIntegration:
    """Test schema integration scenarios."""
    
    def test_one_liner_format_to_text(self):
        """Test OneLinerTool format_to_text method."""
        tool = OneLinerTool()
        
        schema_object = OneLineSummary(
            company_name_en="TEST CORP",
            summary="Company announced major acquisition for growth"
        )
        
        formatted_text = tool.format_to_text(schema_object)
        assert formatted_text == "Company announced major acquisition for growth"
    
    def test_executive_summary_format_to_text(self):
        """Test ExecutiveSummaryTool format_to_text method."""
        tool = ExecutiveSummaryTool()
        
        schema_object = ExecutiveSummary(
            company_name_en="SONY CORP",
            company_description_short="Entertainment and technology company",
            summary="Strong quarterly results with gaming growth",
            key_highlights=[
                "Gaming revenue up 30%",
                "New product launches successful",
                "Market share expansion in Asia"
            ],
            potential_impact_rationale="Positions for continued growth"
        )
        
        formatted_text = tool.format_to_text(schema_object)
        
        # Check that all components are included
        assert "Company Description: Entertainment and technology company" in formatted_text
        assert "Executive Summary: Strong quarterly results with gaming growth" in formatted_text
        assert "Key Highlights:" in formatted_text
        assert "• Gaming revenue up 30%" in formatted_text
        assert "• New product launches successful" in formatted_text
        assert "• Market share expansion in Asia" in formatted_text
        assert "Potential Impact: Positions for continued growth" in formatted_text
    
    def test_executive_summary_format_minimal(self):
        """Test ExecutiveSummaryTool format_to_text with minimal data."""
        tool = ExecutiveSummaryTool()
        
        schema_object = ExecutiveSummary(
            company_name_en="MINIMAL CORP",
            summary="Brief summary",
            key_highlights=["Single highlight"]
        )
        
        formatted_text = tool.format_to_text(schema_object)
        
        # Should not include optional sections
        assert "Company Description:" not in formatted_text
        assert "Potential Impact:" not in formatted_text
        
        # Should include required sections
        assert "Executive Summary: Brief summary" in formatted_text
        assert "Key Highlights:" in formatted_text
        assert "• Single highlight" in formatted_text


if __name__ == "__main__":
    # Run tests if pytest is available
    try:
        pytest.main([__file__, "-v"])
    except ImportError:
        print("pytest not available. Install with: pip install pytest")
        print("Running basic schema validation...")
        
        # Basic validation tests
        schema = OneLineSummary(company_name_en="Test Corp", summary="Test summary")
        assert schema.summary == "Test summary"
        
        exec_schema = ExecutiveSummary(
            company_name_en="Executive Corp",
            summary="Executive test",
            key_highlights=["Point 1"]
        )
        assert exec_schema.summary == "Executive test"
        
        print("✅ Basic schema validation passed!")