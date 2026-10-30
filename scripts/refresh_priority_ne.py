#!/usr/bin/env python3
"""Refresh a complete NE-2 Schedule E dataset before the shared hourly scan.

Never overwrite the last verified NE-2 data on failed or partial FEC results.
"""
import os
import sys

import refresh_all

key=os.environ.get("FEC_API_KEY") or "DEMO_KEY"
if not refresh_all.refresh_priority_race("NE-2",key):
    sys.exit(1)
