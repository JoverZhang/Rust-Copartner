"""
FastAPI daemon for rust-copartner suggestion service
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from .workflow import RustCopartnerWorkflow, WorkflowResult


# Request/Response models
class SuggestionRequest(BaseModel):
    """Request model for suggestion generation"""
    diff_content: Optional[str] = None
    diff_file_path: Optional[str] = None
    project_path: str
    use_mock: bool = False


class SuggestionResponse(BaseModel):
    """Response model for suggestion generation"""
    success: bool
    suggestion: Optional[str] = None
    final_diff: Optional[str] = None
    is_valid: Optional[bool] = None
    error_message: Optional[str] = None
    processing_time_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    llm_mode: str


# Initialize FastAPI app
app = FastAPI(
    title="Rust Copartner API",
    description="API for generating Rust code suggestions based on diffs",
    version="0.1.0"
)

# Global workflow instance
workflow: Optional[RustCopartnerWorkflow] = None


@app.on_event("startup")
async def startup_event():
    """Initialize the workflow on startup"""
    global workflow
    
    # Check if we should use mock mode (for development/testing)
    use_mock = os.getenv("USE_MOCK_LLM", "false").lower() == "true"
    
    try:
        if use_mock:
            # In mock mode, create a dummy config if env vars are missing
            try:
                workflow = RustCopartnerWorkflow.from_env(use_mock=use_mock)
            except ValueError:
                # Create with dummy config for mock mode
                from .llm_client import LLMConfig, LLMClient
                config = LLMConfig(api_key="mock-key", model="mock-model")
                llm_client = LLMClient(config=config, use_mock=True)
                workflow = RustCopartnerWorkflow(llm_client=llm_client)
        else:
            workflow = RustCopartnerWorkflow.from_env(use_mock=use_mock)
            
        print(f"🚀 Rust Copartner daemon started with LLM mode: {'mock' if workflow.llm_client.use_mock else 'real'}")
    except Exception as e:
        print(f"❌ Failed to initialize workflow: {e}")
        sys.exit(1)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if workflow is None:
        raise HTTPException(status_code=503, detail="Workflow not initialized")
    
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        llm_mode="mock" if workflow.llm_client.use_mock else "real"
    )


@app.post("/suggest", response_model=SuggestionResponse)
async def generate_suggestion(request: SuggestionRequest):
    """Generate code suggestion based on diff"""
    if workflow is None:
        raise HTTPException(status_code=503, detail="Workflow not initialized")
    
    # Validate request
    if not request.diff_content and not request.diff_file_path:
        raise HTTPException(
            status_code=400, 
            detail="Either diff_content or diff_file_path must be provided"
        )
    
    if not request.project_path or not Path(request.project_path).exists():
        raise HTTPException(
            status_code=400,
            detail=f"Project path does not exist: {request.project_path}"
        )
    
    try:
        import time
        start_time = time.time()
        
        # Toggle mock mode if requested
        original_mock_mode = workflow.llm_client.use_mock
        if request.use_mock != original_mock_mode:
            workflow.llm_client.set_mock_mode(request.use_mock)
        
        try:
            # Process diff
            if request.diff_content:
                result = await workflow.process_diff(
                    diff_content=request.diff_content,
                    project_path=request.project_path
                )
            else:
                result = await workflow.process_diff_file(
                    diff_file_path=request.diff_file_path,
                    project_path=request.project_path
                )
            
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Prepare response
            if result.success and result.suggestion_result:
                return SuggestionResponse(
                    success=True,
                    suggestion=result.suggestion_result.base_suggestion,
                    final_diff=result.suggestion_result.final_diff,
                    is_valid=result.suggestion_result.is_valid,
                    processing_time_ms=processing_time
                )
            else:
                return SuggestionResponse(
                    success=False,
                    error_message=result.error_message,
                    processing_time_ms=processing_time
                )
        
        finally:
            # Restore original mock mode
            if request.use_mock != original_mock_mode:
                workflow.llm_client.set_mock_mode(original_mock_mode)
    
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000 if 'start_time' in locals() else 0
        return SuggestionResponse(
            success=False,
            error_message=f"Internal server error: {str(e)}",
            processing_time_ms=processing_time
        )


@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "service": "rust-copartner",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "suggest": "/suggest (POST)",
            "docs": "/docs"
        }
    }


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app"""
    return app


def main():
    """Main entry point for the daemon"""
    parser = argparse.ArgumentParser(description="Rust Copartner Daemon")
    parser.add_argument(
        "project_dir",
        help="Project directory to analyze"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=9876,
        help="Port to run the server on (default: 9876)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM for development/testing"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    
    args = parser.parse_args()
    
    # Validate project directory
    project_path = Path(args.project_dir).resolve()
    if not project_path.exists():
        print(f"❌ Project directory not found: {project_path}")
        sys.exit(1)
    
    # Set environment variables for the workflow
    os.environ["PROJECT_PATH"] = str(project_path)
    if args.mock:
        os.environ["USE_MOCK_LLM"] = "true"
    
    print(f"🔧 Starting Rust Copartner daemon")
    print(f"📁 Project directory: {project_path}")
    print(f"🌐 Server will run on http://{args.host}:{args.port}")
    print(f"🤖 LLM mode: {'mock' if args.mock else 'real'}")
    print(f"📚 API docs available at: http://{args.host}:{args.port}/docs")
    
    # Run the server
    uvicorn.run(
        "src.daemon:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()