#!/usr/bin/env bash
# ============================================================
# easli — iOS Build Script
# ============================================================
# Usage:   ./scripts/build-ios.sh [profile]
# Example: ./scripts/build-ios.sh production
#          ./scripts/build-ios.sh preview
#          ./scripts/build-ios.sh                 # default: production
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
echo -e "${BLUE}  easli iOS Build${NC}"
echo -e "${BLUE}  Profile: ${YELLOW}${PROFILE}${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# --- 1. Pre-Flight Checks --------------------------------------

# Check we're in the frontend directory
if [ ! -f "app.json" ] || [ ! -f "eas.json" ]; then
  echo -e "${RED}❌ Error: This script must be run from the frontend/ directory${NC}"
  echo -e "${YELLOW}   Tip: cd frontend && ./scripts/build-ios.sh${NC}"
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

# Check .env exists and has backend URL (informational only — production
# profile in eas.json hardcodes EXPO_PUBLIC_BACKEND_URL, so .env is optional
# on the developer's local machine).
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

# --- 2. Confirm Build ------------------------------------------

echo ""
echo -e "${YELLOW}⚙️  About to start iOS build with profile: ${PROFILE}${NC}"
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

eas build --platform ios --profile "$PROFILE"

BUILD_EXIT=$?

if [ $BUILD_EXIT -ne 0 ]; then
  echo ""
  echo -e "${RED}❌ Build failed (exit code $BUILD_EXIT)${NC}"
  echo -e "${YELLOW}   Check the build logs at: https://expo.dev${NC}"
  exit $BUILD_EXIT
fi

echo ""
echo -e "${GREEN}✅ Build completed successfully!${NC}"

# --- 4. Optional: Submit to TestFlight -------------------------

if [ "$PROFILE" = "production" ]; then
  echo ""
  echo -e "${YELLOW}📤 Submit this build to TestFlight now?${NC}"
  read -p "[y/N] " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${BLUE}📤 Submitting to TestFlight...${NC}"
    eas submit --platform ios --latest

    if [ $? -eq 0 ]; then
      echo ""
      echo -e "${GREEN}✅ Successfully submitted to TestFlight!${NC}"
      echo -e "${BLUE}   Apple needs ~5–15 min to process the build${NC}"
      echo -e "${BLUE}   Then it will appear in TestFlight on your iPhone${NC}"
    else
      echo ""
      echo -e "${RED}❌ Submit failed. You can retry manually:${NC}"
      echo -e "${YELLOW}   eas submit --platform ios --latest${NC}"
    fi
  else
    echo -e "${BLUE}ℹ️  Skipped TestFlight submit. Run later with:${NC}"
    echo -e "${YELLOW}   eas submit --platform ios --latest${NC}"
  fi
fi

echo ""
echo -e "${GREEN}🎉 Done!${NC}"
