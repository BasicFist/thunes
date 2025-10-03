#!/usr/bin/env bash
# Pre-deployment validation for Phase 13
# Runs comprehensive checks before autonomous paper trading deployment

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

FAIL_COUNT=0

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   THUNES Phase 13 Pre-Deployment Validation${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Function to check and report
check() {
    local test_name="$1"
    local command="$2"

    echo -e "${YELLOW}[CHECK]${NC} $test_name..."

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}   ✓ PASS${NC}"
        return 0
    else
        echo -e "${RED}   ✗ FAIL${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi
}

# 1. Environment Checks
echo -e "${BLUE}1. Environment Configuration${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

check "Virtual environment activated" "python -c 'import sys; sys.exit(0 if hasattr(sys, \"real_prefix\") or (hasattr(sys, \"base_prefix\") and sys.base_prefix != sys.prefix) else 1)'"

check ".env file exists" "[ -f .env ]"

check "Binance testnet API keys configured" "grep -q 'BINANCE_TESTNET_API_KEY=' .env"

check "Environment set to testnet" "grep -q 'ENVIRONMENT=testnet' .env || grep -q 'ENVIRONMENT=paper' .env"

echo ""

# 2. Telegram Configuration
echo -e "${BLUE}2. Telegram Bot Configuration${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

check "Telegram bot token configured" "grep -q 'TELEGRAM_BOT_TOKEN=' .env"

check "Telegram chat ID configured" "grep -q 'TELEGRAM_CHAT_ID=' .env"

if python scripts/verify_telegram.py > /dev/null 2>&1; then
    echo -e "${GREEN}   ✓ Telegram connectivity verified${NC}"
else
    echo -e "${YELLOW}   ⚠ Telegram not configured (optional but recommended)${NC}"
fi

echo ""

# 3. Dependencies
echo -e "${BLUE}3. Dependencies Check${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

check "python-binance installed" "python -c 'import binance'"

check "APScheduler installed" "python -c 'import apscheduler'"

check "vectorbt installed" "python -c 'import vectorbt'"

check "pandas installed" "python -c 'import pandas'"

echo ""

# 4. Module Imports
echo -e "${BLUE}4. Module Import Validation${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

check "Config module imports" "python -c 'from src.config import settings, ensure_directories'"

check "PaperTrader imports" "python -c 'from src.live.paper_trader import PaperTrader'"

check "RiskManager imports" "python -c 'from src.risk.manager import RiskManager'"

check "TradingScheduler imports" "python -c 'from src.orchestration.scheduler import TradingScheduler'"

check "CircuitBreaker imports" "python -c 'from src.utils.circuit_breaker import circuit_monitor'"

check "WebSocket stream imports" "python -c 'from src.data.ws_stream import BinanceWebSocketStream'"

echo ""

# 5. Directory Structure
echo -e "${BLUE}5. Directory Structure${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

check "logs directory exists" "[ -d logs ]"

check "artifacts directory exists" "[ -d artifacts ]"

check "data directory exists" "[ -d data ]"

check "scripts directory exists" "[ -d scripts ]"

echo ""

# 6. Risk Configuration
echo -e "${BLUE}6. Risk Management Configuration${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

check "MAX_LOSS_PER_TRADE configured" "grep -q 'MAX_LOSS_PER_TRADE=' .env"

check "MAX_DAILY_LOSS configured" "grep -q 'MAX_DAILY_LOSS=' .env"

check "MAX_POSITIONS configured" "grep -q 'MAX_POSITIONS=' .env"

# Validate risk limits are reasonable
MAX_LOSS=$(grep 'MAX_LOSS_PER_TRADE=' .env | cut -d'=' -f2 | tr -d '"' | tr -d ' ')
if [ -n "$MAX_LOSS" ] && [ "$(echo "$MAX_LOSS < 10" | bc -l)" -eq 1 ]; then
    echo -e "${GREEN}   ✓ Per-trade loss limit reasonable ($MAX_LOSS USDT)${NC}"
else
    echo -e "${YELLOW}   ⚠ Per-trade loss limit high (${MAX_LOSS:-undefined} USDT)${NC}"
