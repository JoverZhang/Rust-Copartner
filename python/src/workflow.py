"""
Main workflow orchestrator for rust-copartner suggestion system
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set
import traceback

from .llm_client import LLMClient
from .diff_parser import DiffParser
from .suggestion_generator import SuggestionGenerator, SuggestionResult


@dataclass
class WorkflowResult:
    """Result of workflow execution"""
    diff_content: str
    project_path: str
    success: bool
    suggestion_result: Optional[SuggestionResult] = None
    error_message: Optional[str] = None
    
    def __str__(self) -> str:
        return (f"WorkflowResult(success={self.success}, "
                f"has_suggestion={self.suggestion_result is not None}, "
                f"error={self.error_message is not None})")


class RustCopartnerWorkflow:
    """
    Main workflow orchestrator that coordinates all components
    """
    
    def __init__(
        self, 
        llm_client: LLMClient,
        max_context_items: int = 30
    ):
        self.llm_client = llm_client
        self.max_context_items = max_context_items
        self.diff_parser = DiffParser()
        self.suggestion_generator = SuggestionGenerator(llm_client)
    
    @classmethod
    def from_env(cls, use_mock: bool = False) -> 'RustCopartnerWorkflow':
        """Create workflow from environment variables"""
        llm_client = LLMClient.from_env(use_mock=use_mock)
        return cls(llm_client=llm_client)
    
    async def process_diff_file(
        self, 
        diff_file_path: str, 
        project_path: str
    ) -> WorkflowResult:
        """
        Process a diff file and generate suggestions
        
        Args:
            diff_file_path: Path to the diff file
            project_path: Path to the project root
            
        Returns:
            Workflow result with suggestions or error
        """
        try:
            # Read diff file
            if not Path(diff_file_path).exists():
                return WorkflowResult(
                    diff_content="",
                    project_path=project_path,
                    success=False,
                    error_message=f"Diff file not found: {diff_file_path}"
                )
            
            with open(diff_file_path, 'r') as f:
                diff_content = f.read()
            
            return await self.process_diff(diff_content, project_path)
            
        except Exception as e:
            return WorkflowResult(
                diff_content="",
                project_path=project_path,
                success=False,
                error_message=f"Error reading diff file: {str(e)}"
            )
    
    async def process_diff(
        self,
        diff_content: str,
        project_path: str
    ) -> WorkflowResult:
        """
        Process diff content and generate suggestions
        
        Args:
            diff_content: Git diff content
            project_path: Path to the project root
            
        Returns:
            Workflow result with suggestions or error
        """
        try:
            # Find the relevant file that was changed
            original_file_path = await self._find_relevant_file(diff_content, project_path)
            if not original_file_path:
                return WorkflowResult(
                    diff_content=diff_content,
                    project_path=project_path,
                    success=False,
                    error_message="Could not find the original file mentioned in the diff"
                )
            
            # Read original file content
            with open(original_file_path, 'r') as f:
                original_content = f.read()
            
            # Parse diff to extract identifiers for context search
            print(f"Parsing diff content: {diff_content}")
            diff_result = self.diff_parser.parse(diff_content)
            identifiers = self.diff_parser.extract_identifiers(diff_result)
            
            # Collect project context
            project_context = await self._collect_project_context(project_path, identifiers)
            
            # Generate suggestions
            suggestion_result = await self.suggestion_generator.generate_suggestion(
                diff_content=diff_content,
                original_file_content=original_content,
                project_context=project_context
            )
            
            return WorkflowResult(
                diff_content=diff_content,
                project_path=project_path,
                success=True,
                suggestion_result=suggestion_result
            )
            
        except Exception as e:
            return WorkflowResult(
                diff_content=diff_content,
                project_path=project_path,
                success=False,
                error_message=f"Workflow error: {str(e)}"
            )
    
    async def _find_relevant_file(self, diff_content: str, project_path: str) -> Optional[str]:
        """
        Find the file that was changed according to the diff
        
        Args:
            diff_content: Git diff content
            project_path: Project root path
            
        Returns:
            Path to the relevant file or None if not found
        """
        try:
            # Parse diff to get file changes
            diff_result = self.diff_parser.parse(diff_content)
            
            for file_change in diff_result.file_changes:
                # Try different possible paths
                possible_paths = [
                    Path(project_path) / file_change.filename,
                    Path(project_path) / "src" / file_change.filename,
                    Path(project_path) / Path(file_change.filename).name
                ]
                
                for path in possible_paths:
                    if path.exists():
                        return str(path)
            
            return None
            
        except Exception:
            return None
    
    async def _collect_project_context(
        self, 
        project_path: str, 
        relevant_identifiers: Set[str]
    ) -> List[str]:
        """
        Collect relevant code context from the project
        
        Args:
            project_path: Project root path
            relevant_identifiers: Identifiers from the diff to search for
            
        Returns:
            List of relevant code snippets
        """
        context = []
        
        try:
            # Find all Rust files in the project
            rust_files = list(self._find_rust_files(project_path))
            
            # Search through files for relevant content
            for file_path in rust_files:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    # Check if file contains any relevant identifiers
                    if self._is_relevant_file(content, relevant_identifiers):
                        relevant_snippets = self._extract_relevant_snippets(
                            content, relevant_identifiers, file_path
                        )
                        context.extend(relevant_snippets)
                        
                except Exception:
                    # Skip files that can't be read
                    continue
            
            # Limit context size
            return context[:self.max_context_items]
            
        except Exception:
            # Return empty context if collection fails
            return []
    
    def _find_rust_files(self, project_path: str):
        """Find all Rust files in the project"""
        project = Path(project_path)
        if not project.exists():
            return []
        
        # Common Rust file locations
        rust_patterns = [
            "**/*.rs"
        ]
        
        rust_files = []
        for pattern in rust_patterns:
            rust_files.extend(project.glob(pattern))
        
        return [str(f) for f in rust_files if f.is_file()]
    
    def _is_relevant_file(self, content: str, identifiers: Set[str]) -> bool:
        """Check if file contains relevant identifiers"""
        content_lower = content.lower()
        
        # Check for exact matches first
        for identifier in identifiers:
            if identifier.lower() in content_lower:
                return True
        
        # Check for partial matches for compound identifiers
        for identifier in identifiers:
            if len(identifier) > 3:  # Only check longer identifiers
                if any(part in content_lower for part in identifier.lower().split('_')):
                    return True
        
        return False
    
    def _extract_relevant_snippets(
        self, 
        content: str, 
        identifiers: Set[str], 
        file_path: str
    ) -> List[str]:
        """Extract relevant code snippets from file content"""
        snippets = []
        lines = content.split('\n')
        
        # Find lines that contain relevant identifiers
        relevant_lines = []
        for i, line in enumerate(lines):
            if any(identifier in line for identifier in identifiers):
                # Include some context around the relevant line
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                
                snippet = '\n'.join(lines[start:end])
                relative_path = Path(file_path).name
                formatted_snippet = f"From {relative_path}:\n{snippet}"
                
                if formatted_snippet not in snippets:
                    snippets.append(formatted_snippet)
        
        # Look for struct/impl/fn blocks that might be relevant
        struct_pattern = re.compile(r'^(pub\s+)?struct\s+(\w+)', re.MULTILINE)
        impl_pattern = re.compile(r'^impl(?:\s*<[^>]*>)?\s+(\w+)', re.MULTILINE)
        fn_pattern = re.compile(r'^(?:pub\s+)?fn\s+(\w+)', re.MULTILINE)
        
        for pattern, block_type in [(struct_pattern, "struct"), (impl_pattern, "impl"), (fn_pattern, "fn")]:
            for match in pattern.finditer(content):
                if match.group(1) in identifiers or (len(match.groups()) > 1 and match.group(2) in identifiers):
                    # Extract the full block
                    start_pos = match.start()
                    line_num = content[:start_pos].count('\n')
                    
                    # Find the end of the block (simplified)
                    brace_count = 0
                    block_lines = []
                    found_opening = False
                    
                    for i in range(line_num, min(line_num + 20, len(lines))):  # Limit block size
                        line = lines[i]
                        block_lines.append(line)
                        
                        if '{' in line:
                            found_opening = True
                            brace_count += line.count('{')
                        if found_opening:
                            brace_count -= line.count('}')
                            if brace_count <= 0:
                                break
                    
                    if block_lines:
                        block_snippet = '\n'.join(block_lines)
                        relative_path = Path(file_path).name
                        formatted_snippet = f"From {relative_path} ({block_type} block):\n{block_snippet}"
                        
                        if formatted_snippet not in snippets:
                            snippets.append(formatted_snippet)
        
        return snippets