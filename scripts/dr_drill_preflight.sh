#!/usr/bin/env bash
# Disaster Recovery Drill Pre-Flight Checklist
# Verifies all prerequisites are met before executing DR drill
# Expected runtime: ~5 minutes

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

FAIL_COUNT=0
WARN_COUNT=0

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Disaster Recovery Drill - Pre-Flight Checklist${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "This script verifies all prerequisites for executing the DR drill."
echo "Expected runtime: ~5 minutes"
echo ""

# Function to check and report
check() {
    local test_name="$1"
    local command="$2"

    echo -n "[CHECK] $test_name... "

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi
}

warn_check() {
    local test_name="$1"
    local command="$2"

    echo -n "[CHECK] $test_name... "

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ WARN${NC}"
        WARN_COUNT=$((WARN_COUNT + 1))
        return 1
    fi
}

# ========================================
# 1. Environment Configuration
# ========================================
echo -e "${BLUE}1. Environment Configuration${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

check "Virtual environment activated" "[ ! -z \"\$VIRTUAL_ENV\" ]" || {
    echo -e "${RED}   ERROR: Virtual environment not activated${NC}"
    echo "   Run: source .venv/bin/activate"
}

check ".env file exists" "[ -f .env ]" || {
    echo -e "${RED}   ERROR: .env file missing${NC}"
    echo "   Copy .env.example to .env and configure"
}

check "Required environment variables set" "[ ! -z \"\${BINANCE_TESTNET_API_KEY:-}\" ] && [ ! -z \"\${BINANCE_TESTNET_API_SECRET:-}\" ]" || {
    echo -e "${RED}   ERROR: Binance testnet credentials not configured${NC}"
    echo "   Check .env has BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET"
}

echo ""

# ========================================
# 2. Telegram Bot Configuration
# ========================================
echo -e "${BLUE}2. Telegram Bot Configuration${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

if [ ! -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ ! -z "${TELEGRAM_CHAT_ID:-}" ]; then
    echo -e "${GREEN}✓ PASS${NC}: Telegram credentials configured"

    # Test telegram connectivity
    python -c "
from src.alerts.telegram import TelegramBot
import sys

try:
    bot = TelegramBot()
    if bot.enabled:
        print('✅ Telegram bot operational')
        # Send test message
        bot.send_message_sync('🧪 DR Drill Pre-Flight Check: Telegram connectivity test')
        print('✅ Test message sent successfully')
        sys.exit(0)
    else:
        print('⚠️ Telegram bot disabled in configuration')
        sys.exit(1)
except Exception as e:
    print(f'❌ Telegram connectivity failed: {e}')
    sys.exit(1)
" && echo "" || {
    echo ""
    echo -e "${YELLOW}⚠ WARN${NC}: Telegram connectivity issues detected"
    echo "   DR drill requires Telegram for alert verification"
    WARN_COUNT=$((WARN_COUNT + 1))
}
else
    echo -e "${RED}✗ FAIL${NC}: Telegram not configured"
    echo "   Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env"
    echo "   DR drill requires Telegram for alert verification"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo ""

# ========================================
# 3. Exchange Connectivity
# ========================================
echo -e "${BLUE}3. Exchange Connectivity${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

python -c "
from src.data.binance_client import BinanceDataClient
import sys

try:
    client = BinanceDataClient(testnet=True)
    account = client.client.get_account()

    print('✅ Binance testnet connection active')
    print(f'   Can trade: {account.get(\"canTrade\")}')
    print(f'   Account type: {account.get(\"accountType\")}')

    # Check balance
    usdt_balance = next((b for b in account['balances'] if b['asset'] == 'USDT'), None)
    if usdt_balance:
        balance = float(usdt_balance['free'])
        print(f'   USDT balance: {balance:.2f}')
        if balance < 100:
            print(f'⚠️  Low balance: Consider requesting testnet funds')
            print(f'   Get funds at: testnet.binance.vision')

    sys.exit(0)
except Exception as e:
    print(f'❌ ERROR: Exchange connectivity failed: {e}')
    print('   Check API keys are valid for testnet')
    sys.exit(1)
" && echo "" || {
    echo ""
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

echo ""

# ========================================
# 4. Position Tracker Operational
# ========================================
echo -e "${BLUE}4. Position Tracker Operational${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

python -c "
from src.models.position import PositionTracker
import sys

try:
    pt = PositionTracker()
    open_count = pt.count_open_positions()

    print(f'✅ Position tracker initialized')
    print(f'   Current open positions: {open_count}')

    if open_count == 0:
        print('⚠️  No open positions - DR drill Test 1 requires at least one position')
        print('   Create a position before starting drill or skip to Test 3')

    sys.exit(0)
except Exception as e:
    print(f'❌ ERROR: Position tracker initialization failed: {e}')
    sys.exit(1)
" && echo "" || {
    echo ""
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

echo ""

# ========================================
# 5. Risk Manager Operational
# ========================================
echo -e "${BLUE}5. Risk Manager Operational${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
import sys

