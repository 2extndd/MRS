#!/bin/bash
# Force Railway to redeploy worker from GitHub (not local files)

echo "=== FORCE RAILWAY REDEPLOY FROM GITHUB ==="
echo ""
echo "Проблема: railway up загружает локальные файлы"
echo "Решение: Заставить Railway pull из GitHub"
echo ""

# 1. Проверить что коммит в GitHub
echo "1. Проверка GitHub..."
GITHUB_COMMIT=$(git ls-remote origin HEAD | cut -f1)
LOCAL_COMMIT=$(git rev-parse HEAD)

echo "   Local commit:  $LOCAL_COMMIT"
echo "   GitHub commit: $GITHUB_COMMIT"

if [ "$LOCAL_COMMIT" = "$GITHUB_COMMIT" ]; then
    echo "   ✅ Коммиты совпадают"
else
    echo "   ❌ ВНИМАНИЕ: Коммиты не совпадают!"
    echo "   Нужно сделать: git push origin main"
    exit 1
fi

echo ""
echo "2. Удаление Railway link (чтобы заставить его pull из GitHub)..."
rm -f .railway.json 2>/dev/null || true
echo "   ✅ .railway.json удален (если был)"

echo ""
echo "3. Re-link к Railway проекту..."
railway link -p f17da572-14c9-47b5-a9f1-1b6d5b6dea2d

echo ""
echo "4. Triggering redeploy worker через Railway API..."
# Railway должен теперь pull из GitHub вместо использования локальных файлов

# Для worker - указываем что нужен GitHub source
echo "   Deploying worker from GitHub..."
railway up --service worker

echo ""
echo "5. Deploying web from GitHub..."
railway up --service web

echo ""
echo "=== ГОТОВО ==="
echo ""
echo "Проверьте через 2-3 минуты:"
echo "1. railway logs --service worker | grep 'Checking for pending'"
echo "2. https://web-production-fe38.up.railway.app/logs"
echo ""
echo "Если всё ещё старый код - нужно в Railway Dashboard:"
echo "1. Worker Service → Settings → Source"
echo "2. Убедиться что Source = GitHub: 2extndd/MRS"
echo "3. Branch = main"
echo "4. Нажать 'Redeploy' в Deployments"
