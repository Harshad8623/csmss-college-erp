# gunicorn.conf.py  –  Production server configuration
# ──────────────────────────────────────────────────────────────────────────────
# Tuned for CSMSS ERP: 10,000 students + 200 teachers on a 2-core/512 MB instance
# (Render free tier).  Scale workers/threads up as you upgrade your plan.
# ──────────────────────────────────────────────────────────────────────────────

import multiprocessing, os

# ── Worker count ──────────────────────────────────────────────────────────────
# Rule of thumb: (2 × CPU cores) + 1
# Render free tier = 0.1 vCPU shared → use 2 workers to stay within memory.
# Upgrade to 4–8 workers on a paid plan.
workers = int(os.environ.get("WEB_CONCURRENCY", 2))

# ── Worker class ──────────────────────────────────────────────────────────────
# gthread: multi-threaded worker, best for Flask + PostgreSQL (I/O bound).
worker_class = "gthread"
threads      = 4        # 2 workers × 4 threads = 8 concurrent requests

# ── Connection queue ──────────────────────────────────────────────────────────
# How many connections to queue while all workers are busy.
backlog = 512

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout        = 60   # Kill workers that hang > 60s (prevents deadlocks)
graceful_timeout = 30
keepalive      = 5    # Keep-alive for persistent connections

# ── Binding ───────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.environ.get('PORT', '5001')}"

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog  = "-"      # stdout (captured by Render)
errorlog   = "-"      # stderr
loglevel   = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ── Process naming ────────────────────────────────────────────────────────────
proc_name = "csmss-erp"

# ── Pre-load app (saves ~30 MB RAM by fork-sharing) ───────────────────────────
preload_app = True
