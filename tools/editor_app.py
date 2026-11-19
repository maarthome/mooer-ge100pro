"""Start the GE100 Pro editor as a desktop app (entry point for GE100Pro_Editor.exe)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from ge100pro.app import main  # noqa: E402

sys.exit(main())
