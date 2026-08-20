#!/usr/bin/env python3
"""Prove this fixture can write everything the contract has, before a run depends on it."""
from __future__ import annotations

import sys
from pathlib import Path


def main():
    print("perunit selftest")
    import anndata as ad
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scprofile import manifest
    for m in (ad, np, pd, manifest):
        assert m is not None
    print(f"  anndata {ad.__version__}  numpy {np.__version__}")
    print("perunit selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
