"""
Telegram Notifier para GROW Strategy Scanner
Envía alertas y reportes al bot de Telegram
"""

import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Envía mensajes al bot de Telegram.
    Requiere: TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en variables de entorno.
    """

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)
        if not self.enabled:
            logger.warning("Telegram no configurado. Define TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.")

    def _send(self, text: str, parse_mode: str = "HTML", disable_preview: bool = True) -> bool:
        if not self.enabled:
            return False
        try:
            url = self.BASE_URL.format(token=self.token, method="sendMessage")
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_preview,
            }
            resp = requests.post(url, json=payload, timeout=10)
            if not resp.ok:
                logger.error(f"Telegram error {resp.status_code}: {resp.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error enviando a Telegram: {e}")
            return False

    # ── Mensajes ────────────────────────────────────────────────────────────

    def send_scan_started(self, total: int):
        msg = (
            "🔍 <b>GROW Scanner — Iniciando</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Analizando <b>{total}</b> acciones\n"
            f"⏳ Resultados en unos minutos..."
        )
        self._send(msg)

    def send_scan_complete(self, results: List[Dict], scan_id: int):
        """Envía resumen del scan + top picks con señales."""
        if not results:
            self._send("⚠️ <b>Scan completado</b> — Sin resultados calificados.")
            return

        breakouts = [r for r in results if r.get('signal') == 'BREAKOUT']
        pullbacks = [r for r in results if r.get('signal') == 'PULLBACK']
        top5 = results[:5]
        avg_score = round(sum(r['score'] for r in results) / len(results), 1)

        # ── Encabezado ──
        lines = [
            "📈 <b>GROW SCANNER — Resultados</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"✅ Calificadas: <b>{len(results)}</b> acciones",
            f"🟢 Breakouts: <b>{len(breakouts)}</b>  |  🟡 Pullbacks: <b>{len(pullbacks)}</b>",
            f"⭐ Score promedio: <b>{avg_score}/100</b>",
            "",
        ]

        # ── Breakouts destacados ──
        if breakouts:
            lines.append("🚀 <b>BREAKOUTS ACTIVOS:</b>")
            for r in breakouts[:5]:
                entry = f"${r['entry_price']:.2f}" if r.get('entry_price') else "—"
                stop  = f"${r['stop_loss']:.2f}"  if r.get('stop_loss')  else "—"
                tgt   = f"${r['target']:.2f}"     if r.get('target')     else "—"
                rr    = f"{r['r_r_ratio']}:1"     if r.get('r_r_ratio')  else "—"
                lines.append(
                    f"  <b>${r['ticker']}</b>  Score:{r['score']}  RSI:{r['rsi']:.0f}\n"
                    f"  📍 Entrada:{entry}  Stop:{stop}  🎯{tgt}  R:R {rr}\n"
                    f"  📊 ATH:{r['distance_ath']:.1f}%  1M:{r['returns_1m']:+.1f}%"
                )
            lines.append("")

        # ── Pullbacks ──
        if pullbacks:
            lines.append("🔄 <b>PULLBACKS (reentrada):</b>")
            for r in pullbacks[:3]:
                lines.append(
                    f"  <b>${r['ticker']}</b>  Score:{r['score']}  "
                    f"ATH:{r['distance_ath']:.1f}%  RSI:{r['rsi']:.0f}"
                )
            lines.append("")

        # ── Top 5 por score ──
        lines.append("🏆 <b>TOP 5 POR SCORE:</b>")
        for i, r in enumerate(top5, 1):
            signal_icon = {"BREAKOUT": "🟢", "PULLBACK": "🟡"}.get(r['signal'], "⚪")
            lines.append(
                f"  {i}. {signal_icon} <b>{r['ticker']}</b>  {r['score']}/100  "
                f"${r['price']:.2f}  {r['sector'][:15] if r.get('sector') else ''}"
            )

        lines += [
            "",
            f"⚠️ <i>Análisis educativo. No es consejo de inversión.</i>",
            f"🔗 <i>Scan #{scan_id}</i>",
        ]

        self._send("\n".join(lines))

    def send_alert(self, ticker: str, signal: str, data: Dict):
        """Alerta rápida para una señal específica."""
        icon = "🚀" if signal == "BREAKOUT" else "🔄"
        entry = f"${data['entry_price']:.2f}" if data.get('entry_price') else "—"
        stop  = f"${data['stop_loss']:.2f}"  if data.get('stop_loss')  else "—"
        tgt   = f"${data['target']:.2f}"     if data.get('target')     else "—"

        msg = (
            f"{icon} <b>SEÑAL {signal} — {ticker}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Precio: <b>${data.get('price', 0):.2f}</b>\n"
            f"⭐ Score: <b>{data.get('score', 0)}/100</b>\n"
            f"📊 ATH: {data.get('distance_ath', 0):.1f}%  |  RSI: {data.get('rsi', 0):.0f}\n"
            f"📈 1M: {data.get('returns_1m', 0):+.1f}%  3M: {data.get('returns_3m', 0):+.1f}%\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Entrada: {entry}\n"
            f"🛑 Stop:    {stop}\n"
            f"🎯 Target:  {tgt}\n"
            f"⚖️  R:R:     {data.get('r_r_ratio', 0)}:1\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏢 {data.get('sector', 'Unknown')}  |  Cap: ${data.get('market_cap', 0):.1f}B"
        )
        self._send(msg)

    def send_error(self, message: str):
        self._send(f"❌ <b>Error en GROW Scanner</b>\n<code>{message[:200]}</code>")

    def send_message(self, text: str):
        """Mensaje libre."""
        self._send(text)

    def test(self) -> bool:
        """Verifica que el bot funciona."""
        return self._send(
            "✅ <b>GROW Scanner conectado</b>\n"
            "Bot de Telegram configurado correctamente."
        )
