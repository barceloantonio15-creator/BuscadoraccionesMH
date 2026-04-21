"""
GROW Strategy Dashboard — Flask Backend (Cloud Edition)
Deploy en Railway · Notificaciones Telegram · Scan programado
"""

from flask import Flask, jsonify, render_template, request, Response, stream_with_context
from flask_cors import CORS
import sqlite3
import threading
import json
import os
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()  # carga .env en desarrollo local

from scanner import GrowthStrategyScanner
from telegram_notifier import TelegramNotifier

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ─── App & Config ─────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

DB_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'grow_data.db')
TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
SCAN_API_KEY     = os.environ.get('SCAN_API_KEY', '')
AUTO_SCAN        = os.environ.get('AUTO_SCAN', 'false').lower() == 'true'
SCAN_STOCKS      = int(os.environ.get('SCAN_STOCKS', 50))
PORT             = int(os.environ.get('PORT', 5000))

telegram = TelegramNotifier(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

_scanner: Optional[GrowthStrategyScanner] = None
_scan_thread: Optional[threading.Thread] = None
_scan_lock = threading.Lock()
_sse_clients: list = []


# ─── Database ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT, finished_at TEXT,
                total_scanned INTEGER DEFAULT 0, total_qualified INTEGER DEFAULT 0
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER, ticker TEXT, name TEXT, score REAL, signal TEXT,
                price REAL, entry_price REAL, stop_loss REAL, target REAL,
                r_r_ratio REAL, distance_ath REAL, rsi REAL,
                returns_1m REAL, returns_3m REAL, returns_6m REAL,
                volume_ratio REAL, sector TEXT, industry TEXT,
                market_cap REAL, pe_ratio REAL, revenue_growth REAL,
                earnings_growth REAL, atr_percent REAL, volatility REAL,
                scores_json TEXT, details_json TEXT, scanned_at TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans(id)
            )""")
        conn.commit()
    logger.info("DB inicializada: %s", DB_PATH)


def save_results(scan_id: int, results: list):
    with get_db() as conn:
        for r in results:
            conn.execute("""INSERT INTO results (
                    scan_id,ticker,name,score,signal,price,entry_price,stop_loss,target,
                    r_r_ratio,distance_ath,rsi,returns_1m,returns_3m,returns_6m,
                    volume_ratio,sector,industry,market_cap,pe_ratio,revenue_growth,
                    earnings_growth,atr_percent,volatility,scores_json,details_json,scanned_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (scan_id, r['ticker'], r.get('name', r['ticker']),
                 r['score'], r['signal'], r['price'],
                 r.get('entry_price'), r.get('stop_loss'), r.get('target'),
                 r.get('r_r_ratio', 0), r.get('distance_ath', 0),
                 r.get('rsi', 0), r.get('returns_1m', 0), r.get('returns_3m', 0),
                 r.get('returns_6m', 0), r.get('volume_ratio', 0),
                 r.get('sector', 'Unknown'), r.get('industry', 'Unknown'),
                 r.get('market_cap', 0), r.get('pe_ratio'),
                 r.get('revenue_growth'), r.get('earnings_growth'),
                 r.get('atr_percent', 0), r.get('volatility', 0),
                 json.dumps(r.get('scores', {})), json.dumps(r.get('details', {})),
                 r.get('scanned_at', datetime.now().isoformat())))
        conn.execute("UPDATE scans SET total_qualified=?, finished_at=? WHERE id=?",
                     (len(results), datetime.now().isoformat(), scan_id))
        conn.commit()


