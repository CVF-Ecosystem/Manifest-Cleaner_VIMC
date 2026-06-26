#!/usr/bin/env python3
"""VIMC Manifest Cleaner v2.0 - Entry Point.

Modular architecture with ship type auto-detection.
Supports MARINER (desc first, KGS) and PIONEER/NAVIGATOR/STAR (weight first, TONS).
"""

import sys
import tkinter as tk
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from gui.main_window import ManifestCleanerApp
from utils.helpers import setup_logging, get_application_path

try:
    from tkinterdnd2 import TkinterDnD  # type: ignore
    HAS_DND = True
except ImportError:
    HAS_DND = False


def main():
    """Main entry point."""
    # Setup logging
    log_dir = get_application_path() / "logs"
    log_dir.mkdir(exist_ok=True)
    setup_logging(log_dir / "vimc_manifest_cleaner.log")
    
    # Create root window
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    # Run application
    app = ManifestCleanerApp(root)
    app.run()


if __name__ == "__main__":
    main()
