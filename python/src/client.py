"""
Client for rust-copartner suggestion service
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional, Dict, Any

import httpx


class RustCopartnerClient:
    """Client for communicating with rust-copartner daemon"""
    
    def __init__(self, base_url: str = "http://localhost:9876", timeout: float = 30.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if the daemon is healthy"""
        async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
    
    async def suggest(self, diff_content: str) -> Dict[str, Any]:
        """Generate suggestions from diff content"""
        payload = {
            "diff_content": diff_content
        }
        
        async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
            response = await client.post(f"{self.base_url}/suggest", json=payload)
            response.raise_for_status()
            return response.json()
    
    async def apply_suggestion(self, suggestion_id: str, accept: bool) -> Dict[str, Any]:
        """Apply or reject a suggestion"""
        payload = {
            "suggestion_id": suggestion_id,
            "accept": accept
        }
        
        async with httpx.AsyncClient(timeout=self.timeout, proxy=None) as client:
            response = await client.post(f"{self.base_url}/apply", json=payload)
            response.raise_for_status()
            return response.json()


def print_suggestion_result(result: Dict[str, Any], show_timing: bool = True):
    """Print suggestion result in a simplified format for client"""
    if result.get("success"):        
        # Only print final diff if available
        if result.get("final_diff"):
            print("📝 Suggested changes:")
            print("-" * 50)
            print(result["final_diff"])
            print()
    
    else:
        print("❌ Failed to generate suggestion")
        if result.get("error_message"):
            print(f"Error: {result['error_message']}")
        print()


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
    
    args = parser.parse_args()
    
    # Validate and read diff file
    diff_file_path = Path(args.diff_file)
    if not diff_file_path.exists():
        print(f"❌ Diff file not found: {diff_file_path}")
        sys.exit(1)
    
    try:
        with open(diff_file_path, 'r', encoding='utf-8') as f:
            diff_content = f.read()
    except Exception as e:
        print(f"❌ Failed to read diff file: {e}")
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
        print("🔄 Generating suggestion...")
        print()
        
        result = await client.suggest(diff_content)
        
        if args.json:
            # Output JSON result
            print(json.dumps(result, indent=2))
        else:
            # Print user-friendly result
            print_suggestion_result(result)
            
            # Handle interactive confirmation if daemon requests it
            if result.get("requires_confirmation"):
                suggestion_id = result.get("suggestion_id")
                if suggestion_id:
                    user_accepts = ask_user_confirmation(result.get("final_diff", ""))
                    
                    # Send user's decision back to daemon
                    apply_result = await client.apply_suggestion(suggestion_id, user_accepts)
                    
                    if user_accepts:
                        if apply_result.get("success"):
                            print("✅ Changes applied successfully!")
                            if apply_result.get("files_changed"):
                                print(f"📝 Modified files: {', '.join(apply_result['files_changed'])}")
                        else:
                            print(f"❌ Failed to apply changes: {apply_result.get('error', 'Unknown error')}")
                    else:
                        print("❌ Suggestion rejected by user")
    
    except httpx.ConnectError:
        print(f"❌ Cannot connect to daemon at {base_url}")
        print("Make sure the daemon is running with:")
        print(f"  python rust-copartner-daemon.py <project_dir> -p {args.port}")
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