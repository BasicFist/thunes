# Telegram Bot Setup Guide

## Overview

THUNES uses Telegram for critical alerts and daily summaries. This guide walks you through setting up your Telegram bot in under 5 minutes.

## Quick Start

```bash
# Run automated setup script
./scripts/setup_telegram.sh

# Or verify existing configuration
python scripts/verify_telegram.py
```

## Manual Setup (Step-by-Step)

### Step 1: Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Choose a name for your bot (e.g., "THUNES Trading Bot")
4. Choose a username (must end in "bot", e.g., "thunes_trading_bot")
5. **Copy the bot token** - it looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

### Step 2: Get Your Chat ID

1. **Start a chat with your bot** - Send any message (e.g., "Hello")
2. Visit this URL in your browser (replace `<BOT_TOKEN>` with your token):
   ```
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```
3. Look for `"chat":{"id":XXXXXXXX}` in the JSON response
4. **Copy the chat ID** - it's a positive or negative number (e.g., `123456789` or `-987654321`)

**Example Response:**
```json
{
  "ok": true,
  "result": [
    {
      "update_id": 123456789,
      "message": {
        "message_id": 1,
        "from": {...},
        "chat": {
          "id": 987654321,  ← THIS IS YOUR CHAT ID
          "first_name": "John",
          "type": "private"
        },
        "date": 1234567890,
        "text": "Hello"
      }
    }
  ]
}
```

### Step 3: Add to .env

Add these lines to your `.env` file:

```bash
# Telegram Alerts Configuration
TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_CHAT_ID="987654321"
```

**Security Note**: Keep these values secret! Never commit them to Git.

### Step 4: Test Configuration

```bash
# Activate virtual environment
source .venv/bin/activate

# Test the bot
python scripts/verify_telegram.py
```

You should receive a test message in Telegram within seconds.

## What Alerts Will You Receive?

### 1. Kill-Switch Alerts (Critical) 🚨

**Trigger**: When daily loss exceeds `MAX_DAILY_LOSS` (default: 20 USDT)

**Example Message**:
```
🚨 KILL-SWITCH ACTIVATED

Trading has been halted due to loss limits.

Daily Loss: -25.00 USDT
Limit: -20.00 USDT

Action Required:
1. Review trades in logs/audit_trail.jsonl
2. Analyze what went wrong
3. Manually deactivate: risk_manager.deactivate_kill_switch()

System will remain halted until manual intervention.
```

### 2. Daily Summary (23:00 UTC) 📊

**Example Message**:
```
📊 THUNES Daily Summary (2025-10-03)

Performance:
• Closed Trades: 5
• Win Rate: 60.0% (3W / 2L)
• Total PnL: +12.50 USDT
• Sharpe Ratio: 1.75

Risk Status:
• Open Positions: 1/3
• Daily PnL: +12.50 USDT
• Kill-Switch: Inactive

System Health:
• Circuit Breakers: All OK
• WebSocket: Connected
• API Status: Operational

Next signal check: 2025-10-03 23:10 UTC
```

### 3. Parameter Decay Warning ⚠️

**Trigger**: When Sharpe ratio < 1.0 (critical if < 0.5)

**Example Message**:
```
⚠️ PARAMETER DECAY WARNING

Strategy performance declining:

Current Sharpe: 0.45 (Critical: < 0.5)
Rolling 7-day window
Last 14 trades analyzed

Action Required:
• Consider re-running optimization
• Review market regime changes
• Check if strategy assumptions still valid

Run: python -m src.optimize.run_optuna --trials 25
```

### 4. Re-Optimization Complete ✅

**Example Message**:
```
✅ Re-Optimization Complete

New parameters loaded:

Strategy: SMA Crossover
Fast Window: 12 → 15
Slow Window: 26 → 30

Backtest Results (90 days):
• Sharpe Ratio: 1.85
• Win Rate: 65.0%
• Max Drawdown: 8.5%

Parameters active starting next signal check.
```

## Troubleshooting

### "TelegramBot disabled: Missing token or chat_id"

**Cause**: Credentials not found in `.env`

