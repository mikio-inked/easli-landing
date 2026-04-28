# ============================================================
# KlarPost — iOS Build Script (Windows / PowerShell)
# ============================================================
# Usage:   .\scripts\build-ios.ps1 [profile]
# Example: .\scripts\build-ios.ps1 production
#          .\scripts\build-ios.ps1 preview
#          .\scripts\build-ios.ps1                 # default: production
# ============================================================
# IMPORTANT: First time only, allow PowerShell to run scripts:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# ============================================================

param(
    [string]$Profile = "production"
)

$ErrorActionPreference = "Stop"

function Write-Color($Text, $Color) {
    Write-Host $Text -ForegroundColor $Color
}

Write-Color "============================================================" Cyan
Write-Color "  KlarPost iOS Build (Windows)" Cyan
Write-Color "  Profile: $Profile" Yellow
Write-Color "============================================================" Cyan
Write-Host ""

# --- 1. Pre-Flight Checks --------------------------------------

# Check we're in the frontend directory
if (-not (Test-Path "app.json") -or -not (Test-Path "eas.json")) {
    Write-Color "[ERROR] This script must be run from the frontend/ directory" Red
    Write-Color "  Tip: cd frontend; .\scripts\build-ios.ps1" Yellow
    exit 1
}

# Check Node.js is installed
try {
    $nodeVersion = node --version 2>$null
    Write-Color "[OK] Node.js: $nodeVersion" Green
} catch {
    Write-Color "[ERROR] Node.js is not installed" Red
    Write-Color "  Download from: https://nodejs.org/ (LTS version)" Yellow
    exit 1
}

# Check eas-cli is installed
try {
    $easVersion = eas --version 2>$null
    Write-Color "[OK] EAS CLI: $easVersion" Green
} catch {
    Write-Color "[ERROR] eas-cli is not installed" Red
    Write-Color "  Install with: npm install -g eas-cli" Yellow
    exit 1
}

# Check user is logged in
Write-Color "[CHECK] Verifying Expo login..." Cyan
try {
    $expoUser = eas whoami 2>$null
    if ([string]::IsNullOrWhiteSpace($expoUser)) { throw }
    Write-Color "[OK] Logged in as: $expoUser" Green
} catch {
    Write-Color "[ERROR] Not logged in to Expo" Red
    Write-Color "  Run: eas login" Yellow
    exit 1
}

# Check projectId is configured
$appJson = Get-Content "app.json" -Raw | ConvertFrom-Json
$projectId = $appJson.expo.extra.eas.projectId
if ([string]::IsNullOrWhiteSpace($projectId)) {
    Write-Color "[WARN] app.json has no extra.eas.projectId" Yellow
    Write-Color "  Running 'eas init' to link this project to your account..." Yellow
    eas init
    if ($LASTEXITCODE -ne 0) {
        Write-Color "[ERROR] eas init failed" Red
        exit 1
    }
}

# Check .env exists and has backend URL
if (-not (Test-Path ".env")) {
    Write-Color "[ERROR] frontend/.env is missing" Red
    exit 1
}
$envContent = Get-Content ".env" -Raw
if ($envContent -notmatch "EXPO_PUBLIC_BACKEND_URL") {
    Write-Color "[ERROR] EXPO_PUBLIC_BACKEND_URL is not set in .env" Red
    exit 1
}
$backendUrl = (Get-Content ".env" | Where-Object { $_ -match "^EXPO_PUBLIC_BACKEND_URL=" }) -replace "^EXPO_PUBLIC_BACKEND_URL=", ""
Write-Color "[OK] Backend URL: $backendUrl" Green

# --- 2. Confirm Build ------------------------------------------

Write-Host ""
Write-Color "About to start iOS build with profile: $Profile" Yellow
Write-Color "Estimated wait: 15-25 min (free tier) / 5-10 min (paid tier)" Yellow
$confirm = Read-Host "Continue? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Color "Aborted." Red
    exit 0
}

# --- 3. Run Build ----------------------------------------------

Write-Host ""
Write-Color "[BUILD] Starting EAS build..." Cyan
Write-Host ""

eas build --platform ios --profile $Profile --non-interactive

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Color "[ERROR] Build failed (exit code $LASTEXITCODE)" Red
    Write-Color "  Check the build logs at: https://expo.dev" Yellow
    exit $LASTEXITCODE
}

Write-Host ""
Write-Color "[SUCCESS] Build completed!" Green

# --- 4. Optional: Submit to TestFlight -------------------------

if ($Profile -eq "production") {
    Write-Host ""
    Write-Color "Submit this build to TestFlight now?" Yellow
    $submit = Read-Host "(y/N)"
    if ($submit -eq "y" -or $submit -eq "Y") {
        Write-Host ""
        Write-Color "[SUBMIT] Submitting to TestFlight..." Cyan
        eas submit --platform ios --latest --non-interactive

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Color "[SUCCESS] Successfully submitted to TestFlight!" Green
            Write-Color "  Apple needs ~5-15 min to process the build" Cyan
            Write-Color "  Then it will appear in TestFlight on your iPhone" Cyan
        } else {
            Write-Host ""
            Write-Color "[ERROR] Submit failed. You can retry manually:" Red
            Write-Color "  eas submit --platform ios --latest" Yellow
        }
    } else {
        Write-Color "[INFO] Skipped TestFlight submit. Run later with:" Cyan
        Write-Color "  eas submit --platform ios --latest" Yellow
    }
}

Write-Host ""
Write-Color "[DONE]" Green
