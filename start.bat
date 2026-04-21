@echo off
echo ============================================
echo  GROW Strategy Dashboard
echo ============================================
echo.

if not exist "venv" (
    echo Creando entorno virtual...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Instalando dependencias...
pip install -r requirements.txt -q

echo.
echo Abriendo dashboard en http://localhost:5000
start "" http://localhost:5000
echo.
python app.py
