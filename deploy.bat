@echo off
echo ========================================
echo  SmartLog - Deploy to Render
echo ========================================
echo.
echo Opening Render Dashboard...
start https://dashboard.render.com
echo.
echo Step 1: Log in if needed
echo Step 2: Click "smartlog-v2" from Services
echo Step 3: Click "Manual Deploy" -> "Deploy latest commit"
echo.
pause
echo.
echo Checking deployment...
timeout /t 60 /nobreak >nul
curl -s https://smartlog-v2.onrender.com/api/health
echo.
pause
