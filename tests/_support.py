"""Shared source locations for development tests outside the installed skills."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DUO_SCRIPTS = ROOT / 'skills' / 'duo' / 'scripts'
sys.path.insert(0, str(DUO_SCRIPTS))
