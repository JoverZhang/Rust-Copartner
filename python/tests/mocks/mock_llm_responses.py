"""Mock LLM responses for testing"""

# Mock responses for different types of code changes
MOCK_RESPONSES = {
    "struct_rename_point_to_point3d": {
        "base_suggestion": """Based on the diff showing a struct rename from Point to Point3D, I suggest adding a z coordinate to make it truly 3D:

```rust
#[derive(Debug, Clone, Copy, PartialEq)]
struct Point3D {
    x: i32,
    y: i32,
    z: i32,
}

impl Point3D {
    fn new(x: i32, y: i32, z: i32) -> Self {
        Self { x, y, z }
    }
}

fn main() {
    let p = Point3D::new(1, 2, 3);
    println!("p = {:?}", p);
}
```""",
        "final_diff": """--- a/main.rs
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
    },
    "function_rename": {
        "base_suggestion": """The function has been renamed. I suggest updating all references to use the new name consistently.""",
        "final_diff": """--- a/main.rs
+++ b/main.rs
@@ -5,7 +5,7 @@
 }
 
 impl Point {
-    fn new(x: i32, y: i32) -> Self {
+    fn create(x: i32, y: i32) -> Self {
         Self { x, y }
     }
 }"""
    },
    "add_field": {
        "base_suggestion": """A field has been added. I suggest updating the constructor and any relevant methods.""",
        "final_diff": """--- a/main.rs
+++ b/main.rs
@@ -2,6 +2,7 @@
 struct Point {
     x: i32,
     y: i32,
+    z: i32,
 }"""
    },
    "prompt_make_point_3d": {
        "base_suggestion": """To make the Point struct 3D, I need to:

1. Rename the struct to Point3D to reflect its nature
2. Add a z coordinate field to represent the third dimension
3. Update the constructor to accept and initialize the z coordinate
4. Update all references to use the new struct name and constructor signature

Here's the implementation:

```rust
#[derive(Debug, Clone, Copy, PartialEq)]
struct Point3D {
    x: i32,
    y: i32,
    z: i32,
}

impl Point3D {
    fn new(x: i32, y: i32, z: i32) -> Self {
        Self { x, y, z }
    }
}

fn main() {
    let p = Point3D::new(1, 2, 3);
    println!("p = {:?}", p);
}
```

This change transforms the 2D Point into a true 3D point with proper initialization.""",
        "final_diff": """--- a/main.rs
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
    }
}


def get_mock_response(change_type: str, response_type: str = "final_diff") -> str:
    """
    Get a mock LLM response for a specific type of change
    
    Args:
        change_type: Type of change (e.g., "struct_rename_point_to_point3d")
        response_type: Type of response ("base_suggestion" or "final_diff")
    
    Returns:
        Mock response string
    """
    return MOCK_RESPONSES.get(change_type, {}).get(response_type, "No suggestion available")


def mock_llm_call(prompt: str, **kwargs) -> str:
    """
    Mock LLM call that returns appropriate response based on prompt content
    
    Args:
        prompt: The prompt sent to LLM
        **kwargs: Additional arguments (ignored in mock)
    
    Returns:
        Mock response based on prompt analysis
    """
    prompt_lower = prompt.lower()
    
    # Check for prompt mode requests (natural language)
    if "make point struct 3d" in prompt_lower or ("point" in prompt_lower and "3d" in prompt_lower and "change request" in prompt_lower):
        if "step-by-step" in prompt_lower or "explanation" in prompt_lower or "analyze" in prompt_lower:
            return get_mock_response("prompt_make_point_3d", "base_suggestion")
        else:
            return get_mock_response("prompt_make_point_3d", "final_diff")
    
    # Check for diff-based requests (interactive mode)
    elif "point" in prompt_lower and "point3d" in prompt_lower:
        if "base suggestion" in prompt_lower or "suggest" in prompt_lower:
            return get_mock_response("struct_rename_point_to_point3d", "base_suggestion")
        else:
            return get_mock_response("struct_rename_point_to_point3d", "final_diff")
    
    elif "rename" in prompt_lower and "function" in prompt_lower:
        return get_mock_response("function_rename", "final_diff")
    
    elif "add" in prompt_lower and "field" in prompt_lower:
        return get_mock_response("add_field", "final_diff")
    
    # Default response for unrecognized patterns
    return "--- a/main.rs\n+++ b/main.rs\n@@ -1,3 +1,3 @@\n // No specific suggestion available"