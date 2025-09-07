"""
Client for rust-copartner suggestion service
"""

import sys
import argparse
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

import httpx


class RustCopartnerClient:
    """Client for communicating with rust-copartner daemon"""
    
    def __init__(self, base_url: str = "http://localhost:9876", timeout: float = 30.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if the daemon is healthy"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
    
    async def suggest_from_content(
        self, 
        diff_content: str, 
        project_path: str,
        use_mock: bool = False
    ) -> Dict[str, Any]:
        """Generate suggestions from diff content"""
        payload = {
            "diff_content": diff_content,
            "project_path": project_path,
            "use_mock": use_mock
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/suggest", json=payload)
            response.raise_for_status()
            return response.json()
    
    async def suggest_from_file(
        self, 
        diff_file_path: str, 
        project_path: str,
        use_mock: bool = False
    ) -> Dict[str, Any]:
        """Generate suggestions from diff file"""
        payload = {
            "diff_file_path": diff_file_path,
            "project_path": project_path,
            "use_mock": use_mock
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/suggest", json=payload)
            response.raise_for_status()
            return response.json()
    
    def apply_diff(self, diff_content: str, project_path: str, dry_run: bool = False, backup: bool = True) -> Dict[str, Any]:
        """Apply a diff to the project files
        
        Args:
            diff_content: The diff content to apply
            project_path: Path to the project directory
            dry_run: If True, only validate the diff without applying it
            backup: If True, create backup files before applying changes
            
        Returns:
            Dict with success status and details
        """
        if not diff_content or not diff_content.strip():
            return {
                "success": True,
                "message": "No changes to apply (empty diff)",
                "files_changed": []
            }
        
        project_path = Path(project_path).resolve()
        if not project_path.exists():
            return {
                "success": False,
                "error": f"Project path does not exist: {project_path}"
            }
        
        try:
            # Create temporary patch file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
                patch_file.write(diff_content + '\n')
                patch_file.flush()
                
                try:
                    # First, validate the patch
                    result = subprocess.run([
                        'git', 'apply', '--check', '--verbose', patch_file.name
                    ], capture_output=True, text=True, cwd=str(project_path))
                    
                    if result.returncode != 0:
                        return {
                            "success": False,
                            "error": "Diff validation failed",
                            "details": result.stderr
                        }
                    
                    if dry_run:
                        return {
                            "success": True,
                            "message": "Diff is valid and can be applied",
                            "dry_run": True
                        }
                    
                    # Extract list of files that will be modified
                    files_to_change = self._extract_files_from_diff(diff_content)
                    
                    # Create backups if requested
                    backup_files = []
                    if backup and files_to_change:
                        backup_dir = project_path / ".rust-copartner-backups"
                        backup_dir.mkdir(exist_ok=True)
                        
                        for file_path in files_to_change:
                            full_path = project_path / file_path
                            if full_path.exists():
                                timestamp = subprocess.run(['date', '+%Y%m%d_%H%M%S'], 
                                                         capture_output=True, text=True).stdout.strip()
                                backup_name = f"{file_path.replace('/', '_')}_{timestamp}.bak"
                                backup_path = backup_dir / backup_name
                                shutil.copy2(str(full_path), str(backup_path))
                                backup_files.append(str(backup_path))
                    
                    # Apply the patch
                    result = subprocess.run([
                        'git', 'apply', patch_file.name
                    ], capture_output=True, text=True, cwd=str(project_path))
                    
                    if result.returncode != 0:
                        return {
                            "success": False,
                            "error": "Failed to apply diff",
                            "details": result.stderr,
                            "backup_files": backup_files
                        }
                    
                    return {
                        "success": True,
                        "message": f"Successfully applied diff to {len(files_to_change)} file(s)",
                        "files_changed": files_to_change,
                        "backup_files": backup_files
                    }
                
                finally:
                    # Clean up temporary patch file
                    try:
                        os.unlink(patch_file.name)
                    except:
                        pass
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error applying diff: {str(e)}"
            }
    
    def _extract_files_from_diff(self, diff_content: str) -> List[str]:
        """Extract list of files being modified from diff content"""
        files = []
        for line in diff_content.split('\n'):
            if line.startswith('--- a/'):
                # Extract file path from git diff format
                file_path = line[6:]  # Remove '--- a/' prefix
                if file_path not in files:
                    files.append(file_path)
        return files


def print_suggestion_result(result: Dict[str, Any], show_timing: bool = True):
    """Print suggestion result in a user-friendly format"""
    if result.get("success"):
        print("✅ Suggestion generated successfully!")
        print()
        
        # Print base suggestion if available
        if result.get("suggestion"):
            print("💡 Suggested improvement:")
            print("-" * 50)
            print(result["suggestion"])
            print()
        
        # Print final diff if available
        if result.get("final_diff"):
            print("📝 Suggested changes (diff format):")
            print("-" * 50)
            print(result["final_diff"])
            print()
        
        # Print validation status
        is_valid = result.get("is_valid")
        if is_valid is not None:
            if is_valid:
                print("✅ The suggested changes are valid and can be applied")
            else:
                print("⚠️  The suggested changes may have issues - please review carefully")
            print()
        
        # Print timing information
        if show_timing and result.get("processing_time_ms"):
            print(f"⏱️  Processing time: {result['processing_time_ms']:.2f}ms")
            print()
    
    else:
        print("❌ Failed to generate suggestion:")
        print(f"Error: {result.get('error_message', 'Unknown error')}")
        
        if show_timing and result.get("processing_time_ms"):
            print(f"Processing time: {result['processing_time_ms']:.2f}ms")


def ask_user_confirmation(suggestion_diff: str) -> bool:
    """Ask user if they want to accept the suggestion"""
    print("Accept? (y/n): ", end="", flush=True)
    response = input().strip().lower()
    return response in ['y', 'yes']


async def main():
    """Main client entry point"""
    parser = argparse.ArgumentParser(description="Rust Copartner Client")
    parser.add_argument(
        "diff_file",
        help="Path to the diff file"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=9876,
        help="Port of the daemon server (default: 9876)"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host of the daemon server (default: localhost)"
    )
    parser.add_argument(
        "--project-path",
        help="Project path (defaults to current directory)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM for testing"
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Don't ask for confirmation before applying changes"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result in JSON format"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30.0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the suggested changes but don't apply them"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create backup files when applying changes"
    )
    
    args = parser.parse_args()
    
    # Validate diff file
    diff_file_path = Path(args.diff_file)
    if not diff_file_path.exists():
        print(f"❌ Diff file not found: {diff_file_path}")
        sys.exit(1)
    
    # Determine project path
    project_path = args.project_path or str(Path.cwd())
    project_path = str(Path(project_path).resolve())
    
    if not Path(project_path).exists():
        print(f"❌ Project path not found: {project_path}")
        sys.exit(1)
    
    # Create client
    base_url = f"http://{args.host}:{args.port}"
    client = RustCopartnerClient(base_url=base_url, timeout=args.timeout)
    
    try:
        # Health check
        print(f"🔍 Connecting to daemon at {base_url}")
        health = await client.health_check()
        print(f"✅ Connected to daemon (version: {health.get('version', 'unknown')}, "
              f"LLM mode: {health.get('llm_mode', 'unknown')})")
        print()
        
        # Generate suggestion
        print(f"📄 Processing diff file: {diff_file_path}")
        print(f"📁 Project path: {project_path}")
        print("🔄 Generating suggestion...")
        print()
        
        result = await client.suggest_from_file(
            diff_file_path=str(diff_file_path),
            project_path=project_path,
            use_mock=args.mock
        )
        
        if args.json:
            # Output JSON result
            print(json.dumps(result, indent=2))
        else:
            # Print user-friendly result
            print_suggestion_result(result)
            
            # Ask for confirmation if suggestion is valid and user wants confirmation
            if (result.get("success") and 
                result.get("final_diff") and 
                result.get("is_valid") and 
                not args.no_confirm):
                
                if ask_user_confirmation(result["final_diff"]):
                    print("✅ Suggestion accepted by user")
                    
                    if args.dry_run:
                        print("🔍 Validating changes (dry-run mode)...")
                    else:
                        print("🔄 Applying changes...")
                    
                    # Apply the diff using the client's apply_diff method
                    apply_result = client.apply_diff(
                        diff_content=result["final_diff"],
                        project_path=project_path,
                        dry_run=args.dry_run,
                        backup=not args.no_backup
                    )
                    
                    if apply_result["success"]:
                        print(f"✅ {apply_result['message']}")
                        if apply_result.get("files_changed"):
                            print(f"📝 Modified files: {', '.join(apply_result['files_changed'])}")
                        if apply_result.get("backup_files"):
                            print(f"💾 Backup files created: {len(apply_result['backup_files'])}")
                    else:
                        print(f"❌ Failed to apply changes: {apply_result['error']}")
                        if apply_result.get("details"):
                            print(f"Details: {apply_result['details']}")
                        print("You can apply the diff manually using:")
                        print("  git apply <patch-file>")
                else:
                    print("❌ Suggestion rejected by user")
    
    except httpx.ConnectError:
        print(f"❌ Cannot connect to daemon at {base_url}")
        print("Make sure the daemon is running with:")
        print(f"  python -m src.daemon {project_path} -p {args.port}")
        sys.exit(1)
    
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error: {e.response.status_code}")
        try:
            error_detail = e.response.json()
            print(f"Error details: {error_detail}")
        except:
            print(f"Response text: {e.response.text}")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())