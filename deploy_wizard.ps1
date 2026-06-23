# SmartLog - Render Deploy Wizard
# ================================
# This script will:
# 1. Open your browser to Render dashboard
# 2. Guide you step by step
# 3. Automatically verify after deployment

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SmartLog - Render Deploy Wizard" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Open Render Dashboard
Write-Host "Step 1: Opening Render Dashboard..." -ForegroundColor Yellow
Start-Process "https://dashboard.render.com"
Start-Sleep 2

Write-Host ""
Write-Host "Now in your browser, please:" -ForegroundColor Green
Write-Host "  1. Log in to Render (if needed)" -ForegroundColor White
Write-Host "  2. You'll see 'smartlog-v2' in Services" -ForegroundColor White
Write-Host "  3. Click on it" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter when you're on the service page"

# Step 2: Manual Deploy
Write-Host ""
Write-Host "Step 2: Trigger Manual Deploy" -ForegroundColor Yellow
Write-Host ""
Write-Host "In the Render dashboard, click:" -ForegroundColor Green
Write-Host "  'Manual Deploy' -> 'Deploy latest commit'" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter AFTER clicking Deploy"

# Step 3: Wait
Write-Host ""
Write-Host "Step 3: Waiting for deployment (60 seconds)..." -ForegroundColor Yellow
for ($i = 60; $i -ge 1; $i--) {
    Write-Progress -Activity "Waiting for deploy" -Status "$i seconds remaining" -PercentComplete ((60-$i)/60*100)
    Start-Sleep 1
}

# Step 4: Check Health
Write-Host ""
Write-Host "Step 4: Checking deployment..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "https://smartlog-v2.onrender.com/api/health" -TimeoutSec 10 -ErrorAction Stop
    $data = $response.Content | ConvertFrom-Json
    Write-Host ""
    Write-Host "Status: $($data.status)" -ForegroundColor $(if($data.status -eq 'healthy'){'Green'}else{'Red'})
    Write-Host "Database: $($data.database)" -ForegroundColor $(if($data.database -eq 'connected'){'Green'}else{'Red'})
    Write-Host "Database Configured: $($data.database_configured)" -ForegroundColor Yellow
    Write-Host ""
    
    if ($data.database -eq 'not_configured') {
        Write-Host "Database not configured. Setting up DATABASE_URL step:" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  1. Go to https://dashboard.render.com" -ForegroundColor White
        Write-Host "  2. Click 'smartlog-db' (PostgreSQL)" -ForegroundColor White
        Write-Host "  3. Copy 'Internal Database URL'" -ForegroundColor White
        Write-Host "  4. Go back to 'smartlog-v2' Service" -ForegroundColor White
        Write-Host "  5. Environment -> Add Variable" -ForegroundColor White
        Write-Host "     Key: DATABASE_URL" -ForegroundColor White
        Write-Host "     Value: (paste what you copied)" -ForegroundColor White
        Write-Host "  6. Save Changes (auto-restarts)" -ForegroundColor White
    }
    elseif ($data.database -eq 'connected') {
        Write-Host "SUCCESS! Application is running with database!" -ForegroundColor Green
        Write-Host "Open https://smartlog-v2.onrender.com in your browser" -ForegroundColor Green
    }
} catch {
    Write-Host "Deployment might still be in progress..." -ForegroundColor Red
    Write-Host "Check dashboard: https://dashboard.render.com" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Cyan
Read-Host "Press Enter to exit"
