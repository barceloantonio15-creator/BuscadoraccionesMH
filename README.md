# 📈 GROW Strategy Dashboard — Cloud Edition

Scanner de acciones CANSLIM + Near-ATH Momentum con dashboard web en la nube y alertas en Telegram.

---

## 📋 Guía completa paso a paso

### 1️⃣ Crear el bot de Telegram

1. Abre Telegram → busca **@BotFather** → escribe `/newbot`
2. Elige nombre y username → copia el **TOKEN** (`1234567890:AAFxxx...`)
3. **Obtener tu Chat ID automáticamente** con el script incluido:

```bash
# Instala requests si no lo tienes:
pip install requests

# Ejecuta el helper:
python setup_telegram.py TU_TOKEN_AQUI
```

El script espera a que escribas `/start` en tu bot y te muestra el Chat ID directamente.

---

### 2️⃣ Subir el código a GitHub

```bash
# Desde la carpeta del proyecto:
git init
git add .
git commit -m "GROW Dashboard inicial"
git branch -M main

# Crea un repo NUEVO en github.com (vacío, sin README),
# luego conecta y sube:
git remote add origin https://github.com/TU_USUARIO/grow-dashboard.git
git push -u origin main
```

---

### 3️⃣ Añadir secrets a GitHub

En tu repo de GitHub → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Tu token del bot |
| `TELEGRAM_CHAT_ID` | Tu chat ID |

Así el workflow de CI/CD puede notificarte en cada deploy.

---

### 4️⃣ Deploy en Railway

1. Ve a **[railway.app](https://railway.app)** → inicia sesión con GitHub
2. **"New Project" → "Deploy from GitHub repo"**
3. Selecciona `grow-dashboard`
4. Railway detecta el `Procfile` y `nixpacks.toml` automáticamente → despliega

---

### 5️⃣ Variables de entorno en Railway

En tu proyecto Railway → pestaña **"Variables"** → añade una a una:

| Variable | Valor | Descripción |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `1234567890:AAFxxx...` | Token del bot |
| `TELEGRAM_CHAT_ID` | `-1001234567890` | Tu chat ID |
| `AUTO_SCAN` | `true` | Scans automáticos lun-vie |
| `SCAN_STOCKS` | `50` | Acciones por scan (10-200) |
| `SCAN_API_KEY` | *(opcional)* | Protege el botón de scan |

> ⚠️ Railway inyecta `PORT` automáticamente — **no lo añadas**.

---

### 6️⃣ Verificar que funciona

- Railway te dará una URL: `https://grow-dashboard-production.up.railway.app`
- Ábrela → verás el dashboard
- Pulsa **"🤖 Test Telegram"** → deberías recibir un mensaje en Telegram
- Pulsa **"▶ Iniciar Scan"** para tu primer scan manual

---

## 🔄 Flujo completo

```
git push → GitHub Actions (tests) → Telegram "Deploy iniciado"
                ↓
          Railway redeploya automáticamente
                ↓
    Dashboard disponible en tu URL de Railway
                ↓
    [AUTO_SCAN=true] → 9:35 ET y 15:55 ET (lun-vie)
                ↓
    Resultados → Telegram con breakouts y pullbacks
```

---

## 📊 Estrategia GROW — Criterios de puntuación

| Criterio | Peso | Descripción |
|---|---|---|
| Proximidad a ATH | 30% | Dentro del 5-15% del máximo histórico |
| Tendencia MAs | 20% | MAs 10/21/50/200 alineadas alcistas |
| Momentum | 20% | Retornos positivos 1M / 3M / 6M |
| Volumen | 15% | Volumen superior al promedio 50D |
| RSI | 10% | Zona óptima 60-75 |
| Consolidación | 5% | Volatilidad baja (< 25% anualizada) |
| Fundamentales | +10% | Bonus: crecimiento ingresos/EPS + ownership inst. |

**Señales:**
- 🟢 **BREAKOUT** — Precio sobre MA10, volumen > 1.3×, cierre en máximos del día, a menos del 8% del ATH
- 🟡 **PULLBACK** — Retroceso a MA21 con RSI > 50 y tendencia alcista intacta

---

## 📁 Estructura del proyecto

```
grow-dashboard/
├── app.py                      # Backend Flask (API + scheduler + SSE)
├── scanner.py                  # Lógica de análisis GROW/CANSLIM
├── telegram_notifier.py        # Notificaciones Telegram
├── setup_telegram.py           # Helper para obtener Chat ID
├── gunicorn.conf.py            # Config de producción
├── templates/
│   └── dashboard.html          # Frontend (Chart.js + SSE en tiempo real)
├── requirements.txt
├── Procfile                    # Para Railway
├── railway.json                # Config Railway
├── nixpacks.toml               # Versión Python para Railway
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD + notificación Telegram en deploy
├── .env.example                # Plantilla de variables
└── .gitignore                  # Excluye .env y .db del repo
```

---

## 🛠 API Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Dashboard web |
| `POST` | `/api/scan/start` | Iniciar scan (`{"max_stocks": 50}`) |
| `GET` | `/api/scan/status` | Estado actual del scan |
| `POST` | `/api/scan/stop` | Detener scan |
| `GET` | `/api/results` | Resultados (`?signal=BREAKOUT&min_score=70`) |
| `GET` | `/api/stats` | Estadísticas para los gráficos |
| `GET` | `/api/history` | Historial de scans anteriores |
| `POST` | `/api/telegram/test` | Enviar mensaje de prueba a Telegram |
| `GET` | `/api/events` | SSE — progreso en tiempo real |
| `GET` | `/health` | Healthcheck para Railway |

---

## 💻 Desarrollo local

```bash
cp .env.example .env
# → Edita .env con tu token y chat_id

python -m venv venv
source venv/bin/activate    # Mac/Linux
# venv\Scripts\activate     # Windows

pip install -r requirements.txt
python app.py
# → http://localhost:5000
```

---

## ⚠️ Disclaimer

Análisis únicamente educativo. Las inversiones conllevan riesgo de pérdida de capital. Realiza siempre tu propia investigación antes de invertir.