def get_latest_scan_results(limit=100, signal=None, min_score=0):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM scans ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return []
        scan_id = row['id']
        query = "SELECT * FROM results WHERE scan_id=? AND score>=?"
        params = [scan_id, min_score]
        if signal and signal != 'ALL':
            query += " AND signal=?"; params.append(signal)
        query += " ORDER BY score DESC LIMIT ?"; params.append(limit)
        rows = conn.execute(query, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d['scores']  = json.loads(d.get('scores_json')  or '{}')
            d['details'] = json.loads(d.get('details_json') or '{}')
            out.append(d)
        return out


def get_scan_history():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 20")]


# ─── SSE ──────────────────────────────────────────────────────────────────────

def broadcast_sse(data: dict):
    msg = f"data: {json.dumps(data)}\n\n"
    dead = []
    for q in _sse_clients:
        try: q.append(msg)
        except Exception: dead.append(q)
    for q in dead:
        if q in _sse_clients: _sse_clients.remove(q)


# ─── Background Scan ──────────────────────────────────────────────────────────

def run_scan_background(max_stocks: int, scan_id: int):
    global _scanner
    telegram.send_scan_started(max_stocks)

    def progress_cb(current, total, ticker, result):
        broadcast_sse({'type':'progress','current':current,'total':total,
                       'ticker':ticker,'qualified':result is not None,
                       'score': result['score'] if result else None,
                       'signal': result['signal'] if result else None})
        with get_db() as conn:
            conn.execute("UPDATE scans SET total_scanned=? WHERE id=?", (current, scan_id))
            conn.commit()

    try:
        results = _scanner.scan(max_stocks=max_stocks, progress_callback=progress_cb)
        save_results(scan_id, results)
        broadcast_sse({'type':'complete','total_qualified':len(results),'scan_id':scan_id})
        logger.info("Scan %d completado: %d resultados", scan_id, len(results))
        telegram.send_scan_complete(results, scan_id)
    except Exception as e:
        logger.error("Error scan: %s", e, exc_info=True)
        broadcast_sse({'type':'error','message':str(e)})
        telegram.send_error(str(e))
        with get_db() as conn:
            conn.execute("UPDATE scans SET finished_at=? WHERE id=?",
                         (datetime.now().isoformat(), scan_id)); conn.commit()


# ─── Scheduler ────────────────────────────────────────────────────────────────

def _trigger_auto_scan():
    global _scanner, _scan_thread
    with _scan_lock:
        if _scanner and _scanner.scan_status.get('running'):
            return
        _scanner = GrowthStrategyScanner()
        with get_db() as conn:
            cur = conn.execute("INSERT INTO scans (started_at,total_scanned) VALUES (?,?)",
                               (datetime.now().isoformat(), 0))
            scan_id = cur.lastrowid; conn.commit()
        _scan_thread = threading.Thread(target=run_scan_background,
                                        args=(SCAN_STOCKS, scan_id), daemon=True)
        _scan_thread.start()
        logger.info("Auto-scan iniciado (scan_id=%d)", scan_id)


def setup_scheduler():
    if not AUTO_SCAN:
        logger.info("AUTO_SCAN desactivado"); return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        scheduler = BackgroundScheduler(timezone='America/New_York')
        scheduler.add_job(_trigger_auto_scan, CronTrigger(day_of_week='mon-fri', hour=9,  minute=35))
        scheduler.add_job(_trigger_auto_scan, CronTrigger(day_of_week='mon-fri', hour=15, minute=55))
        scheduler.start()
        logger.info("Scheduler activo: 9:35 y 15:55 ET lun-vie")
    except ImportError:
        logger.warning("APScheduler no instalado — instala con: pip install apscheduler")


# ─── Auth ─────────────────────────────────────────────────────────────────────

def check_api_key():
    if not SCAN_API_KEY: return True
    return request.headers.get('X-API-Key') == SCAN_API_KEY


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/scan/start', methods=['POST'])
def start_scan():
    global _scanner, _scan_thread
    if not check_api_key():
        return jsonify({'error': 'No autorizado'}), 401
    with _scan_lock:
        if _scanner and _scanner.scan_status.get('running'):
            return jsonify({'error': 'Ya hay un scan en curso'}), 409
        data = request.get_json(silent=True) or {}
        max_stocks = max(10, min(200, int(data.get('max_stocks', SCAN_STOCKS))))
        _scanner = GrowthStrategyScanner()
        with get_db() as conn:
            cur = conn.execute("INSERT INTO scans (started_at,total_scanned) VALUES (?,?)",
                               (datetime.now().isoformat(), 0))
            scan_id = cur.lastrowid; conn.commit()
        _scan_thread = threading.Thread(target=run_scan_background,
                                        args=(max_stocks, scan_id), daemon=True)
        _scan_thread.start()
    return jsonify({'message': f'Scan iniciado ({max_stocks} acciones)', 'scan_id': scan_id})


@app.route('/api/scan/status')
def scan_status():
    if not _scanner:
        return jsonify({'running': False, 'progress': 0, 'total': 0})
    return jsonify(_scanner.scan_status)


@app.route('/api/scan/stop', methods=['POST'])
def stop_scan():
    if _scanner: _scanner.scan_status['running'] = False
    return jsonify({'message': 'Señal de parada enviada'})


@app.route('/api/results')
def get_results():
    results = get_latest_scan_results(
        limit=int(request.args.get('limit', 100)),
        signal=request.args.get('signal', 'ALL'),
        min_score=float(request.args.get('min_score', 0))
    )
    return jsonify({'results': results, 'count': len(results)})


@app.route('/api/history')
def scan_history():
    return jsonify({'history': get_scan_history()})


@app.route('/api/stats')
def stats():
    results = get_latest_scan_results(limit=500)
    if not results: return jsonify({'no_data': True})
    signals, sectors = {}, {}
    scores = [r['score'] for r in results]
    for r in results:
        signals[r.get('signal','NEUTRAL')] = signals.get(r.get('signal','NEUTRAL'), 0) + 1
        sectors[r.get('sector','Unknown')] = sectors.get(r.get('sector','Unknown'), 0) + 1
    return jsonify({
        'total': len(results), 'signals': signals,
        'sectors': dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True)),
        'avg_score': round(sum(scores)/len(scores), 1), 'top_score': max(scores),
        'score_distribution': {
            '90-100': sum(1 for s in scores if s >= 90),
            '80-89':  sum(1 for s in scores if 80 <= s < 90),
            '70-79':  sum(1 for s in scores if 70 <= s < 80),
            '60-69':  sum(1 for s in scores if 60 <= s < 70),
            '<60':    sum(1 for s in scores if s < 60),
        }
    })


@app.route('/api/telegram/test', methods=['POST'])
def test_telegram():
    ok = telegram.test()
    return (jsonify({'message': 'Mensaje enviado a Telegram ✓'}) if ok
            else jsonify({'error': 'Error. Revisa TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID'}), 500)


@app.route('/api/events')
def sse_stream():
    q = []
    _sse_clients.append(q)
    def generate():
        yield f"data: {json.dumps({'type':'connected'})}\n\n"
        try:
            import time
            while True:
                yield q.pop(0) if q else (time.sleep(0.2) or '')
        except GeneratorExit:
            pass
        finally:
            if q in _sse_clients: _sse_clients.remove(q)
    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    setup_scheduler()
    logger.info("GROW Dashboard en puerto %d", PORT)
    app.run(host='0.0.0.0', port=PORT, threaded=True, debug=False)
