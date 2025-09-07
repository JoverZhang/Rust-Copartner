"""Tests for workflow module"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from src.workflow import RustCopartnerWorkflow, WorkflowResult
from src.llm_client import LLMClient, LLMConfig


class TestWorkflow:
    @pytest.fixture
    def mock_llm_client(self):
        """Fixture providing a mock LLM client"""
        config = LLMConfig(api_key="test", model="test-model")
        client = LLMClient(config=config, use_mock=True)
        return client
    
    @pytest.fixture
    def workflow(self, mock_llm_client):
        """Fixture providing a workflow with mock LLM"""
        return RustCopartnerWorkflow(llm_client=mock_llm_client)
    
    @pytest.mark.asyncio
    async def test_process_diff_complete_workflow(self, workflow, sample_diff, temp_project_dir):
        """Test complete workflow from diff to suggestion"""
        # Create test files
        main_rs = temp_project_dir / "main.rs"
        main_rs.write_text("""#[derive(Debug, Clone, Copy, PartialEq)]
struct Point {
    x: i32,
    y: i32,
}

impl Point {
    fn new(x: i32, y: i32) -> Self {
        Self { x, y }
    }
}

fn main() {
    let p = Point::new(1, 2);
    println!("p = {:?}", p);
}""")
        
        result = await workflow.process_diff(
            diff_content=sample_diff,
            project_path=str(temp_project_dir)
        )
        
        assert isinstance(result, WorkflowResult)
        assert result.diff_content == sample_diff
        assert result.suggestion_result is not None
        assert result.suggestion_result.base_suggestion is not None
        assert result.suggestion_result.final_diff is not None
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_process_diff_file(self, workflow, sample_diff, temp_project_dir):
        """Test processing diff from file"""
        # Create diff file
        diff_file = temp_project_dir / "last_change.diff"
        diff_file.write_text(sample_diff)
        
        # Create main.rs file
        main_rs = temp_project_dir / "main.rs"
        main_rs.write_text("""#[derive(Debug, Clone, Copy, PartialEq)]
struct Point {
    x: i32,
    y: i32,
}

impl Point {
    fn new(x: i32, y: i32) -> Self {
        Self { x, y }
    }
}

fn main() {
    let p = Point::new(1, 2);
    println!("p = {:?}", p);
}""")
        
        result = await workflow.process_diff_file(
            diff_file_path=str(diff_file),
            project_path=str(temp_project_dir)
        )
        
        assert isinstance(result, WorkflowResult)
        assert result.diff_content == sample_diff
        assert result.suggestion_result is not None
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_collect_project_context(self, workflow, temp_project_dir):
        """Test collecting project context files"""
        # Create multiple rust files
        (temp_project_dir / "lib.rs").write_text("""
