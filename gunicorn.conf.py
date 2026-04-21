# gunicorn.conf.py — Configuración de producción para Railway

import os

# Binding
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"

# Workers: 1 worker + threads para SSE (Server-Sent Events)
# No usar múltiples workers con SSE/estado en memoria
workers = 1
threads = 4
worker_class = "gthread"

# Timeouts
timeout = 120          # 2 min para scans largos
keepalive = 5
graceful_timeout = 30

# Logging
accesslog = "-"        # stdout
errorlog  = "-"        # stderr
loglevel  = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

# Reload en desarrollo (desactivado en prod)
reload = os.environ.get("FLASK_ENV") == "development"
