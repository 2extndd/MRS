#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "═══════════════════════════════════════════════════════════════════"
echo "🚀 RAILWAY AUTOMATIC SETUP - MercariSearcher"
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 не найден. Установите Python 3.${NC}"
    exit 1
fi

# Проверка наличия requests
if ! python3 -c "import requests" 2>/dev/null; then
    echo -e "${BLUE}📦 Устанавливаю requests...${NC}"
    pip3 install requests
fi

# Запрос токена
if [ -z "$RAILWAY_TOKEN" ]; then
    echo -e "${BLUE}🔑 Введите ваш Railway API Token:${NC}"
    echo -e "${BLUE}   (Получите на: https://railway.app/account/tokens)${NC}"
    echo ""
    read -p "Token: " RAILWAY_TOKEN
    export RAILWAY_TOKEN
fi

# Запуск скрипта
echo ""
echo -e "${GREEN}✓ Запускаю автоматическую настройку...${NC}"
echo ""

python3 setup_railway.py

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Готово!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════${NC}"
