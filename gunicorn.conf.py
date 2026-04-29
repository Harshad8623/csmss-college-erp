# gunicorn.conf.py  –  Production server configuration
# ──────────────────────────────────────────────────────────────────────────────
# Tuned for CSMSS ERP: 10,000 students + 200 teachers
#
# Plan-based WEB_CONCURRENCY guide (set as Render env var):
#   Free    (0.1 vCPU, 512MB)  → WEB_CONCURRENCY=2   (8 concurrent req)
#   Starter (0.5 vCPU, 512MB)  → WEB_CONCURRENCY=2   (8 concurrent req)
#   Standard(1 vCPU,   2GB)    → WEB_CONCURRENCY=4   (16 concurrent req)
#   Pro     (2 vCPU,   4GB)    → WEB_CONCURRENCY=8   (32 concurrent req)
#   Pro Plus(4 vCPU,   8GB)    → WEB_CONCURRENCY=16  (64 concurrent req)
# ──────────────────────────────────────────────────────────────────────────────

import os

# ── Worker count ──────────────────────────────────────────────────────────────
# Set WEB_CONCURRENCY env var in Render Dashboard → Environment
# Formula: (2 × CPU cores) + 1  but cap at available memory
workers = int(os.environ.get("WEB_CONCURRENCY", 4))

# ── Worker class ──────────────────────────────────────────────────────────────
# gthread: multi-threaded, best for Flask + PostgreSQL (I/O-bound)
worker_class = "gthread"
threads      = 4        # workers × threads = total concurrent requests

# ── Connection queue ──────────────────────────────────────────────────────────
backlog = 1024          # Queue up to 1024 connections during peak load

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout          = 60   # Kill workers that hang > 60s (prevents deadlocks)
graceful_timeout = 30
keepalive        = 5

# ── Binding ───────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.environ.get('PORT', '5001')}"

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog  = "-"
errorlog   = "-"
loglevel   = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sus'

# ── Process naming ────────────────────────────────────────────────────────────
proc_name = "csmss-erp"

# ── Pre-load app (saves ~30-60 MB RAM by fork-sharing) ────────────────────────
preload_app = True

# ── Worker recycling (prevents memory leaks over time) ────────────────────────
max_requests        = 1000   # Restart worker after 1000 requests
max_requests_jitter = 50     # Add randomness to avoid simultaneous restarts
