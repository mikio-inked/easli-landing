#!/usr/bin/env bash
# ============================================================
# easli — Android Build Script
# ============================================================
# Usage:   ./scripts/build-android.sh [profile]
# Example: ./scripts/build-android.sh production        # AAB for Play Store
#          ./scripts/build-android.sh production-apk    # APK for sideload
#          ./scripts/build-android.sh preview           # internal APK
#          ./scripts/build-android.sh                   # default: production
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROFILE="${1:-production}"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  easli Android Build${NC}"
echo -e "${BLUE}  Profile: ${YELLOW}${PROFILE}${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# --- 1. Pre-Flight Checks --------------------------------------

# Check we're in the frontend directory
if [ ! -f "app.json" ] || [ ! -f "eas.json" ]; then
  echo -e "${RED}❌ Error: This script must be run from the frontend/ directory${NC}"
  echo -e "${YELLOW}   Tip: cd frontend && ./scripts/build-android.sh${NC}"
  exit 1
fi

# Check eas-cli is installed
if ! command -v eas &> /dev/null; then
  echo -e "${RED}❌ Error: eas-cli is not installed${NC}"
  echo -e "${YELLOW}   Install with: npm install -g eas-cli${NC}"
  exit 1
fi

# Check user is logged in
echo -e "${BLUE}🔍 Checking Expo login...${NC}"
if ! eas whoami &> /dev/null; then
  echo -e "${RED}❌ Error: Not logged in to Expo${NC}"
  echo -e "${YELLOW}   Run: eas login${NC}"
  exit 1
fi
EXPO_USER=$(eas whoami)
echo -e "${GREEN}✅ Logged in as: ${EXPO_USER}${NC}"

# Check projectId is configured
PROJECT_ID=$(node -e "const a=require('./app.json'); console.log(a.expo.extra?.eas?.projectId || '')" 2>/dev/null || echo "")
if [ -z "$PROJECT_ID" ]; then
  echo -e "${YELLOW}⚠️  Warning: app.json does not contain extra.eas.projectId${NC}"
  echo -e "${YELLOW}   Running eas init to link this project to your account...${NC}"
  eas init
fi

# Check .env (informational only)
if [ ! -f ".env" ]; then
  echo -e "${YELLOW}⚠️  Warning: frontend/.env is missing.${NC}"
  echo -e "${YELLOW}   Production builds use the hardcoded URL from eas.json — proceeding.${NC}"
elif ! grep -q "EXPO_PUBLIC_BACKEND_URL" .env; then
  echo -e "${YELLOW}⚠️  Warning: EXPO_PUBLIC_BACKEND_URL is not set in .env${NC}"
  echo -e "${YELLOW}   Production builds use the hardcoded URL from eas.json — proceeding.${NC}"
else
  BACKEND_URL=$(grep "EXPO_PUBLIC_BACKEND_URL" .env | cut -d '=' -f2-)
  echo -e "${GREEN}✅ Backend URL (from .env): ${BACKEND_URL}${NC}"
fi

# Show effective production URL from eas.json for the chosen profile
EAS_URL=$(node -e "const j=require('./eas.json'); const p=j.build?.['$PROFILE']; console.log(p?.env?.EXPO_PUBLIC_BACKEND_URL || '(not set in eas.json)')" 2>/dev/null || echo "(unknown)")
echo -e "${GREEN}✅ Profile [$PROFILE] backend URL: ${EAS_URL}${NC}"

# Show build artefact type
BUILD_TYPE=$(node -e "const j=require('./eas.json'); const p=j.build?.['$PROFILE']; console.log(p?.android?.buildType || 'apk')" 2>/dev/null || echo "apk")
echo -e "${GREEN}✅ Profile [$PROFILE] artefact: ${BUILD_TYPE}${NC}"
if [ "$BUILD_TYPE" = "app-bundle" ]; then
  echo -e "${BLUE}   (AAB — Android App Bundle, required for Play Store upload)${NC}"
