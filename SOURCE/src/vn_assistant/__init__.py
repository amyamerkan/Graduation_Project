"""Hybrid assistant for Vietnamese heritage, tourism and administration."""

import os

# Keep native CPU thread pools bounded when sklearn, PyTorch and FAISS coexist.
# Users can override these before starting Python; GPU execution is unaffected.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

__version__ = "1.2.0"
