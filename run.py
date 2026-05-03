"""
CSMSS College ERP — Production Server Launcher
================================================
  Windows (dev/college server): Waitress WSGI — handles 200+ simultaneous users
  Linux/Render (production):    Gunicorn via Procfile (gunicorn.conf.py)
  Development:                  Flask dev server (set FLASK_ENV=development)
"""
import os
import sys

from app import create_app

app = create_app()

if __name__ == '__main__':
    env  = os.environ.get('FLASK_ENV', 'production')
    port = int(os.environ.get('PORT', 5001))

    if env == 'development':
        # Dev mode: auto-reload, debug errors shown in browser
        print(f"[DEV] Starting Flask dev server on http://0.0.0.0:{port}")
        app.run(debug=True, host='0.0.0.0', port=port, use_reloader=True)

    elif sys.platform == 'win32':
        # Windows production: use Waitress (Gunicorn doesn't support Windows)
        try:
            from waitress import serve
            threads = int(os.environ.get('WEB_CONCURRENCY', 8)) * 4  # 32 threads default
            print(f"[PROD] Starting Waitress on http://0.0.0.0:{port}  threads={threads}")
            print(f"[PROD] Ready for 10,000+ students — CSMSS ERP")
            serve(
                app,
                host='0.0.0.0',
                port=port,
                threads=threads,
                connection_limit=1000,      # Max simultaneous TCP connections
                cleanup_interval=30,        # Close idle connections every 30s
                channel_timeout=60,         # Drop unresponsive clients after 60s
                log_socket_errors=False,    # Suppress noisy socket close logs
            )
        except ImportError:
            print("[ERROR] waitress not installed. Run: pip install waitress")
            sys.exit(1)
    else:
        # Linux: Gunicorn is started via Procfile. If run directly, use Gunicorn API.
        try:
            from gunicorn.app.base import BaseApplication

            class StandaloneApp(BaseApplication):
                def __init__(self, application, options=None):
                    self.options   = options or {}
                    self.application = application
                    super().__init__()
                def load_config(self):
                    for key, val in self.options.items():
                        self.cfg.set(key.lower(), val)
                def load(self):
                    return self.application

            options = {
                'bind':        f'0.0.0.0:{port}',
                'workers':     int(os.environ.get('WEB_CONCURRENCY', 4)),
                'worker_class': 'gthread',
                'threads':     4,
                'timeout':     60,
                'max_requests': 1000,
                'max_requests_jitter': 50,
            }
            print(f"[PROD] Starting Gunicorn on http://0.0.0.0:{port}")
            StandaloneApp(app, options).run()
        except ImportError:
            print("[ERROR] gunicorn not installed. Run: pip install gunicorn")
            sys.exit(1)
