"""
Diff parser for extracting information from git diff files
"""

import re
from dataclasses import dataclass
from typing import List, Set, Optional
from enum import Enum


class ChangeType(Enum):
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"
    CONTEXT = "context"


@dataclass
class DiffChange:
    """Represents a single line change in a diff"""
    line_number: int
    change_type: ChangeType
    old_line: Optional[str] = None
    new_line: Optional[str] = None


@dataclass
class FileChange:
    """Represents all changes to a single file"""
    filename: str
    old_filename: str
    new_filename: str
    changes: List[DiffChange]


@dataclass
class DiffResult:
    """Result of parsing a diff containing all file changes"""
    file_changes: List[FileChange]


class DiffParser:
    """Parser for git diff format"""
    
    def __init__(self):
        self.file_header_pattern = re.compile(r'^--- a/(.+)$')
        self.new_file_pattern = re.compile(r'^\+\+\+ b/(.+)$')
        self.hunk_header_pattern = re.compile(r'^@@ -(\d+),?\d* \+(\d+),?\d* @@')
        
    def parse(self, diff_content: str) -> DiffResult:
        """
        Parse git diff content into structured format
        
        Args:
            diff_content: String content of git diff
            
        Returns:
            DiffResult containing parsed changes
            
        Raises:
            ValueError: If diff format is invalid
        """
        if not diff_content.strip():
            return DiffResult(file_changes=[])
        
        lines = diff_content.strip().split('\n')
        file_changes = []
        current_file = None
        current_changes = []
        old_line_num = 0
        new_line_num = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check for file header
            old_file_match = self.file_header_pattern.match(line)
            if old_file_match:
                # Save previous file if exists
                if current_file:
                    file_changes.append(FileChange(
                        filename=current_file,
                        old_filename=f"a/{current_file}",
                        new_filename=f"b/{current_file}",
                        changes=current_changes
                    ))
                
                # Start new file
                current_file = old_file_match.group(1)
                current_changes = []
                
                # Skip the next line (should be +++ b/filename)
                i += 1
                if i < len(lines):
                    new_file_match = self.new_file_pattern.match(lines[i])
                    if not new_file_match:
                        raise ValueError("Invalid diff format: expected +++ line after ---")
                
                i += 1
                continue
            
            # Check for hunk header
            hunk_match = self.hunk_header_pattern.match(line)
            if hunk_match:
                old_line_num = int(hunk_match.group(1))
                new_line_num = int(hunk_match.group(2))
                i += 1
                continue
            
            # Process change lines
            if line.startswith('-'):
                # Deletion
                current_changes.append(DiffChange(
                    line_number=old_line_num,
                    change_type=ChangeType.DELETION,
                    old_line=line[1:],  # Remove the - prefix
                    new_line=None
                ))
                old_line_num += 1
                
            elif line.startswith('+'):
                # Addition
                current_changes.append(DiffChange(
                    line_number=new_line_num,
                    change_type=ChangeType.ADDITION,
                    old_line=None,
                    new_line=line[1:]  # Remove the + prefix
                ))
                new_line_num += 1
                
            elif line.startswith(' ') or (not line.startswith('@@') and current_file):
                # Context line (unchanged)
                current_changes.append(DiffChange(
                    line_number=old_line_num,
                    change_type=ChangeType.CONTEXT,
                    old_line=line[1:] if line.startswith(' ') else line,
                    new_line=line[1:] if line.startswith(' ') else line
                ))
                old_line_num += 1
                new_line_num += 1
            
            i += 1
        
        # Save the last file
        if current_file:
            file_changes.append(FileChange(
                filename=current_file,
                old_filename=f"a/{current_file}",
                new_filename=f"b/{current_file}",
                changes=current_changes
            ))
        
        if not file_changes and diff_content.strip():
            raise ValueError("Invalid diff format: no valid file changes found")
        
        # Post-process to detect modifications (paired deletions and additions)
        for file_change in file_changes:
            file_change.changes = self._detect_modifications(file_change.changes)
        
        return DiffResult(file_changes=file_changes)
    
    def _detect_modifications(self, changes: List[DiffChange]) -> List[DiffChange]:
        """
        Convert paired deletions and additions into modifications
        
        Args:
            changes: List of changes to process
            
        Returns:
            List of changes with modifications detected
        """
        processed_changes = []
        i = 0
        
        while i < len(changes):
            current = changes[i]
            
            # Look for deletion followed by addition (modification)
            if (current.change_type == ChangeType.DELETION and 
                i + 1 < len(changes) and 
                changes[i + 1].change_type == ChangeType.ADDITION):
                
                next_change = changes[i + 1]
                # Create modification
                processed_changes.append(DiffChange(
                    line_number=current.line_number,
                    change_type=ChangeType.MODIFICATION,
                    old_line=current.old_line,
                    new_line=next_change.new_line
                ))
                i += 2  # Skip both deletion and addition
            else:
                processed_changes.append(current)
                i += 1
        
        return processed_changes
    
    def extract_identifiers(self, diff_result: DiffResult) -> Set[str]:
        """
        Extract Rust identifiers from diff changes
        
        Args:
            diff_result: Parsed diff result
            
        Returns:
            Set of extracted identifiers
        """
        identifiers = set()
        
        # Pattern to match Rust identifiers
        identifier_pattern = re.compile(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b')
        
        # Rust keywords and common types to include
        rust_keywords = {
            'struct', 'impl', 'fn', 'enum', 'trait', 'mod', 'pub', 'use',
            'let', 'mut', 'const', 'static', 'match', 'if', 'else', 'loop',
            'for', 'while', 'return', 'break', 'continue', 'Self', 'self',
            'i32', 'i64', 'u32', 'u64', 'f32', 'f64', 'bool', 'char', 'str',
            'String', 'Vec', 'Option', 'Result'
        }
        
        for file_change in diff_result.file_changes:
            for change in file_change.changes:
                # Extract from old line
                if change.old_line:
                    found_identifiers = identifier_pattern.findall(change.old_line)
                    identifiers.update(found_identifiers)
                
                # Extract from new line
                if change.new_line:
                    found_identifiers = identifier_pattern.findall(change.new_line)
                    identifiers.update(found_identifiers)
        
        # Filter out very short identifiers and common noise
        filtered_identifiers = {
            identifier for identifier in identifiers
            if len(identifier) >= 1 and not identifier.isdigit()
        }
        
        # Always include relevant Rust keywords found
        filtered_identifiers.update(rust_keywords.intersection(identifiers))
        
        return filtered_identifiers