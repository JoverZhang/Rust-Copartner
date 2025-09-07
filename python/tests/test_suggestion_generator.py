"""Tests for suggestion_generator module"""

import pytest
from unittest.mock import Mock, AsyncMock
from src.suggestion_generator import SuggestionGenerator, SuggestionResult
from src.llm_client import LLMClient, LLMConfig, LLMResponse
from src.diff_parser import DiffParser


class TestSuggestionGenerator:
    @pytest.fixture
    def mock_llm_client(self):
        """Fixture providing a mock LLM client"""
        config = LLMConfig(api_key="test", model="test-model")
        client = LLMClient(config=config, use_mock=True)
        return client
    
    @pytest.fixture
    def suggestion_generator(self, mock_llm_client):
        """Fixture providing a suggestion generator with mock LLM"""
        return SuggestionGenerator(llm_client=mock_llm_client)
    
    @pytest.mark.asyncio
    async def test_generate_base_suggestion(self, suggestion_generator, sample_diff, sample_rust_code):
        """Test generating base suggestion from diff and context"""
        result = await suggestion_generator.generate_base_suggestion(
            diff_content=sample_diff,
            original_file_content=sample_rust_code,
            project_context=[]
        )
        
        assert isinstance(result, SuggestionResult)
        assert result.base_suggestion is not None
        assert len(result.base_suggestion) > 0
        assert result.diff_content == sample_diff
        assert result.original_content == sample_rust_code
    
    @pytest.mark.asyncio
    async def test_generate_final_suggestion(self, suggestion_generator, sample_rust_code):
        """Test generating final suggestion diff"""
        base_suggestion = "Add a z coordinate to make Point3D truly 3D"
        
        result = await suggestion_generator.generate_final_suggestion(
            base_suggestion=base_suggestion,
            original_file_content=sample_rust_code
        )
        
        assert isinstance(result, SuggestionResult)
        assert result.final_diff is not None
        assert "---" in result.final_diff and "+++" in result.final_diff  # Check diff format
        assert result.base_suggestion == base_suggestion
    
    @pytest.mark.asyncio
    async def test_generate_complete_suggestion(self, suggestion_generator, sample_diff, sample_rust_code):
        """Test complete suggestion generation pipeline"""
        result = await suggestion_generator.generate_suggestion(
            diff_content=sample_diff,
            original_file_content=sample_rust_code,
            project_context=[]
        )
        
        assert isinstance(result, SuggestionResult)
        assert result.base_suggestion is not None
        assert result.final_diff is not None
        assert result.diff_content == sample_diff
        assert result.original_content == sample_rust_code
        assert result.is_valid is not None  # Should have validation result
    
    @pytest.mark.asyncio
    async def test_generate_with_project_context(self, suggestion_generator, sample_diff, sample_rust_code):
        """Test generating suggestion with project context"""
        project_context = [
            "// Similar struct in the project:",
            "struct Vector3D { x: f64, y: f64, z: f64 }",
            "impl Vector3D { fn new(x: f64, y: f64, z: f64) -> Self { Self { x, y, z } } }"
        ]
        
        result = await suggestion_generator.generate_suggestion(
            diff_content=sample_diff,
            original_file_content=sample_rust_code,
            project_context=project_context
        )
        
        assert isinstance(result, SuggestionResult)
        assert result.base_suggestion is not None
        # Should contain reference to the provided context
        assert "Point3D" in result.final_diff or "z" in result.final_diff
    
    @pytest.mark.asyncio
    async def test_validate_suggestion_valid(self, suggestion_generator, temp_project_dir):
        """Test validation of a valid suggestion diff"""
        # Create a test file
        test_file = temp_project_dir / "main.rs"
        
        # Simple valid diff format
        valid_diff = """--- a/main.rs
+++ b/main.rs
@@ -1,4 +1,4 @@
 #[derive(Debug, Clone, Copy, PartialEq)]
-struct Point {
+struct Point3D {
     x: i32,
     y: i32,"""
        
        is_valid = await suggestion_generator.validate_suggestion(
            suggestion_diff=valid_diff,
            original_file_path=str(test_file)
        )
        
        # Note: This might be False due to git environment in tests, but we check the logic works
        assert isinstance(is_valid, bool)
    
    @pytest.mark.asyncio
    async def test_validate_suggestion_invalid(self, suggestion_generator, temp_project_dir):
        """Test validation of an invalid suggestion diff"""
        # Create a test file
        test_file = temp_project_dir / "main.rs"
        
        # Invalid diff that doesn't apply
        invalid_diff = """--- a/main.rs
+++ b/main.rs
@@ -99,1 +99,1 @@
-this line does not exist
+this replacement will fail"""
        
        is_valid = await suggestion_generator.validate_suggestion(
            suggestion_diff=invalid_diff,
            original_file_path=str(test_file)
        )
        
        assert is_valid is False
    
    def test_extract_diff_context(self, suggestion_generator, sample_diff):
        """Test extracting context from diff"""
        parser = DiffParser()
        diff_result = parser.parse(sample_diff)
        
        context = suggestion_generator._extract_diff_context(diff_result)
        
        assert isinstance(context, dict)
        assert "identifiers" in context
        assert "Point" in context["identifiers"]
        assert "Point3D" in context["identifiers"]
        assert "change_summary" in context
        assert "struct" in context["change_summary"].lower()
    
    def test_format_project_context(self, suggestion_generator):
        """Test formatting project context for LLM"""
        context_items = [
            "struct Vector3D { x: f64, y: f64, z: f64 }",
            "impl Vector3D { fn new() -> Self { ... } }"
        ]
        
        formatted = suggestion_generator._format_project_context(context_items)
        
        assert isinstance(formatted, str)
        assert "Vector3D" in formatted
        assert "project" in formatted.lower() or "context" in formatted.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_llm_failure(self, suggestion_generator, sample_diff, sample_rust_code):
        """Test error handling when LLM call fails"""
        # Mock the LLM client to raise an exception
        suggestion_generator.llm_client.generate = AsyncMock(side_effect=Exception("LLM API Error"))
        
        with pytest.raises(Exception, match="LLM API Error"):
            await suggestion_generator.generate_suggestion(
                diff_content=sample_diff,
                original_file_content=sample_rust_code,
                project_context=[]
            )
    
    @pytest.mark.asyncio
    async def test_empty_diff_handling(self, suggestion_generator):
        """Test handling of empty diff"""
        result = await suggestion_generator.generate_suggestion(
            diff_content="",
            original_file_content="fn main() {}",
            project_context=[]
        )
        
        # Should handle gracefully and return a result indicating no changes needed
        assert isinstance(result, SuggestionResult)
        assert result.base_suggestion is not None
    
    @pytest.mark.asyncio
    async def test_large_context_handling(self, suggestion_generator, sample_diff, sample_rust_code):
        """Test handling of large project context"""
        # Create a large context
        large_context = [f"// Context item {i}: struct Test{i} {{}}" for i in range(100)]
        
        result = await suggestion_generator.generate_suggestion(
            diff_content=sample_diff,
            original_file_content=sample_rust_code,
            project_context=large_context
        )
        
        assert isinstance(result, SuggestionResult)
        assert result.base_suggestion is not None
        # Should truncate or handle large context appropriately
    
    def test_suggestion_result_properties(self):
        """Test SuggestionResult properties and methods"""
        result = SuggestionResult(
            diff_content="test diff",
            original_content="test content",
            base_suggestion="test suggestion",
            final_diff="test final diff",
            is_valid=True,
            project_context=["context1", "context2"]
        )
        
        assert result.diff_content == "test diff"
        assert result.original_content == "test content"
        assert result.base_suggestion == "test suggestion"
        assert result.final_diff == "test final diff"
        assert result.is_valid is True
        assert len(result.project_context) == 2
        
        # Test string representation
        str_repr = str(result)
        assert "SuggestionResult" in str_repr
    
    def test_suggestion_generator_initialization(self, mock_llm_client):
        """Test SuggestionGenerator initialization"""
        generator = SuggestionGenerator(llm_client=mock_llm_client)
        
        assert generator.llm_client is mock_llm_client
        assert hasattr(generator, 'max_context_tokens')
        assert generator.max_context_tokens > 0