"""Tests for diff_parser module"""

import pytest
from src.diff_parser import DiffParser, DiffChange, FileChange, ChangeType


class TestDiffParser:
    def test_parse_simple_diff(self, sample_diff):
        """Test parsing a simple diff with struct rename"""
        parser = DiffParser()
        result = parser.parse(sample_diff)
        
        assert len(result.file_changes) == 1
        file_change = result.file_changes[0]
        assert file_change.filename == "main.rs"
        assert file_change.old_filename == "a/main.rs"
        assert file_change.new_filename == "b/main.rs"
        
        # Find the modification change (not all changes)
        modification_changes = [c for c in file_change.changes if c.change_type == ChangeType.MODIFICATION]
        assert len(modification_changes) == 1
        change = modification_changes[0]
        assert change.line_number == 2
        assert change.old_line == "struct Point {"
        assert change.new_line == "struct Point3D {"
    
    def test_extract_identifiers_from_struct_rename(self, sample_diff):
        """Test extracting identifiers from struct rename diff"""
        parser = DiffParser()
        result = parser.parse(sample_diff)
        identifiers = parser.extract_identifiers(result)
        
        assert "Point" in identifiers
        assert "Point3D" in identifiers
        assert "struct" in identifiers
    
    def test_parse_multi_line_diff(self):
        """Test parsing diff with multiple changes"""
        diff_content = """--- a/main.rs
+++ b/main.rs
@@ -1,10 +1,12 @@
 #[derive(Debug, Clone, Copy, PartialEq)]
-struct Point {
+struct Point3D {
     x: i32,
     y: i32,
+    z: i32,
 }
 
-impl Point {
+impl Point3D {
     fn new(x: i32, y: i32) -> Self {
         Self { x, y }
     }"""
        
        parser = DiffParser()
        result = parser.parse(diff_content)
        
        file_change = result.file_changes[0]
        # Check we have the expected types of changes
        modification_changes = [c for c in file_change.changes if c.change_type == ChangeType.MODIFICATION]
        addition_changes = [c for c in file_change.changes if c.change_type == ChangeType.ADDITION]
        assert len(modification_changes) == 2  # struct and impl renames
        assert len(addition_changes) == 1  # z field addition
        
        # Check struct rename
        struct_change = next(c for c in modification_changes if "struct Point" in c.old_line)
        assert struct_change.old_line.strip() == "struct Point {"
        assert struct_change.new_line.strip() == "struct Point3D {"
        
        # Check impl rename
        impl_change = next(c for c in modification_changes if "impl Point" in c.old_line)
        assert impl_change.old_line.strip() == "impl Point {"
        assert impl_change.new_line.strip() == "impl Point3D {"
    
    def test_parse_addition_diff(self):
        """Test parsing diff with only additions"""
        diff_content = """--- a/main.rs
+++ b/main.rs
@@ -2,6 +2,7 @@
 struct Point {
     x: i32,
     y: i32,
+    z: i32,
 }"""
        
        parser = DiffParser()
        result = parser.parse(diff_content)
        
        file_change = result.file_changes[0]
        additions = [c for c in file_change.changes if c.change_type == ChangeType.ADDITION]
        assert len(additions) == 1
        addition = additions[0]
        assert addition.new_line.strip() == "z: i32,"
        assert addition.old_line is None
    
    def test_parse_deletion_diff(self):
        """Test parsing diff with deletions"""
        diff_content = """--- a/main.rs
+++ b/main.rs
@@ -2,7 +2,6 @@
 struct Point {
     x: i32,
     y: i32,
-    z: i32,
 }"""
        
        parser = DiffParser()
        result = parser.parse(diff_content)
        
        file_change = result.file_changes[0]
        deletions = [c for c in file_change.changes if c.change_type == ChangeType.DELETION]
        assert len(deletions) == 1
        deletion = deletions[0]
        assert deletion.old_line.strip() == "z: i32,"
        assert deletion.new_line is None
    
    def test_extract_identifiers_comprehensive(self):
        """Test comprehensive identifier extraction"""
        diff_content = """--- a/lib.rs
+++ b/lib.rs
@@ -5,8 +5,8 @@
 }
 
-impl Point {
-    fn new(x: i32, y: i32) -> Self {
+impl Point3D {
+    fn create_point(x: i32, y: i32, z: i32) -> Self {
         Self { x, y }
     }
 }"""
        
        parser = DiffParser()
        result = parser.parse(diff_content)
        identifiers = parser.extract_identifiers(result)
        
        # Should extract both old and new identifiers
        expected_identifiers = {
            "Point", "Point3D", "impl", "fn", "new", "create_point", 
            "i32", "Self", "x", "y", "z"
        }
        
        for identifier in expected_identifiers:
            assert identifier in identifiers
    
    def test_empty_diff(self):
        """Test parsing empty diff"""
        parser = DiffParser()
        result = parser.parse("")
        
        assert len(result.file_changes) == 0
    
    def test_invalid_diff_format(self):
        """Test handling invalid diff format"""
        parser = DiffParser()
        
        with pytest.raises(ValueError, match="Invalid diff format"):
            parser.parse("not a valid diff")
    
    def test_multiple_files_diff(self):
        """Test parsing diff with multiple files"""
        diff_content = """--- a/main.rs
+++ b/main.rs
@@ -1,3 +1,3 @@
-struct Point {
+struct Point3D {
     x: i32,
 }
--- a/lib.rs
+++ b/lib.rs
@@ -1,3 +1,3 @@
-fn old_function() {}
+fn new_function() {}"""
        
        parser = DiffParser()
        result = parser.parse(diff_content)
        
        assert len(result.file_changes) == 2
        assert result.file_changes[0].filename == "main.rs"
        assert result.file_changes[1].filename == "lib.rs"