else
  echo -e "${BLUE}   (APK — install directly / sideload / internal distribution)${NC}"
fi

# --- 2. Confirm Build ------------------------------------------

echo ""
echo -e "${YELLOW}⚙️  About to start Android build with profile: ${PROFILE}${NC}"
echo -e "${YELLOW}   Estimated wait: 15–25 min (free tier) / 5–10 min (paid tier)${NC}"
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${RED}Aborted.${NC}"
  exit 0
fi

# --- 3. Run Build ----------------------------------------------

echo ""
echo -e "${BLUE}🚀 Starting EAS build...${NC}"
echo ""

eas build --platform android --profile "$PROFILE"

BUILD_EXIT=$?

if [ $BUILD_EXIT -ne 0 ]; then
  echo ""
  echo -e "${RED}❌ Build failed (exit code $BUILD_EXIT)${NC}"
  echo -e "${YELLOW}   Check the build logs at: https://expo.dev${NC}"
  exit $BUILD_EXIT
fi

echo ""
echo -e "${GREEN}✅ Build completed successfully!${NC}"

# --- 4. Optional: Submit to Google Play ------------------------

if [ "$PROFILE" = "production" ]; then
  # Only offer submit if the AAB is ready (not APK)
  if [ "$BUILD_TYPE" = "app-bundle" ]; then
    # Check service account JSON exists
    SA_PATH=$(node -e "const j=require('./eas.json'); console.log(j.submit?.production?.android?.serviceAccountKeyPath || '')" 2>/dev/null || echo "")

    if [ -n "$SA_PATH" ] && [ -f "$SA_PATH" ]; then
      echo ""
      echo -e "${YELLOW}📤 Submit this AAB to Google Play (track: internal)?${NC}"
      read -p "[y/N] " -n 1 -r
      echo
      if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${BLUE}📤 Submitting to Google Play...${NC}"
        eas submit --platform android --latest

        if [ $? -eq 0 ]; then
          echo ""
          echo -e "${GREEN}✅ Successfully submitted to Google Play!${NC}"
          echo -e "${BLUE}   Go to Play Console → Testing → Internal testing to publish${NC}"
          echo -e "${BLUE}   ⚠️  Remember: new apps need 14-day Closed Testing before Production${NC}"
        else
          echo ""
          echo -e "${RED}❌ Submit failed. You can retry manually:${NC}"
          echo -e "${YELLOW}   eas submit --platform android --latest${NC}"
        fi
      else
        echo -e "${BLUE}ℹ️  Skipped submit. Run later with:${NC}"
        echo -e "${YELLOW}   eas submit --platform android --latest${NC}"
      fi
    else
      echo ""
      echo -e "${YELLOW}⚠️  Google Play service account JSON not found:${NC}"
      echo -e "${YELLOW}   Expected at: ${SA_PATH:-./secrets/google-play-service-account.json}${NC}"
      echo ""
      echo -e "${BLUE}📋 To enable automatic submit:${NC}"
      echo -e "${BLUE}   1. Go to Google Play Console → Setup → API access${NC}"
      echo -e "${BLUE}   2. Create service account + grant 'Release Manager' role${NC}"
      echo -e "${BLUE}   3. Download JSON key → place at: ./secrets/google-play-service-account.json${NC}"
      echo -e "${BLUE}   4. Re-run this script, or use: eas submit --platform android --latest${NC}"
      echo ""
      echo -e "${BLUE}ℹ️  For now: download the AAB from https://expo.dev and upload manually${NC}"
      echo -e "${BLUE}   to Play Console → Testing → Internal testing → Create new release${NC}"
    fi
  else
    echo ""
    echo -e "${BLUE}ℹ️  APK built (not AAB). Play Store requires AAB.${NC}"
    echo -e "${BLUE}   For Play Store upload, run: ./scripts/build-android.sh production${NC}"
    echo -e "${BLUE}   Your APK is ready for direct install / sideload / internal test distribution.${NC}"
  fi
fi

echo ""
echo -e "${GREEN}🎉 Done!${NC}"