fi

echo ""

# 7. Test Suite
echo -e "${BLUE}7. Test Suite Validation${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

echo "   Running core tests (this may take 30-60 seconds)..."
if source .venv/bin/activate && pytest tests/test_scheduler.py tests/test_risk_manager.py tests/test_circuit_breaker.py -v --tb=no -q > /tmp/thunes_test_output.txt 2>&1; then
    PASSED=$(grep -oP '\d+(?= passed)' /tmp/thunes_test_output.txt | head -1)
    echo -e "${GREEN}   ✓ Core tests passed ($PASSED tests)${NC}"
else
    FAILED=$(grep -oP '\d+(?= failed)' /tmp/thunes_test_output.txt | head -1)
    echo -e "${RED}   ✗ Core tests failed ($FAILED failures)${NC}"
    echo "   See /tmp/thunes_test_output.txt for details"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo ""

# 8. Exchange Connectivity
echo -e "${BLUE}8. Exchange Connectivity${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

if python -c "
from src.data.binance_client import BinanceDataClient
from src.config import settings
client = BinanceDataClient(testnet=True)
try:
    balance = client.client.get_account()
    print(f\"   Balance check successful\")
    exit(0)
except Exception as e:
    print(f\"   Error: {e}\")
    exit(1)
" 2>&1 | tee /tmp/binance_check.txt; then
    echo -e "${GREEN}   ✓ Binance testnet connection successful${NC}"
else
    echo -e "${RED}   ✗ Binance testnet connection failed${NC}"
    cat /tmp/binance_check.txt
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo ""

# 9. Audit Trail
echo -e "${BLUE}9. Audit Trail Setup${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

check "Audit trail file writable" "touch logs/audit_trail.jsonl && [ -w logs/audit_trail.jsonl ]"

if [ -f logs/audit_trail.jsonl ] && [ -s logs/audit_trail.jsonl ]; then
    ENTRIES=$(wc -l < logs/audit_trail.jsonl)
    echo -e "${GREEN}   ✓ Audit trail contains $ENTRIES entries${NC}"
else
    echo -e "${YELLOW}   ⚠ Audit trail empty (will be created on first trade)${NC}"
fi

echo ""

# 10. System Resources
echo -e "${BLUE}10. System Resources${NC}"
echo -e "${BLUE}────────────────────────────${NC}"

# Disk space (need at least 1GB)
DISK_AVAIL=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$DISK_AVAIL" -gt 1 ]; then
    echo -e "${GREEN}   ✓ Disk space sufficient (${DISK_AVAIL}GB available)${NC}"
else
    echo -e "${YELLOW}   ⚠ Low disk space (${DISK_AVAIL}GB available)${NC}"
fi

# Memory (need at least 500MB)
MEM_AVAIL=$(free -m | grep Mem | awk '{print $7}')
if [ "$MEM_AVAIL" -gt 500 ]; then
    echo -e "${GREEN}   ✓ Memory sufficient (${MEM_AVAIL}MB available)${NC}"
else
    echo -e "${YELLOW}   ⚠ Low memory (${MEM_AVAIL}MB available)${NC}"
fi

echo ""

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}   VALIDATION PASSED ✓${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}System is ready for Phase 13 deployment!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Start scheduler: nohup python -m src.orchestration.run_scheduler > logs/scheduler_stdout.log 2>&1 &"
    echo "2. Monitor logs: tail -f logs/scheduler.log"
    echo "3. Check Telegram for daily summaries (23:00 UTC)"
    echo "4. Review after 7 days for Phase 14 GO/NO-GO decision"
    echo ""
    exit 0
else
    echo -e "${RED}   VALIDATION FAILED ✗${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${RED}Found $FAIL_COUNT issue(s) that must be fixed before deployment.${NC}"
    echo ""
    echo "Common fixes:"
    echo "1. Missing credentials: Run ./scripts/setup_telegram.sh"
    echo "2. Test failures: Run pytest -v to see detailed errors"
    echo "3. Import errors: Run pip install -r requirements.txt"
    echo "4. Exchange connectivity: Verify API keys in .env"
    echo ""
    exit 1
fi
