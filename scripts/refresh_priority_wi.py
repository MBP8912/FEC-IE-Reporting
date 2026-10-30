#!/usr/bin/env python3
"""Refresh WI-1's complete 2026 general-election Schedule E data before other API calls.

A rate limit or interrupted FEC pagination must not publish partial totals.
"""
import os
import sys

import refresh_all

key=os.environ.get("FEC_API_KEY") or "DEMO_KEY"
if not refresh_all.refresh_priority_race("WI-1",key):
    sys.exit(1)
