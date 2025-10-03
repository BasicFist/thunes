#!/usr/bin/env bash
# Setup Telegram bot for THUNES alerts
# This script helps configure Telegram credentials in .env

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   THUNES Telegram Bot Setup${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create .env file first (copy from .env.example if available)"
    exit 1
fi

# Instructions
echo -e "${YELLOW}Step 1: Create Telegram Bot${NC}"
echo "1. Open Telegram and search for @BotFather"
echo "2. Send /newbot command"
echo "3. Follow instructions to name your bot"
echo "4. Copy the bot token (looks like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)"
echo ""

# Get bot token
read -p "Enter your Telegram bot token: " BOT_TOKEN

if [ -z "$BOT_TOKEN" ]; then
    echo -e "${RED}Error: Bot token cannot be empty${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 2: Get Chat ID${NC}"
echo "1. Start a chat with your bot in Telegram (send any message)"
echo "2. Visit: https://api.telegram.org/bot${BOT_TOKEN}/getUpdates"
echo "3. Find \"chat\":{\"id\":XXXXXXXX} in the JSON response"
echo "4. Copy the chat ID (positive or negative number)"
echo ""

# Get chat ID
read -p "Enter your chat ID: " CHAT_ID

if [ -z "$CHAT_ID" ]; then
    echo -e "${RED}Error: Chat ID cannot be empty${NC}"
    exit 1
fi

# Backup .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
echo -e "${GREEN}✓ Created backup: .env.backup.$(date +%Y%m%d_%H%M%S)${NC}"

# Check if Telegram config already exists
if grep -q "TELEGRAM_BOT_TOKEN" .env; then
    # Update existing config
    sed -i "s|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=\"${BOT_TOKEN}\"|" .env
    sed -i "s|^TELEGRAM_CHAT_ID=.*|TELEGRAM_CHAT_ID=\"${CHAT_ID}\"|" .env
    echo -e "${GREEN}✓ Updated existing Telegram configuration${NC}"
else
    # Add new config
    echo "" >> .env
    echo "# Telegram Alerts Configuration" >> .env
    echo "TELEGRAM_BOT_TOKEN=\"${BOT_TOKEN}\"" >> .env
    echo "TELEGRAM_CHAT_ID=\"${CHAT_ID}\"" >> .env
    echo -e "${GREEN}✓ Added Telegram configuration to .env${NC}"
fi

echo ""
echo -e "${YELLOW}Step 3: Test Configuration${NC}"
echo "Testing Telegram bot connectivity..."

# Test the bot
python3 << EOF
import sys
import os

# Add src to path
sys.path.insert(0, 'src')

# Set environment variables
os.environ['TELEGRAM_BOT_TOKEN'] = '${BOT_TOKEN}'
os.environ['TELEGRAM_CHAT_ID'] = '${CHAT_ID}'

try:
    from src.alerts.telegram import TelegramBot

    bot = TelegramBot()
    if bot.enabled:
        result = bot.send_message_sync("🚀 THUNES Telegram Bot Setup Complete!\n\nYour bot is configured and ready for Phase 13 deployment.")
        if result:
            print("\n${GREEN}✓ SUCCESS: Test message sent!${NC}")
            print("Check your Telegram to confirm you received it.")
            sys.exit(0)
        else:
            print("\n${RED}✗ FAILED: Could not send test message${NC}")
            sys.exit(1)
    else:
        print("\n${RED}✗ FAILED: Bot not enabled${NC}")
        sys.exit(1)
except Exception as e:
    print(f"\n${RED}✗ ERROR: {e}${NC}")
    sys.exit(1)
EOF

TEST_RESULT=$?

echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}   Telegram Setup Complete! ✓${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Run: source .venv/bin/activate"
    echo "2. Run: make test  (to verify all tests pass)"
    echo "3. Deploy Phase 13 autonomous paper trading"
    echo ""
else
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}   Telegram Setup Failed ✗${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "1. Verify bot token is correct"
    echo "2. Ensure you've sent at least one message to the bot"
    echo "3. Check chat ID is correct (positive or negative number)"
    echo "4. Try visiting: https://api.telegram.org/bot${BOT_TOKEN}/getUpdates"
    echo ""
    echo "To restore backup: cp .env.backup.* .env"
    exit 1
fi
