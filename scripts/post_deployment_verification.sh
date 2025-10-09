#!/usr/bin/env bash
# Post-Deployment Verification Script for Phase 13
# Runs immediate checks after deployment to verify system health
# Should be executed within first 10 minutes of deployment

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
echo -e "${BLUE}   THUNES Phase 13 Post-Deployment Verification${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "Checking system health after deployment..."
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
# 1. Process Health
# ========================================
echo -e "${BLUE}1. Process Health${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

if check "Scheduler process running" "[ -f /tmp/scheduler.pid ] && ps -p \$(cat /tmp/scheduler.pid) > /dev/null"; then
    PID=$(cat /tmp/scheduler.pid)
    echo "   Process ID: $PID"

    # Check how long it's been running
    UPTIME=$(ps -p $PID -o etime= | tr -d ' ')
    echo "   Uptime: $UPTIME"

    # Check memory usage
    MEM=$(ps -p $PID -o rss= | awk '{print $1/1024 " MB"}')
    echo "   Memory: $MEM"
else
    echo -e "${RED}   ERROR: Scheduler not running! Check logs for startup errors.${NC}"
fi

echo ""

# ========================================
# 2. Log Health
# ========================================
echo -e "${BLUE}2. Log Health${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

# Check for critical errors in last 50 lines
if [ -f logs/paper_trader.log ]; then
    CRITICAL_COUNT=$(tail -50 logs/paper_trader.log | grep -i "CRITICAL" | wc -l)
    ERROR_COUNT=$(tail -50 logs/paper_trader.log | grep -i "ERROR" | wc -l)

    if [ $CRITICAL_COUNT -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: No critical errors in recent logs"
    else
        echo -e "${RED}✗ FAIL${NC}: Found $CRITICAL_COUNT critical errors"
        echo "   Recent critical errors:"
        tail -50 logs/paper_trader.log | grep -i "CRITICAL" | tail -3
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi

    if [ $ERROR_COUNT -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: No errors in recent logs"
    else
        echo -e "${YELLOW}⚠ WARN${NC}: Found $ERROR_COUNT errors (review recommended)"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi
else
    echo -e "${YELLOW}⚠ WARN${NC}: Log file not created yet (may take a few minutes)"
    WARN_COUNT=$((WARN_COUNT + 1))
fi

echo ""

# ========================================
# 3. Risk Management Status
# ========================================
echo -e "${BLUE}3. Risk Management Status${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

python -c "
from src.risk.manager import RiskManager
from src.models.position import PositionTracker
import sys

try:
    rm = RiskManager(position_tracker=PositionTracker())
    status = rm.get_risk_status()

    print(f'Kill-switch active: {status[\"kill_switch_active\"]}')
    print(f'Daily P&L: {status[\"daily_pnl\"]} USDT')
    print(f'Open positions: {status[\"open_positions\"]}/{status[\"max_positions\"]}')
    print(f'Cool-down active: {status[\"cool_down_active\"]}')

    # Verify kill-switch is inactive (should be at deployment)
    if status['kill_switch_active']:
        print('❌ FAIL: Kill-switch should be inactive at deployment!')
        sys.exit(1)
    else:
        print('✅ Kill-switch inactive (expected at deployment)')

    sys.exit(0)
except Exception as e:
    print(f'❌ ERROR: Failed to check risk status: {e}')
    sys.exit(1)
" && echo "" || { echo ""; FAIL_COUNT=$((FAIL_COUNT + 1)); }

echo ""

# ========================================
# 4. Database Health
# ========================================
echo -e "${BLUE}4. Database Health${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

python -c "
from src.models.position import PositionTracker
import sys

try:
    pt = PositionTracker()
    count = pt.count_open_positions()
    print(f'✅ Position tracker accessible')
    print(f'   Open positions: {count}')

    # Check if DB file exists and is writable
    import os
    db_path = 'positions.db'  # Adjust if different
    if os.path.exists(db_path):
        if os.access(db_path, os.W_OK):
            print(f'✅ Database file writable: {db_path}')
        else:
            print(f'❌ Database file not writable: {db_path}')
            sys.exit(1)
    else:
        print(f'⚠️  Database file will be created on first trade')

    sys.exit(0)
except Exception as e:
    print(f'❌ ERROR: Database health check failed: {e}')
    sys.exit(1)
" && echo "" || { echo ""; FAIL_COUNT=$((FAIL_COUNT + 1)); }

echo ""

# ========================================
# 5. Audit Trail
# ========================================
echo -e "${BLUE}5. Audit Trail${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

if [ -f logs/audit_trail.jsonl ]; then
    # Check if file is writable
    if [ -w logs/audit_trail.jsonl ]; then
        echo -e "${GREEN}✓ PASS${NC}: Audit trail file writable"

        # Validate JSON format (if file has content)
        if [ -s logs/audit_trail.jsonl ]; then
            if tail -10 logs/audit_trail.jsonl | python -m json.tool > /dev/null 2>&1; then
                echo -e "${GREEN}✓ PASS${NC}: Audit trail format valid"
                ENTRIES=$(wc -l < logs/audit_trail.jsonl)
                echo "   Entries: $ENTRIES"
            else
                echo -e "${RED}✗ FAIL${NC}: Audit trail format invalid (corrupted JSON)"
                FAIL_COUNT=$((FAIL_COUNT + 1))
            fi
        else
            echo -e "${YELLOW}⚠ WARN${NC}: Audit trail empty (will be populated on first trade)"
            WARN_COUNT=$((WARN_COUNT + 1))
        fi
    else
        echo -e "${RED}✗ FAIL${NC}: Audit trail file not writable"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
else
    echo -e "${YELLOW}⚠ WARN${NC}: Audit trail file doesn't exist yet (will be created)"
    WARN_COUNT=$((WARN_COUNT + 1))
fi

echo ""

# ========================================
# 6. Telegram Connectivity (Optional)
# ========================================
echo -e "${BLUE}6. Telegram Connectivity (Optional)${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

python -c "
from src.alerts.telegram import TelegramBot
import sys

try:
    bot = TelegramBot()
    if bot.enabled:
        print('✅ Telegram bot configured')
        print(f'   Bot enabled: True')
        # Don't send test message here (would spam during checks)
    else:
        print('⚠️  Telegram not configured (optional but recommended)')
        print('   Bot enabled: False')

    sys.exit(0)
except Exception as e:
    print(f'⚠️  Telegram check failed: {e}')
    print('   (This is not a deployment blocker)')
    sys.exit(0)  # Don't fail deployment for Telegram issues
" && echo "" || { echo ""; }

echo ""

# ========================================
# 7. Exchange Connectivity
# ========================================
echo -e "${BLUE}7. Exchange Connectivity${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

python -c "
from src.data.binance_client import BinanceDataClient
import sys

try:
    client = BinanceDataClient(testnet=True)
    account = client.client.get_account()

    print('✅ Binance testnet connection active')
    print(f'   Can trade: {account.get(\"canTrade\")}')
    print(f'   Can withdraw: {account.get(\"canWithdraw\")}')

    # Verify withdrawal is disabled
    if account.get('canWithdraw', True):
        print('❌ CRITICAL: Withdrawal enabled! This is a security risk.')
        sys.exit(1)

    sys.exit(0)
except Exception as e:
    print(f'❌ ERROR: Exchange connectivity failed: {e}')
    sys.exit(1)
" && echo "" || { echo ""; FAIL_COUNT=$((FAIL_COUNT + 1)); }

echo ""

# ========================================
# 8. Resource Usage
# ========================================
echo -e "${BLUE}8. Resource Usage${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

if [ -f /tmp/scheduler.pid ]; then
    PID=$(cat /tmp/scheduler.pid)

    # Memory check
    MEM_MB=$(ps -p $PID -o rss= | awk '{print $1/1024}')
    if (( $(echo "$MEM_MB < 1024" | bc -l) )); then
        echo -e "${GREEN}✓ PASS${NC}: Memory usage acceptable (${MEM_MB} MB < 1024 MB)"
    else
        echo -e "${YELLOW}⚠ WARN${NC}: Memory usage high (${MEM_MB} MB)"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi

    # CPU check (if available)
    CPU=$(ps -p $PID -o %cpu= | tr -d ' ')
    echo "   CPU usage: ${CPU}%"

    # Disk space
    DISK_AVAIL=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "$DISK_AVAIL" -gt 1 ]; then
        echo -e "${GREEN}✓ PASS${NC}: Disk space sufficient (${DISK_AVAIL}GB available)"
    else
        echo -e "${YELLOW}⚠ WARN${NC}: Low disk space (${DISK_AVAIL}GB available)"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi
fi

echo ""

# ========================================
# 9. Recent Activity
# ========================================
echo -e "${BLUE}9. Recent Activity${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

if [ -f logs/paper_trader.log ]; then
    echo "Last 5 log entries:"
    tail -5 logs/paper_trader.log | sed 's/^/   /'
else
    echo -e "${YELLOW}⚠ WARN${NC}: No log activity yet (system just started)"
fi

echo ""

# ========================================
# Summary
# ========================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "Verification Results:"
echo "  ✓ Passed:   $((9 - FAIL_COUNT - WARN_COUNT))"
echo "  ✗ Failed:   $FAIL_COUNT"
echo "  ⚠ Warnings: $WARN_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ DEPLOYMENT VERIFIED${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    if [ $WARN_COUNT -gt 0 ]; then
        echo "⚠️  Note: $WARN_COUNT warnings detected. Review above for details."
        echo "   These are not critical but should be monitored."
    fi
    echo ""
    echo "System is operational. Continue monitoring:"
    echo "  - Watch logs: tail -f logs/paper_trader.log"
    echo "  - Check health: bash /tmp/health_check.sh"
    echo "  - Review metrics in Telegram (if configured)"
    echo ""
    echo "Next check: T+1 hour"
    echo ""
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ DEPLOYMENT VERIFICATION FAILED${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "⚠️  $FAIL_COUNT critical issues detected."
    echo ""
    echo "Action required:"
    echo "1. Review failures above"
    echo "2. Check logs: tail -50 logs/paper_trader.log"
    echo "3. Fix issues"
    echo "4. Re-run verification: bash scripts/post_deployment_verification.sh"
    echo ""
    echo "If issues persist, consider emergency stop:"
    echo "  pkill -9 -f scheduler"
    echo ""
    exit 1
fi
