"""Vercel entrypoint for the API service (D-019).

Vercel bundles only this folder plus the files listed in `includeFiles` (vercel.json), so the
court_delay package comes from ../src and the model from ./model
(`python -m court_delay.train --export backend/model`). The front end is a separate static
service on Vercel, so this app serves only /api/*.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
os.environ.setdefault("COURT_DELAY_MODEL_DIR", str(HERE / "model"))

from court_delay.api import create_app  # noqa: E402  (needs the path set above)

app = create_app(frontend=None)
