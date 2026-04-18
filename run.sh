#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Rotation Intel — Setup & Run
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ROTATION INTEL — Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 required. Install from https://python.org"
    exit 1
fi

echo "✓ Python $(python3 --version)"

# Create venv
if [ ! -d "venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install deps
echo "→ Installing dependencies..."
pip install -q -r requirements.txt

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CONFIGURATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Created .env from template."
    echo ""
    echo "   REQUIRED (for AI synthesis):"
    echo "   → ANTHROPIC_API_KEY  https://console.anthropic.com"
    echo "      Cost: ~\$0.05-0.15 per synthesis run"
    echo ""
    echo "   OPTIONAL (for live narrative signals):"
    echo "   → TELEGRAM_API_ID    https://my.telegram.org/apps"
    echo "   → TELEGRAM_API_HASH  (same URL)"
    echo "   → TELEGRAM_PHONE     Your phone number"
    echo "      Cost: FREE"
    echo ""
    echo "   OPTIONAL (late signal / exit indicator):"
    echo "   → REDDIT_CLIENT_ID   https://reddit.com/prefs/apps"
    echo "   → REDDIT_CLIENT_SECRET"
    echo "      Cost: FREE"
    echo ""
    echo "   Edit .env then run this script again."
    echo ""
    exit 0
fi

echo "✓ .env found"

# Check required keys
ANTHROPIC_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d'=' -f2)
if [ "$ANTHROPIC_KEY" = "your_key_here" ] || [ -z "$ANTHROPIC_KEY" ]; then
    echo ""
    echo "⚠️  ANTHROPIC_API_KEY not set in .env"
    echo "   The system will run with mock synthesis data."
    echo "   Get your key: https://console.anthropic.com"
    echo ""
fi

TELEGRAM_ID=$(grep TELEGRAM_API_ID .env | cut -d'=' -f2)
if [ "$TELEGRAM_ID" = "your_api_id_here" ] || [ -z "$TELEGRAM_ID" ]; then
    echo "⚠️  Telegram not configured — narrative signals will use mock data"
    echo "   Get credentials: https://my.telegram.org/apps (free)"
    echo ""
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STARTING SERVER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Dashboard: http://localhost:8000"
echo "  API:       http://localhost:8000/api/synthesis"
echo ""
echo "  Pipeline runs automatically every 6 hours."
echo "  Click ▶ RUN NOW in dashboard to trigger manually."
echo ""
echo "  Ctrl+C to stop."
echo ""

python3 server.py
