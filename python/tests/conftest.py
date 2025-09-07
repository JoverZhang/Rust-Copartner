import pytest
import os
from unittest.mock import Mock
from pathlib import Path


@pytest.fixture
def mock_env():
    """Fixture to provide mock environment variables"""
    return {
        "OPENROUTER_API_KEY": "test-api-key",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENROUTER_MODEL": "deepseek/deepseek-r1:free",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_COLLECTION": "rust-copartner-test",
    }


@pytest.fixture
def sample_diff():
    """Fixture providing a sample diff for testing"""
    return """--- a/main.rs
+++ b/main.rs
@@ -1,5 +1,5 @@
 #[derive(Debug, Clone, Copy, PartialEq)]
-struct Point {
+struct Point3D {
     x: i32,
     y: i32,
 }"""


@pytest.fixture
def sample_rust_code():
    """Fixture providing sample Rust code for testing"""
    return """#[derive(Debug, Clone, Copy, PartialEq)]
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
}"""


@pytest.fixture
def expected_suggestion():
    """Fixture providing expected LLM suggestion for testing"""
    return """--- a/main.rs
+++ b/main.rs
@@ -1,16 +1,17 @@
 #[derive(Debug, Clone, Copy, PartialEq)]
-struct Point {
+struct Point3D {
     x: i32,
     y: i32,
+    z: i32,
 }
 
-impl Point {
-    fn new(x: i32, y: i32) -> Self {
-        Self { x, y }
+impl Point3D {
+    fn new(x: i32, y: i32, z: i32) -> Self {
+        Self { x, y, z }
     }
 }
 
 fn main() {
-    let p = Point::new(1, 2);
+    let p = Point3D::new(1, 2, 3);
     println!("p = {:?}", p);
 }"""


@pytest.fixture
def temp_project_dir(tmp_path):
    """Fixture providing a temporary project directory with sample files"""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    # Create sample main.rs
    main_rs = project_dir / "main.rs"
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
    
    return project_dir