**Fix**:
1. Verify `.env` contains `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
2. Check for typos in variable names (case-sensitive)
3. Ensure values are quoted: `TELEGRAM_BOT_TOKEN="your_token"`
4. Restart the scheduler after updating `.env`

### "Failed to send message"

**Possible Causes**:
1. **Invalid bot token** - Verify token is correct from @BotFather
2. **Invalid chat ID** - Ensure you've sent at least one message to the bot first
3. **Network issues** - Check firewall isn't blocking api.telegram.org
4. **Bot not started** - Send `/start` to your bot in Telegram

**Debug**:
```bash
# Test bot connectivity directly
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage" \
  -d "chat_id=<YOUR_CHAT_ID>" \
  -d "text=Test from THUNES"
```

### "Chat not found"

**Cause**: Chat ID is incorrect or you haven't started the bot

**Fix**:
1. Open Telegram and find your bot
2. Send any message to the bot (e.g., "Hello")
3. Get chat ID again from `/getUpdates` endpoint
4. Update `.env` with correct chat ID

## Security Best Practices

### 1. Protect Your Credentials

```bash
# Set restrictive permissions on .env
chmod 600 .env

# Verify permissions
ls -la .env
# Should show: -rw------- (only owner can read/write)
```

### 2. Never Commit Secrets

The `.gitignore` already excludes `.env`, but double-check:

```bash
# Verify .env is ignored
git status | grep .env
# Should show nothing (file is ignored)
```

### 3. Rotate Tokens Regularly

**After production deployment** (every 3-6 months):
1. Generate new bot token via @BotFather: `/token`
2. Update `.env` with new token
3. Restart scheduler
4. Revoke old token via @BotFather

## Advanced Configuration

### Custom Alert Thresholds

Edit `src/config.py` to customize alert triggers:

```python
# In .env
MAX_DAILY_LOSS=50.0  # Trigger kill-switch at -50 USDT
SHARPE_THRESHOLD=1.2  # Warn if Sharpe < 1.2 (default: 1.0)
SHARPE_CRITICAL=0.6   # Critical warning if < 0.6 (default: 0.5)
```

### Disable Telegram (Testing)

To run without Telegram (not recommended for production):

```bash
# In .env, comment out or remove:
# TELEGRAM_BOT_TOKEN="..."
# TELEGRAM_CHAT_ID="..."
```

System will log warnings but continue operation.

### Multiple Recipients (Group Chat)

To send alerts to a group:

1. Create Telegram group
2. Add your bot to the group
3. Send a message in the group
4. Get group chat ID from `/getUpdates` (usually negative number like `-123456789`)
5. Update `TELEGRAM_CHAT_ID` in `.env`

## Testing Checklist

Before deploying Phase 13, verify:

- [ ] Test message received successfully
- [ ] Bot responds to messages (optional, but good to verify)
- [ ] Kill-switch alert works (manually trigger with low limit)
- [ ] Daily summary format looks correct
- [ ] No permission errors in logs

**Test Kill-Switch Manually**:
```python
from src.risk.manager import RiskManager
from src.models.position import PositionTracker

# Temporarily lower limit to trigger
rm = RiskManager(
    position_tracker=PositionTracker(),
    max_daily_loss=5.0,  # Very low threshold
    enable_telegram=True
)

# This should trigger kill-switch and send Telegram alert
rm.record_loss(amount=10.0)
```

## Integration with Scheduler

The scheduler automatically uses Telegram if configured:

```python
# In src/orchestration/scheduler.py
if settings.telegram_bot_token and settings.telegram_chat_id:
    self.telegram_bot = TelegramBot()  # Auto-enabled
```

No code changes needed - just set the environment variables!

## FAQ

**Q: Can I use the same bot for multiple trading systems?**
A: Yes, but use different chat IDs (personal chat vs group chat) to separate alerts.

**Q: What if Telegram API is down?**
A: System continues operating. Alerts are logged locally and you can review `logs/audit_trail.jsonl`.

**Q: How much does Telegram cost?**
A: Free! Telegram bots have no API usage limits for personal use.

**Q: Can I customize alert messages?**
A: Yes, edit templates in `src/alerts/telegram.py` (methods: `send_kill_switch_alert`, `send_daily_summary`, etc.)

## Next Steps

After Telegram is configured:

1. ✅ Run: `python scripts/verify_telegram.py`
2. ✅ Check: Telegram message received
3. ✅ Run: `make test` (verify all tests pass)
4. 🚀 Deploy: Phase 13 autonomous paper trading

---

**Last Updated**: 2025-10-03
**Maintainer**: Mickael Souedan