pub struct Vector3D {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

impl Vector3D {
    pub fn new(x: f64, y: f64, z: f64) -> Self {
        Self { x, y, z }
    }
}
""")
        
        (temp_project_dir / "utils.rs").write_text("""
pub fn distance(p1: &Point, p2: &Point) -> f64 {
    let dx = p1.x - p2.x;
    let dy = p1.y - p2.y;
    (dx * dx + dy * dy).sqrt()
}
""")
        
        context = await workflow._collect_project_context(str(temp_project_dir), ["Point", "Vector3D"])
        
        assert isinstance(context, list)
        assert len(context) > 0
        # Should contain relevant code snippets
        assert any("Vector3D" in item for item in context)
    
    @pytest.mark.asyncio
    async def test_find_relevant_file(self, workflow, temp_project_dir, sample_diff):
        """Test finding the file that was changed in the diff"""
        # Create main.rs
        main_rs = temp_project_dir / "main.rs"
        main_rs.write_text("struct Point { x: i32, y: i32 }")
        
        file_path = await workflow._find_relevant_file(sample_diff, str(temp_project_dir))
        
        assert file_path is not None
        assert file_path.endswith("main.rs")
        assert Path(file_path).exists()
    
    @pytest.mark.asyncio
    async def test_find_relevant_file_not_found(self, workflow, sample_diff):
        """Test handling when relevant file is not found"""
        # Use a non-existent directory
        
        file_path = await workflow._find_relevant_file(sample_diff, "/nonexistent/path")
        
        assert file_path is None
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_diff_file(self, workflow, temp_project_dir):
        """Test error handling for invalid diff file"""
        # Create invalid diff file
        diff_file = temp_project_dir / "invalid.diff"
        diff_file.write_text("this is not a valid diff")
        
        result = await workflow.process_diff_file(
            diff_file_path=str(diff_file),
            project_path=str(temp_project_dir)
        )
        
        assert isinstance(result, WorkflowResult)
        assert result.success is False
        assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_error_handling_missing_diff_file(self, workflow, temp_project_dir):
        """Test error handling for missing diff file"""
        result = await workflow.process_diff_file(
            diff_file_path=str(temp_project_dir / "nonexistent.diff"),
            project_path=str(temp_project_dir)
        )
        
        assert isinstance(result, WorkflowResult)
        assert result.success is False
        assert result.error_message is not None
        assert "not found" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_llm_failure(self, workflow, sample_diff, temp_project_dir):
        """Test error handling when LLM fails"""
        # Create main.rs
        main_rs = temp_project_dir / "main.rs"
        main_rs.write_text("struct Point { x: i32, y: i32 }")
        
        # Mock LLM to fail
        workflow.llm_client.generate = AsyncMock(side_effect=Exception("LLM API Error"))
        
        result = await workflow.process_diff(
            diff_content=sample_diff,
            project_path=str(temp_project_dir)
        )
        
        assert isinstance(result, WorkflowResult)
        assert result.success is False
        assert "LLM API Error" in result.error_message
    
    @pytest.mark.asyncio
    async def test_workflow_with_empty_project(self, workflow, sample_diff):
        """Test workflow with empty project directory"""
        result = await workflow.process_diff(
            diff_content=sample_diff,
            project_path="/nonexistent/path"
        )
        
        assert isinstance(result, WorkflowResult)
        assert result.success is False
    
    def test_workflow_initialization_default(self, mock_env):
        """Test workflow initialization with default settings"""
        with patch.dict('os.environ', mock_env):
            workflow = RustCopartnerWorkflow.from_env(use_mock=True)
            
            assert workflow.llm_client is not None
            assert workflow.max_context_items > 0
    
    def test_workflow_initialization_custom(self, mock_llm_client):
        """Test workflow initialization with custom client"""
        workflow = RustCopartnerWorkflow(
            llm_client=mock_llm_client,
            max_context_items=50
        )
        
        assert workflow.llm_client is mock_llm_client
        assert workflow.max_context_items == 50
    
    def test_workflow_result_properties(self):
        """Test WorkflowResult properties"""
        result = WorkflowResult(
            diff_content="test diff",
            project_path="/test/path",
            success=True
        )
        
        assert result.diff_content == "test diff"
        assert result.project_path == "/test/path"
        assert result.success is True
        assert result.suggestion_result is None
        assert result.error_message is None
        
        # Test string representation
        str_repr = str(result)
        assert "WorkflowResult" in str_repr
        assert "success=True" in str_repr
    
    @pytest.mark.asyncio
    async def test_rust_file_discovery(self, workflow, temp_project_dir):
        """Test discovery of Rust files in project"""
        # Create nested structure
        src_dir = temp_project_dir / "src"
        src_dir.mkdir()
        
        (src_dir / "main.rs").write_text("fn main() {}")
        (src_dir / "lib.rs").write_text("pub struct Test {}")
        
        tests_dir = temp_project_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "integration.rs").write_text("mod tests {}")
        
        # Create non-rust files (should be ignored)
        (temp_project_dir / "README.md").write_text("# Test")
        (temp_project_dir / "Cargo.toml").write_text("[package]")
        
        rust_files = list(workflow._find_rust_files(str(temp_project_dir)))
        
        assert len(rust_files) >= 3
        assert all(f.endswith('.rs') for f in rust_files)
        assert any("main.rs" in f for f in rust_files)
        assert any("lib.rs" in f for f in rust_files)
        assert any("integration.rs" in f for f in rust_files)
    
    @pytest.mark.asyncio
    async def test_context_filtering_by_relevance(self, workflow, temp_project_dir):
        """Test that context is filtered for relevance"""
        # Create files with varying relevance
        (temp_project_dir / "relevant.rs").write_text("""
struct Point3D {
    x: f64,
    y: f64, 
    z: f64
}
""")
        
        (temp_project_dir / "irrelevant.rs").write_text("""
fn unrelated_function() {
    println!("Hello world");
}
""")
        
        context = await workflow._collect_project_context(
            str(temp_project_dir), 
            ["Point3D", "z"]  # Keywords from our diff
        )
        
        # Should prioritize relevant code
        relevant_items = [item for item in context if "Point3D" in item or "z" in item]
        assert len(relevant_items) > 0