"""
Suggestion generator for creating code suggestions based on diffs and context
"""

import subprocess
import tempfile
import os
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path

from .llm_client import LLMClient
from .diff_parser import DiffParser, DiffResult


@dataclass
class SuggestionResult:
    """Result of suggestion generation"""
    diff_content: str
    original_content: str
    base_suggestion: Optional[str] = None
    final_diff: Optional[str] = None
    is_valid: Optional[bool] = None
    project_context: List[str] = None
    
    def __post_init__(self):
        if self.project_context is None:
            self.project_context = []
    
    def __str__(self) -> str:
        return (f"SuggestionResult(base_suggestion_length={len(self.base_suggestion or '')}, "
                f"final_diff_length={len(self.final_diff or '')}, is_valid={self.is_valid})")


class SuggestionGenerator:
    """
    Generates code suggestions based on diffs and project context using LLM
    """
    
    def __init__(self, llm_client: LLMClient, max_context_tokens: int = 4000):
        self.llm_client = llm_client
        self.max_context_tokens = max_context_tokens
        self.diff_parser = DiffParser()
        self._prompts_dir = Path(__file__).parent.parent / "prompts"
        self._load_prompts()
    
    async def generate_suggestion(
        self,
        diff_content: str,
        original_file_content: str,
        project_context: List[str],
        file_path: Optional[str] = None
    ) -> SuggestionResult:
        """
        Generate complete suggestion including base suggestion and final diff
        
        Args:
            diff_content: Git diff content
            original_file_content: Original file content before changes
            project_context: List of relevant code fragments from project
            
        Returns:
            Complete suggestion result
        """
        # Handle empty diff
        if not diff_content.strip():
            return SuggestionResult(
                diff_content=diff_content,
                original_content=original_file_content,
                base_suggestion="No changes detected in the diff.",
                final_diff="",
                is_valid=True,
                project_context=project_context
            )
        
        # Generate base suggestion
        base_result = await self.generate_base_suggestion(
            diff_content, original_file_content, project_context
        )
        
        # Generate final diff
        final_result = await self.generate_final_suggestion(
            base_result.base_suggestion, original_file_content
        )
        
        # Combine results
        result = SuggestionResult(
            diff_content=diff_content,
            original_content=original_file_content,
            base_suggestion=base_result.base_suggestion,
            final_diff=final_result.final_diff,
            project_context=project_context
        )
        
        # Validate the suggestion
        with tempfile.NamedTemporaryFile(mode='w', suffix='.rs', delete=False) as temp_file:
            temp_file.write(original_file_content)
            temp_file.flush()
            
            try:
                result.is_valid = await self.validate_suggestion(
                    result.final_diff, temp_file.name
                )
            finally:
                os.unlink(temp_file.name)
        
        return result
    
    async def generate_prompt_suggestion(
        self,
        prompt: str,
        original_file_content: str,
        project_context: List[str],
        file_path: Optional[str] = None
    ) -> SuggestionResult:
        """
        Generate complete suggestion based on natural language prompt
        
        Args:
            prompt: Natural language description of desired changes
            original_file_content: Original file content before changes
            project_context: List of relevant code fragments from project
            
        Returns:
            Complete suggestion result
        """
        # Generate base suggestion from prompt
        base_result = await self.generate_base_prompt_suggestion(
            prompt, original_file_content, project_context
        )
        
        # Generate final diff
        final_result = await self.generate_final_suggestion(
            base_result.base_suggestion, original_file_content
        )
        
        # Combine results
        result = SuggestionResult(
            diff_content="",  # No input diff for prompt mode
            original_content=original_file_content,
            base_suggestion=base_result.base_suggestion,
            final_diff=final_result.final_diff,
            project_context=project_context
        )
        
        # Validate the suggestion
        with tempfile.NamedTemporaryFile(mode='w', suffix='.rs', delete=False) as temp_file:
            temp_file.write(original_file_content)
            temp_file.flush()
            
            try:
                result.is_valid = await self.validate_suggestion(
                    result.final_diff, temp_file.name
                )
            finally:
                os.unlink(temp_file.name)
        
        return result
    
    async def generate_base_prompt_suggestion(
        self,
        prompt: str,
        original_file_content: str,
        project_context: List[str]
    ) -> SuggestionResult:
        """
        Generate base suggestion based on natural language prompt
        
        Args:
            prompt: Natural language description of desired changes
            original_file_content: Original file content
            project_context: Relevant code fragments
            
        Returns:
            Result with base suggestion
        """
        # Format context for LLM
        formatted_context = self._format_project_context(project_context)
        
        # Create prompt for base suggestion from natural language
        llm_prompt = self._create_prompt_suggestion_prompt(
            prompt, original_file_content, formatted_context
        )
        
        # Generate base suggestion using LLM
        response = await self.llm_client.generate(
            llm_prompt,
            system_message=self._prompt_suggestion_system,
            temperature=0.3
        )
        
        return SuggestionResult(
            diff_content="",  # No input diff for prompt mode
            original_content=original_file_content,
            base_suggestion=response.content,
            project_context=project_context
        )
    
    async def generate_base_suggestion(
        self,
        diff_content: str,
        original_file_content: str,
        project_context: List[str]
    ) -> SuggestionResult:
        """
        Generate base suggestion based on diff and context
        
        Args:
            diff_content: Git diff content
            original_file_content: Original file content
            project_context: Relevant code fragments
            
        Returns:
            Result with base suggestion
        """
        # Parse diff to extract context
        diff_result = self.diff_parser.parse(diff_content)
        diff_context = self._extract_diff_context(diff_result)
        
        # Format context for LLM
        formatted_context = self._format_project_context(project_context)
        
        # Create prompt for base suggestion
        prompt = self._create_base_suggestion_prompt(
            diff_content, original_file_content, diff_context, formatted_context
        )
        print("📄 Base suggestion prompt:")
        print("-" * 50)
        print(prompt)
        print()
        
        # Generate base suggestion using LLM
        start_time = time.time()
        response = await self.llm_client.generate(
            prompt,
            system_message=self._base_suggestion_system,
            temperature=0.3
        )
        print(f"📄 Base suggestion response {time.time() - start_time}ms:")
        print("-" * 50)
        print(response.content)
        print()
        
        return SuggestionResult(
            diff_content=diff_content,
            original_content=original_file_content,
            base_suggestion=response.content,
            project_context=project_context
        )
    
    async def generate_final_suggestion(
        self,
        base_suggestion: str,
        original_file_content: str
    ) -> SuggestionResult:
        """
        Generate final diff suggestion based on base suggestion
        
        Args:
            base_suggestion: Base suggestion from previous step
            original_file_content: Original file content
            
        Returns:
            Result with final diff
        """
        # Create prompt for final diff generation
        prompt = self._create_final_diff_prompt(base_suggestion, original_file_content)
        print(f"📄 Final diff prompt:")
        print("-" * 50)
        print(prompt)
        print()
        
        # Generate final diff using LLM
        start_time = time.time()
        response = await self.llm_client.generate(
            prompt,
            system_message=self._final_diff_system,
            temperature=0.1  # Lower temperature for more consistent diff format
        )
        print(f"📄 Final diff response {time.time() - start_time}ms:")
        print("-" * 50)
        print(response.content)
        print()

        return SuggestionResult(
            diff_content="",
            original_content=original_file_content,
            base_suggestion=base_suggestion,
            final_diff=response.content
        )
    
    async def validate_suggestion(
        self,
        suggestion_diff: str,
        original_file_path: str
    ) -> bool:
        """
        Validate that the suggestion diff can be applied
        
        Args:
            suggestion_diff: The generated diff
            original_file_path: Path to original file
            
        Returns:
            True if diff is valid and can be applied
        """
        if not suggestion_diff or not suggestion_diff.strip():
            return True  # Empty diff is valid (no changes)
        
        # In mock mode, use simpler validation
        if hasattr(self, 'llm_client') and self.llm_client.use_mock:
            # For mock mode, just check if the diff has the basic git diff format
            lines = suggestion_diff.strip().split('\n')
            has_file_header = any(line.startswith('--- ') for line in lines)
            has_new_file_header = any(line.startswith('+++ ') for line in lines)
            has_hunk_header = any(line.startswith('@@') for line in lines)
            
            return has_file_header and has_new_file_header and has_hunk_header
        
        try:
            # Create temporary patch file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
                patch_file.write(suggestion_diff)
                patch_file.flush()
                
                try:
                    # Use git apply --check to validate the patch
                    result = subprocess.run([
                        'git', 'apply', '--check', '--verbose', patch_file.name
                    ], capture_output=True, text=True, cwd=os.path.dirname(original_file_path))
                    
                    if result.returncode != 0:
                        print(f"❌ Git apply --check failed: {result.stderr}")
                        print(f"original file path: {original_file_path}")
                        print("patch file:")
                        print("-" * 50)
                        print(suggestion_diff)
                        print("-" * 50)

                        return False
                    else:
                        return True
                finally:
                    os.unlink(patch_file.name)
                    
        except Exception:
            # If validation fails for any reason, consider it invalid
            return False
    
    def _extract_diff_context(self, diff_result: DiffResult) -> Dict[str, Any]:
        """Extract relevant context information from parsed diff"""
        identifiers = self.diff_parser.extract_identifiers(diff_result)
        
        # Analyze changes to create summary
        change_types = set()
        changed_items = []
        
        for file_change in diff_result.file_changes:
            for change in file_change.changes:
                if change.change_type.value in ['addition', 'deletion', 'modification']:
                    change_types.add(change.change_type.value)
                    
                    # Extract key changed items
                    if change.old_line:
                        if 'struct' in change.old_line:
                            changed_items.append('struct definition')
                        elif 'impl' in change.old_line:
                            changed_items.append('implementation block')
                        elif 'fn' in change.old_line:
                            changed_items.append('function definition')
        
        change_summary = f"{', '.join(change_types)} in {', '.join(set(changed_items))}" if changed_items else "code modifications"
        
        return {
            "identifiers": identifiers,
            "change_types": list(change_types),
            "change_summary": change_summary,
            "file_count": len(diff_result.file_changes)
        }
    
    def _format_project_context(self, context_items: List[str]) -> str:
        """Format project context for inclusion in LLM prompt"""
        if not context_items:
            return "No additional project context available."
        
        # Limit context to avoid token limits
        limited_context = context_items[:20]  # Limit to first 20 items
        
        formatted = "Relevant code from the project:\n\n"
        for i, item in enumerate(limited_context, 1):
            formatted += f"{i}. {item}\n"
        
        if len(context_items) > 20:
            formatted += f"\n... and {len(context_items) - 20} more items"
        
        return formatted
    
    def _load_prompts(self):
        """Load prompt templates from external files"""
        try:
            self._base_suggestion_template = self._load_prompt_file("base_suggestion.md")
            self._prompt_suggestion_template = self._load_prompt_file("prompt_suggestion.md")
            self._final_diff_template = self._load_prompt_file("final_diff.md")
        except FileNotFoundError:
            # Fallback to embedded templates if files don't exist (for tests)
            self._base_suggestion_template = self._get_fallback_base_suggestion_template()
            self._prompt_suggestion_template = self._get_fallback_prompt_suggestion_template()
            self._final_diff_template = self._get_fallback_final_diff_template()
        
        # Load system messages
        self._base_suggestion_system = "You are a Rust code assistant that helps suggest improvements based on code changes."
        self._prompt_suggestion_system = "You are a Rust code assistant that helps implement changes based on natural language descriptions."
        self._final_diff_system = """You are a Rust code refactoring assistant.  
Your task: given my natural language request, output ONLY a unified diff patch."""
    
    def _load_prompt_file(self, filename: str) -> str:
        """Load a prompt template from file"""
        prompt_file = self._prompts_dir / filename
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        else:
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    
    def _get_fallback_base_suggestion_template(self) -> str:
        """Fallback template for base suggestions"""
        return """I need help analyzing a code change and suggesting improvements.

Here's the original file:
```rust
{original_content}
```

Here's the diff showing the change made:
```diff
{diff_content}
```

Change Summary: {change_summary}
Key identifiers involved: {identifiers}

{formatted_context}

Based on the change shown in the diff and the project context, please suggest what additional improvements or changes would make sense. Consider:
1. Consistency with the change pattern (e.g., if renaming Point to Point3D, consider adding 3D functionality)
2. Related code that should also be updated
3. Best practices for the type of change being made
4. Any potential issues or improvements

IMPORTANT: Your response must start with "FILE: <filename>" where <filename> is the name of the file being modified (e.g., "FILE: main.rs" or "FILE: lib.rs").

Please provide a clear, concise suggestion for what should be changed."""
    
    def _get_fallback_prompt_suggestion_template(self) -> str:
        """Fallback template for prompt suggestions"""
        return """You are tasked with implementing the following change request:

"{prompt}"

Here is the current file content:
```rust
{original_content}
```

{context_section}Please analyze the request and provide a detailed explanation of what changes should be made to implement the requested feature. Consider:

1. What structures, functions, or implementations need to be modified
2. What new code needs to be added
3. How the changes should maintain compatibility with existing code
4. Any imports or dependencies that might be needed

IMPORTANT: Your response must start with "FILE: <filename>" where <filename> is the name of the file being modified (e.g., "FILE: main.rs" or "FILE: lib.rs").

Provide a clear, step-by-step explanation of the changes needed."""
    
    def _get_fallback_final_diff_template(self) -> str:
        """Fallback template for final diff generation"""
        return """Based on this suggestion:

{base_suggestion}

And this original file content:
```rust
{original_content}
```

Please generate a complete git diff that implements the suggested changes. 

IMPORTANT: Extract the filename from the suggestion (it starts with "FILE: <filename>") and use that filename in your diff headers.


Constraints:
- Use the standard diff format starting with `--- a/...` and `+++ b/...`
- Include hunk headers like `@@ -start,count +start,count @@`
- Show added lines prefixed with `+`, removed lines prefixed with `-`, unchanged lines without prefix
- Do not output explanations, comments, or any other text outside the diff

Example request: "Rename struct User to Account and add a new field email: String"
Expected output:
{example}"""
    
    def _create_base_suggestion_prompt(
        self,
        diff_content: str,
        original_content: str,
        diff_context: Dict[str, Any],
        formatted_context: str
    ) -> str:
        """Create prompt for base suggestion generation"""
        return self._base_suggestion_template.format(
            original_content=original_content,
            diff_content=diff_content,
            change_summary=diff_context.get('change_summary', 'code modifications'),
            identifiers=', '.join(list(diff_context.get('identifiers', set()))[:10]),
            formatted_context=formatted_context
        )
    
    def _create_prompt_suggestion_prompt(
        self, 
        prompt: str, 
        original_content: str, 
        formatted_context: str
    ) -> str:
        """Create prompt for generating suggestions from natural language prompts"""
        context_section = f"Relevant project context:\n{formatted_context}\n\n" if formatted_context.strip() else ""
        
        return self._prompt_suggestion_template.format(
            prompt=prompt,
            original_content=original_content,
            context_section=context_section
        )
    
    def _create_final_diff_prompt(self, base_suggestion: str, original_content: str) -> str:
        """Create prompt for final diff generation"""
        example = """--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,10 +1,15 @@
-struct User {
+struct Amount {
     id: i32,
-    name: String,
+    amount: f64,
+    email: String,
 }
 
-impl User {
-    fn new(id: i32, name: String) -> Self {
-        Self { id, name }
+impl Amount {
+    fn new(id: i32, amount: f64, email: String) -> Self {
+        Self { id, amount, email }
     }
+
+    fn get_amount(&self) -> f64 {
+        self.amount
+    }
 }
"""
        return self._final_diff_template.format(
            base_suggestion=base_suggestion,
            original_content=original_content,
            example=example
        )