try:
    rm = RiskManager(position_tracker=PositionTracker())
    status = rm.get_risk_status()

    print('✅ Risk manager initialized')
    print(f'   Kill-switch active: {status[\"kill_switch_active\"]}')
    print(f'   Daily P&L: {status[\"daily_pnl\"]} USDT')
    print(f'   Open positions: {status[\"open_positions\"]}/{status[\"max_positions\"]}')

    # Warn if kill-switch is already active
    if status['kill_switch_active']:
        print('⚠️  Kill-switch is currently ACTIVE')
        print('   Deactivate before starting drill or skip to Test 2')

    sys.exit(0)
except Exception as e:
    print(f'❌ ERROR: Risk manager initialization failed: {e}')
    sys.exit(1)
" && echo "" || {
    echo ""
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

echo ""

# ========================================
# 6. Audit Trail Setup
# ========================================
echo -e "${BLUE}6. Audit Trail Setup${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

if [ -f logs/audit_trail.jsonl ]; then
    # Validate JSON format
    if python -c "
import json
with open('logs/audit_trail.jsonl') as f:
    for line in f:
        json.loads(line)
" 2>/dev/null; then
        echo -e "${GREEN}✓ PASS${NC}: Audit trail file exists and valid"
        ENTRIES=$(wc -l < logs/audit_trail.jsonl)
        echo "   Entries: $ENTRIES"
    else
        echo -e "${RED}✗ FAIL${NC}: Audit trail format invalid"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    # Check writeable
    if [ -w logs/audit_trail.jsonl ]; then
        echo -e "${GREEN}✓ PASS${NC}: Audit trail writable"
    else
        echo -e "${RED}✗ FAIL${NC}: Audit trail not writable"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
else
    echo -e "${YELLOW}⚠ WARN${NC}: Audit trail file doesn't exist (will be created)"
    WARN_COUNT=$((WARN_COUNT + 1))
fi

echo ""

# ========================================
# 7. Required Files Present
# ========================================
echo -e "${BLUE}7. Required Files Present${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

check "DR drill guide exists" "[ -f scripts/disaster_recovery_drill.md ]"
check "Operational runbook exists" "[ -f docs/OPERATIONAL-RUNBOOK.md ]"
check "Post-deployment script exists" "[ -f scripts/post_deployment_verification.sh ]"
check "Pre-deployment script exists" "[ -f scripts/pre_deployment_validation.sh ]"

echo ""

# ========================================
# 8. System Resources
# ========================================
echo -e "${BLUE}8. System Resources${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

# Disk space check
DISK_AVAIL=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$DISK_AVAIL" -gt 1 ]; then
    echo -e "${GREEN}✓ PASS${NC}: Disk space sufficient (${DISK_AVAIL}GB available)"
else
    echo -e "${YELLOW}⚠ WARN${NC}: Low disk space (${DISK_AVAIL}GB available)"
    WARN_COUNT=$((WARN_COUNT + 1))
fi

# Memory check
TOTAL_MEM=$(free -m | awk 'NR==2{print $2}')
AVAIL_MEM=$(free -m | awk 'NR==2{print $7}')
if [ "$AVAIL_MEM" -gt 512 ]; then
    echo -e "${GREEN}✓ PASS${NC}: Memory available (${AVAIL_MEM}MB / ${TOTAL_MEM}MB)"
else
    echo -e "${YELLOW}⚠ WARN${NC}: Low memory (${AVAIL_MEM}MB available)"
    WARN_COUNT=$((WARN_COUNT + 1))
fi

echo ""

# ========================================
# Summary
# ========================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "Pre-Flight Check Results:"
echo "  ✓ Passed:   $((8 - FAIL_COUNT - WARN_COUNT))"
echo "  ✗ Failed:   $FAIL_COUNT"
echo "  ⚠ Warnings: $WARN_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ PRE-FLIGHT CHECK PASSED${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    if [ $WARN_COUNT -gt 0 ]; then
        echo "⚠️  Note: $WARN_COUNT warnings detected (non-blocking)"
        echo "   Review warnings above before proceeding"
        echo ""
    fi
    echo "✅ All prerequisites met for DR drill execution"
    echo ""
    echo "Next steps:"
    echo "1. Review the DR drill guide:"
    echo "   cat scripts/disaster_recovery_drill.md"
    echo ""
    echo "2. Execute the drill (2 hours):"
    echo "   - Follow step-by-step procedures"
    echo "   - Record results in drill document"
    echo "   - Update runbook with any corrections"
    echo ""
    echo "3. After drill completion:"
    echo "   - Update deployment readiness (51% → 72%)"
    echo "   - Proceed with Phase 13 deployment"
    echo ""
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ PRE-FLIGHT CHECK FAILED${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "⚠️  $FAIL_COUNT critical issues detected"
    echo ""
    echo "Action required:"
    echo "1. Review failures above"
    echo "2. Fix configuration issues"
    echo "3. Re-run pre-flight check: bash scripts/dr_drill_preflight.sh"
    echo ""
    echo "❌ DO NOT proceed with DR drill until all checks pass"
    echo ""
    exit 1
fi
