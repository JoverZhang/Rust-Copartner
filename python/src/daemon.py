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
import uuid
import subprocess
import tempfile
import shutil
from pathlib import Path


# Request/Response models
class SuggestionRequest(BaseModel):
    """Request model for suggestion generation"""
    diff_content: str


class SuggestionResponse(BaseModel):
    """Response model for suggestion generation"""
    success: bool
    suggestion: Optional[str] = None
    final_diff: Optional[str] = None
    is_valid: Optional[bool] = None
    requires_confirmation: Optional[bool] = None
    suggestion_id: Optional[str] = None
    error_message: Optional[str] = None
    processing_time_ms: Optional[float] = None


class ApplyRequest(BaseModel):
    """Request model for applying suggestions"""
    suggestion_id: str
    accept: bool


class ApplyResponse(BaseModel):
    """Response model for applying suggestions"""
    success: bool
    message: Optional[str] = None
    files_changed: Optional[list] = None
    backup_files: Optional[list] = None
    error: Optional[str] = None


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

# Global state
workflow: Optional[RustCopartnerWorkflow] = None
project_path: Optional[Path] = None
pending_suggestions: Dict[str, Dict[str, Any]] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize the workflow on startup"""
    global workflow, project_path
    
    # Get project path from environment variable set by main()
    project_path_str = os.getenv("PROJECT_PATH")
    if not project_path_str:
        print("❌ PROJECT_PATH environment variable not set")
        sys.exit(1)
    
    project_path = Path(project_path_str)
    if not project_path.exists():
        print(f"❌ Project directory not found: {project_path}")
        sys.exit(1)
    
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
    global pending_suggestions
    
    if workflow is None or project_path is None:
        raise HTTPException(status_code=503, detail="Workflow not initialized")
    
    if not request.diff_content or not request.diff_content.strip():
        raise HTTPException(status_code=400, detail="diff_content is required")
    
    try:
        import time
        start_time = time.time()
        
        # Log diff content being processed
        print("📄 Processing diff content:")
        print(f"Parsing diff content: {request.diff_content}")
        print("🔄 Generating suggestion...")
        
        # Process diff using the configured project path
        result = await workflow.process_diff(
            diff_content=request.diff_content,
            project_path=str(project_path)
        )
        
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        print(f"⏱️  Processing time: {processing_time:.2f}ms")
        
        # Prepare response
        if result.success and result.suggestion_result:
            print("✅ Suggestion generated successfully!")
            
            # Log the suggestion content
            if result.suggestion_result.base_suggestion:
                print("💡 Suggested improvement:")
                print("-" * 50)
                print(result.suggestion_result.base_suggestion)
                print()
            
            # Log the final diff
            if result.suggestion_result.final_diff:
                print("📝 Suggested changes (diff format):")
                print("-" * 50)
                print(result.suggestion_result.final_diff)
                print()
            
            # Log validation status
            is_valid = result.suggestion_result.is_valid
            if is_valid is not None:
                if is_valid:
                    print("✅ The suggested changes are valid and can be applied")
                else:
                    print("⚠️  The suggested changes may have issues - please review carefully")
                print()
            
            # Generate unique ID for this suggestion
            suggestion_id = str(uuid.uuid4())
            
            # Store suggestion for later application
            pending_suggestions[suggestion_id] = {
                "final_diff": result.suggestion_result.final_diff,
                "timestamp": time.time()
            }
            
            return SuggestionResponse(
                success=True,
                suggestion=result.suggestion_result.base_suggestion,
                final_diff=result.suggestion_result.final_diff,
                is_valid=result.suggestion_result.is_valid,
                requires_confirmation=result.suggestion_result.is_valid,
                suggestion_id=suggestion_id if result.suggestion_result.is_valid else None,
                processing_time_ms=processing_time
            )
        else:
            return SuggestionResponse(
                success=False,
                error_message=result.error_message,
                processing_time_ms=processing_time
            )
    
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000 if 'start_time' in locals() else 0
        return SuggestionResponse(
            success=False,
            error_message=f"Internal server error: {str(e)}",
            processing_time_ms=processing_time
        )


@app.post("/apply", response_model=ApplyResponse)
async def apply_suggestion(request: ApplyRequest):
    """Apply or reject a suggestion"""
    global pending_suggestions
    
    if not request.suggestion_id or request.suggestion_id not in pending_suggestions:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    suggestion_data = pending_suggestions[request.suggestion_id]
    
    try:
        if not request.accept:
            # User rejected the suggestion
            del pending_suggestions[request.suggestion_id]
            return ApplyResponse(
                success=True,
                message="Suggestion rejected by user"
            )
        
        # User accepted - apply the diff
        final_diff = suggestion_data["final_diff"]
        
        if not final_diff or not final_diff.strip():
            del pending_suggestions[request.suggestion_id]
            return ApplyResponse(
                success=True,
                message="No changes to apply (empty diff)",
                files_changed=[]
            )
        
        # Apply the diff using git apply
        result = _apply_diff_to_project(final_diff, project_path)
        
        # Clean up the pending suggestion
        del pending_suggestions[request.suggestion_id]
        
        return result
        
    except Exception as e:
        return ApplyResponse(
            success=False,
            error=f"Failed to apply suggestion: {str(e)}"
        )


def _apply_diff_to_project(diff_content: str, proj_path: Path) -> ApplyResponse:
    """Apply a diff to the project files"""
    try:
        # Extract list of files that will be modified
        files_to_change = _extract_files_from_diff(diff_content)
        
        # Create backups
        backup_files = []
        backup_dir = proj_path / ".rust-copartner-backups"
        backup_dir.mkdir(exist_ok=True)
        
        for file_path in files_to_change:
            full_path = proj_path / file_path
            if full_path.exists():
                import time
                timestamp = int(time.time())
                backup_name = f"{file_path.replace('/', '_')}_{timestamp}.bak"
                backup_path = backup_dir / backup_name
                shutil.copy2(str(full_path), str(backup_path))
                backup_files.append(str(backup_path))
        
        # Create temporary patch file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
            # Ensure diff ends with newline (required by git apply)
            if not diff_content.endswith('\n'):
                diff_content += '\n'
            patch_file.write(diff_content)
            patch_file.flush()
            
            try:
                # First, validate the patch
                result = subprocess.run([
                    'git', 'apply', '--check', '--verbose', patch_file.name
                ], capture_output=True, text=True, cwd=str(proj_path))
                
                if result.returncode != 0:
                    return ApplyResponse(
                        success=False,
                        error="Diff validation failed",
                        message=result.stderr
                    )
                
                # Apply the patch
                result = subprocess.run([
                    'git', 'apply', patch_file.name
                ], capture_output=True, text=True, cwd=str(proj_path))
                
                if result.returncode != 0:
                    return ApplyResponse(
                        success=False,
                        error="Failed to apply diff",
                        message=result.stderr
                    )
                
                return ApplyResponse(
                    success=True,
                    message=f"Successfully applied diff to {len(files_to_change)} file(s)",
                    files_changed=files_to_change,
                    backup_files=backup_files
                )
            
            finally:
                # Clean up temporary patch file
                try:
                    os.unlink(patch_file.name)
                except:
                    pass
    
    except Exception as e:
        return ApplyResponse(
            success=False,
            error=f"Unexpected error applying diff: {str(e)}"
        )


def _extract_files_from_diff(diff_content: str) -> list:
    """Extract list of files being modified from diff content"""
    files = []
    for line in diff_content.split('\n'):
        if line.startswith('--- a/'):
            # Extract file path from git diff format
            file_path = line[6:]  # Remove '--- a/' prefix
            if file_path not in files:
                files.append(file_path)
    return files


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
            "apply": "/apply (POST)",
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