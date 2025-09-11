You are tasked with implementing the following change request:

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

Provide a clear, step-by-step explanation of the changes needed.