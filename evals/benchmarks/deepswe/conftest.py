import sys
from pathlib import Path

# shortcut: four benchmark dirs each ship a metrics.py, so pop the cached one before this dir's tests import it. Upgrade to a shared package with unique names.
sys.path.insert(0, str(Path(__file__).parent))
sys.modules.pop("metrics", None)
