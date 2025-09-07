#!/usr/bin/env python3
"""
Entry point for rust-copartner client
"""

import sys
import asyncio
from pathlib import Path

# Add python directory to path
python_dir = Path(__file__).parent / "python"
sys.path.insert(0, str(python_dir))

from src.client import main

if __name__ == "__main__":
    asyncio.run(main())