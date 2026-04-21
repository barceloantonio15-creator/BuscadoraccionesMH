#!/bin/bash
echo "============================================"
echo " GROW Strategy Dashboard"
echo "============================================"
echo

if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Instalando dependencias..."
pip install -r requirements.txt -q

echo
echo "Abriendo dashboard en http://localhost:5000"
(sleep 2 && open http://localhost:5000 2>/dev/null || xdg-open http://localhost:5000 2>/dev/null) &
echo
python app.py
