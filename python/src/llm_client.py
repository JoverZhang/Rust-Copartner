"""
LLM client abstraction with mock/real mode toggle
"""

import os
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Union
from openai import OpenAI


@dataclass
class LLMConfig:
    """Configuration for LLM client"""
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "deepseek/deepseek-r1:free"
    timeout: int = 30
    
    @classmethod
    def from_env(cls) -> 'LLMConfig':
        """Create configuration from environment variables"""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        
        return cls(
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1:free"),
            timeout=int(os.getenv("OPENROUTER_TIMEOUT", "30"))
        )


@dataclass
class LLMResponse:
    """Response from LLM"""
    content: str
    model: str
    usage: Dict[str, Any]
    finish_reason: str = "stop"


class LLMClient:
    """
    LLM client with mock/real mode toggle for development and testing
    """
    
    def __init__(self, config: LLMConfig, use_mock: bool = False):
        self.config = config
        self.use_mock = use_mock
        self.openai_client = None
        
        if not use_mock:
            self._initialize_openai_client()
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client for real API calls"""
        self.openai_client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout
        )
    
    @classmethod
    def from_env(cls, use_mock: bool = False) -> 'LLMClient':
        """Create client from environment variables"""
        config = LLMConfig.from_env()
        return cls(config=config, use_mock=use_mock)
    
    def set_mock_mode(self, use_mock: bool):
        """Toggle between mock and real mode"""
        self.use_mock = use_mock
        if not use_mock and self.openai_client is None:
            self._initialize_openai_client()
    
    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate response from LLM
        
        Args:
            prompt: User prompt/query
            system_message: Optional system message to set context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            LLM response
        """
        if self.use_mock:
            return await self._generate_mock_response(
                prompt, system_message, temperature, max_tokens
            )
        else:
            return await self._generate_real_response(
                prompt, system_message, temperature, max_tokens
            )
    
    async def _generate_mock_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate mock response for testing"""
        # Simulate API delay
        await asyncio.sleep(0.01)
        
        # Use mock response based on prompt content
        content = self._get_mock_response(prompt)
        
        return LLMResponse(
            content=content,
            model="mock-model",
            usage={
                "prompt_tokens": self.estimate_tokens(prompt),
                "completion_tokens": self.estimate_tokens(content),
                "total_tokens": self.estimate_tokens(prompt + content)
            },
            finish_reason="stop"
        )
    
    def _get_mock_response(self, prompt: str) -> str:
        """
        Get mock response based on prompt content
        
        Args:
            prompt: The prompt sent to LLM
            
        Returns:
            Mock response based on prompt analysis
        """
        prompt_lower = prompt.lower()
        
        # Check for final diff generation (should return diff format)
        if "git diff" in prompt_lower and "only output the diff format" in prompt_lower:
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
        
        # Analyze prompt to determine appropriate mock response
        if "point" in prompt_lower and "point3d" in prompt_lower:
            if "base suggestion" in prompt_lower or "suggest" in prompt_lower or "analyzing a code change" in prompt_lower:
                return """Based on the diff showing a struct rename from Point to Point3D, I suggest adding a z coordinate to make it truly 3D:

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
```"""
            else:
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
        
        elif "rename" in prompt_lower and "function" in prompt_lower:
            return """--- a/main.rs
+++ b/main.rs
@@ -5,7 +5,7 @@
 }
 
 impl Point {
-    fn new(x: i32, y: i32) -> Self {
+    fn create(x: i32, y: i32) -> Self {
         Self { x, y }
     }
 }"""
        
        elif "add" in prompt_lower and "field" in prompt_lower:
            return """--- a/main.rs
+++ b/main.rs
@@ -2,6 +2,7 @@
 struct Point {
     x: i32,
     y: i32,
+    z: i32,
 }"""
        
        # Default response for unrecognized patterns
        return "--- a/main.rs\n+++ b/main.rs\n@@ -1,3 +1,3 @@\n // No specific suggestion available"
    
    async def _generate_real_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Generate real response from OpenAI API"""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized. Cannot make real API calls.")
        
        # Prepare messages
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        # Make API call
        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            raise Exception(f"LLM API call failed: {str(e)}")
    
    async def batch_generate(
        self,
        prompts: List[str],
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> List[LLMResponse]:
        """
        Generate responses for multiple prompts concurrently
        
        Args:
            prompts: List of prompts to process
            system_message: Optional system message for all prompts
            temperature: Sampling temperature
            max_tokens: Maximum tokens per response
            
        Returns:
            List of LLM responses
        """
        tasks = [
            self.generate(prompt, system_message, temperature, max_tokens)
            for prompt in prompts
        ]
        return await asyncio.gather(*tasks)
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate number of tokens in text (rough approximation)
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 characters per token for English text
        return max(1, len(text) // 4)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "model": self.config.model,
            "base_url": self.config.base_url,
            "mode": "mock" if self.use_mock else "real",
            "timeout": self.config.timeout
        }