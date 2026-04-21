"""
setup_telegram.py — Ayudante para configurar el bot de Telegram

Uso:
    python setup_telegram.py <TU_BOT_TOKEN>

Muestra tu Chat ID tras enviar /start al bot.
"""

import sys
import requests
import time


def get_chat_id(token: str):
    base = f"https://api.telegram.org/bot{token}"

    # Verificar que el token es válido
    r = requests.get(f"{base}/getMe", timeout=10)
    if not r.ok:
        print(f"\n❌ Token inválido: {r.json().get('description', 'Error desconocido')}")
        print("   Asegúrate de copiar el token completo de @BotFather")
        sys.exit(1)

    bot = r.json()["result"]
    print(f"\n✅ Bot encontrado: @{bot['username']} ({bot['first_name']})")
    print(f"\n📱 Ahora ve a Telegram y escribe /start a @{bot['username']}")
    print("   Esperando mensaje... (Ctrl+C para cancelar)\n")

    # Limpiar updates previos
    requests.get(f"{base}/getUpdates?offset=-1", timeout=10)

    # Esperar mensaje del usuario
    last_update = 0
    while True:
        try:
            r = requests.get(f"{base}/getUpdates?timeout=5&offset={last_update + 1}", timeout=15)
            updates = r.json().get("result", [])
            if updates:
                for upd in updates:
                    last_update = upd["update_id"]
                    msg = upd.get("message") or upd.get("channel_post")
                    if msg:
                        chat = msg["chat"]
                        chat_id = chat["id"]
                        chat_type = chat.get("type", "private")
                        chat_name = chat.get("title") or chat.get("username") or chat.get("first_name", "")

                        print(f"✅ Chat detectado:")
                        print(f"   Tipo:     {chat_type}")
                        print(f"   Nombre:   {chat_name}")
                        print(f"   Chat ID:  {chat_id}")
                        print()
                        print("─" * 50)
                        print("Añade estas variables a Railway (o a tu .env):")
                        print("─" * 50)
                        print(f"TELEGRAM_BOT_TOKEN={token}")
                        print(f"TELEGRAM_CHAT_ID={chat_id}")
                        print("─" * 50)

                        # Enviar confirmación al chat
                        requests.post(f"{base}/sendMessage", json={
                            "chat_id": chat_id,
                            "text": (
                                "✅ <b>GROW Scanner configurado</b>\n"
                                f"Chat ID: <code>{chat_id}</code>\n\n"
                                "Las alertas del scanner llegarán aquí."
                            ),
                            "parse_mode": "HTML"
                        }, timeout=10)
                        return
        except KeyboardInterrupt:
            print("\n\nCancelado.")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python setup_telegram.py <TU_BOT_TOKEN>")
        print("\nEjemplo:")
        print("  python setup_telegram.py 1234567890:AAFxxxxxxxxxxxxxxxxxxx")
        sys.exit(1)

    token = sys.argv[1].strip()
    get_chat_id(token)
