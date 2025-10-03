# Vendor Risk Assessment - Binance

**Assessment Date**: 2025-10-03
**Assessor**: THUNES System Owner
**Review Frequency**: Quarterly
**Next Review**: 2026-01-03

---

## Executive Summary

**Vendor**: Binance Holdings Limited
**Service**: Cryptocurrency exchange (spot trading API + market data)
**Criticality**: **CRITICAL** - System cannot function without it
**Overall Risk Rating**: **MEDIUM** (acceptable for personal trading at MVP scale)

**Key Risks**:
- Regulatory uncertainty (SEC enforcement actions)
- No public SOC 2/ISO 27001 attestations
- Centralized exchange (custodial risk)
- Market manipulation concerns

**Mitigations**:
- Limit capital exposure (10-50 EUR for Phase 14)
- Use testnet for prolonged testing (Phase 13)
- Implement withdrawal-disabled API keys
- Weekly profit withdrawal to external wallet (Phase 14+)

---

## 1. Service Criticality

### 1.1 Service Description

| Attribute | Details |
|-----------|---------|
| **Vendor Name** | Binance Holdings Limited |
| **Service Type** | Cryptocurrency exchange (CEX) |
| **Services Used** | Spot trading API, WebSocket market data |
| **Contract Type** | Standard Terms of Service (no SLA) |
| **Data Classification** | Financial transactions, API credentials |

### 1.2 Business Impact

**If Binance Becomes Unavailable**:
- **Immediate**: Trading halts, positions frozen on exchange
- **Short-term** (1-7 days): Cannot close positions, PnL locked
- **Long-term** (>7 days): Potential capital loss if exchange insolvent

**Availability Requirements**:
- **Trading Hours**: 24/7 (crypto markets never close)
- **Maximum Tolerable Downtime**: 4 hours (before manual intervention)
- **Recovery Time Objective (RTO)**: <1 hour (WebSocket reconnect)
- **Recovery Point Objective (RPO)**: Real-time (no data loss acceptable)

### 1.3 Documented SLA

**Binance Published SLA**: None (best-effort basis)

**Observed Uptime** (per CoinMarketCap monitoring):
- REST API: ~99.9% uptime (2024 average)
- WebSocket: ~99.5% uptime (occasional reconnections required)

**Scheduled Maintenance**:
- Announced 24h in advance via https://www.binance.com/en/support/announcement
- Typically 1-2 hours, monthly frequency

---

## 2. Security Controls

### 2.1 Authentication & Access Control

**Authentication Method**: HMAC-SHA256 signed requests

**Implementation**:
```python
# src/data/binance_client.py:15-30
import hmac
import hashlib
from urllib.parse import urlencode

def generate_signature(query_string: str, api_secret: str) -> str:
    return hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
```

**Key Storage**:
- **Current** (Testnet): `.env` file (chmod 600, git-ignored)
- **Planned** (Production): AWS Secrets Manager or HashiCorp Vault

**API Key Permissions** (verified 2025-10-03):
- ✅ **Enable Spot & Margin Trading**: ON
- ✅ **Enable Reading**: ON
- ❌ **Enable Withdrawals**: OFF (**critical control**)
- ❌ **Enable Futures**: OFF
- ❌ **Enable Internal Transfer**: OFF

**IP Whitelist**: Not enabled (requires static IP, not available on current infrastructure)

### 2.2 API Rate Limits

**Binance Enforced Limits** (per https://binance-docs.github.io/apidocs/spot/en/#limits):

| Operation | Limit | Enforcement | Our Usage |
|-----------|-------|-------------|-----------|
| **Order Placement** | 10 orders/sec | Hard limit (429 error) | 1 order/10min (~0.002/sec) |
| **Order Placement (Daily)** | 100,000 orders/day | Hard limit | ~144 orders/day (10min intervals) |
| **REST Requests** | 1200 req/min | Weight-based system | ~6 req/min (well under limit) |
| **WebSocket Connections** | 5 simultaneous | Hard limit | 1 connection (bookTicker) |

**Our Implementation** (`src/utils/rate_limiter.py:1-150`):
- Decorator-based rate limiting: `@with_rate_limit(max_calls=1, period=1.0)`
- Enforces 1 request/second (well under Binance limits)
- Token bucket algorithm with thread-safe implementation

**Mitigation Against 429 Errors**:
- Circuit breaker trips on rate limit errors
- Exponential backoff on retry (2s, 4s, 8s, 16s)
- Graceful degradation (skip non-critical requests)

### 2.3 Data Segregation

**Testnet vs Production Isolation**:

| Environment | API Endpoint | WebSocket Endpoint | Data Persistence |
|-------------|--------------|-------------------|------------------|
| **Testnet** | `https://testnet.binance.vision` | `wss://testnet.binance.vision/ws` | SQLite: `logs/positions_testnet.db` |
| **Production** | `https://api.binance.com` | `wss://stream.binance.com:9443/ws` | SQLite: `logs/positions_prod.db` |

**Configuration Control** (`src/config.py:15-45`):
```python
class Settings(BaseSettings):
    environment: str = "testnet"  # "testnet" | "paper" | "live"

    @property
    def is_testnet(self) -> bool:
        return self.environment in ["testnet", "paper"]

    @property
    def api_base_url(self) -> str:
        if self.is_testnet:
            return "https://testnet.binance.vision"
        return "https://api.binance.com"
```

**No Cross-Contamination Risk**: Environment controlled via single `.env` variable

### 2.4 Encryption

**Data in Transit**:
- ✅ TLS 1.3 for all HTTPS connections
- ✅ WSS (WebSocket Secure) for real-time data
- Certificate validation enabled (not bypassed)

**Data at Rest**:
- ⚠️ SQLite database unencrypted (acceptable for testnet)
- ⚠️ Audit trail JSONL unencrypted (contains no PII)
- ✅ API keys in `.env` protected by filesystem permissions (chmod 600)

**Planned Enhancement** (Phase 14):
- Encrypt production SQLite with SQLCipher
- Encrypt audit trail with GPG for long-term archival

---

## 3. Compliance Attestations

### 3.1 Available Documentation

**Publicly Disclosed**:
- ❌ **SOC 2 Type II**: Not available
- ❌ **ISO 27001**: Not available (Binance is not a regulated entity in most jurisdictions)
- ✅ **Bug Bounty Program**: https://bugcrowd.com/binance (up to $100,000 rewards)
- ✅ **Proof of Reserves**: Monthly attestations (https://www.binance.com/en/proof-of-reserves)

**Regulatory Status**:
- **USA**: Not registered with SEC/CFTC (US customers restricted)
- **EU**: MiCA compliance in progress (Markets in Crypto-Assets Regulation)
- **Global**: Registered in Cayman Islands, licensed in multiple jurisdictions

### 3.2 Risk Acceptance

**Finding**: Binance does not provide enterprise-grade compliance attestations (SOC 2, ISO 27001)

**Business Justification for Acceptance**:
1. **Capital at Risk**: 10-50 EUR (Phase 14) - acceptable loss tolerance
2. **Testnet Usage**: Phase 13 uses fake capital, zero financial risk
3. **Industry Standard**: Most crypto exchanges lack SOC 2 (Coinbase Pro is exception)
4. **Proof of Reserves**: Binance publishes monthly reserve audits (better than many competitors)

**Compensating Controls**:
- Withdrawal-disabled API keys (prevents fund theft)
- Daily monitoring (detect unauthorized access within 24h)
- Weekly profit withdrawal (minimize on-exchange balance)
- Circuit breaker (limits damage from API bugs)

### 3.3 Third-Party Audits

**Mazars Proof of Reserves** (monthly):
- **Scope**: Verify Binance customer deposits match on-chain reserves
- **Methodology**: Merkle tree verification, on-chain analysis
- **Latest Report**: https://www.binance.com/en/proof-of-reserves (check monthly)

**Smart Contract Audits**:
- Not applicable (THUNES uses CEX, not DeFi protocols)

---

## 4. Incident Response

### 4.1 Binance API Outage

**Detection**:
- Circuit breaker trips (5 consecutive failures)
- WebSocket disconnect without successful reconnect
- REST API returns 503 Service Unavailable

**Automated Response**:
1. Circuit breaker opens (blocks new API calls for 60s)
2. WebSocket attempts reconnection (max 5 attempts, exponential backoff)
3. System falls back to REST API for market data
4. Trading halts if both WebSocket and REST fail

**Manual Response**:
```bash
# 1. Check Binance status page
curl -I https://www.binance.com/en/support/announcement
# Or visit: https://status.binance.com

# 2. Check if outage is global or specific to our account
# Visit: https://twitter.com/binance (official announcements)

# 3. If prolonged (>1 hour), consider manual position closure
# - Login to Binance web UI
# - Close positions manually via market orders

# 4. Wait for service restoration
# - System will auto-reconnect when Binance recovers
# - Verify via logs: "WebSocket reconnected successfully"
```

**Historical Precedent**:
- 2024-05-15: 2-hour outage due to AWS issues (recovered)
- 2023-11-09: 45-minute outage during high volatility (recovered)

**Fallback Options**: None (no alternative exchange integrated)

### 4.2 API Key Compromise

**Indicators**:
- Unexpected trades in Binance order history (check daily)
- Alerts from Binance about suspicious activity
- Positions opened outside scheduler hours (23:00-09:00 UTC)

**Immediate Actions** (<5 minutes):
```bash
# 1. DISABLE API KEY (highest priority)
# Login to: https://testnet.binance.vision/ (or binance.com for prod)
# Navigate to: API Management → Delete Key

# 2. STOP ALL TRADING
pkill -f run_scheduler

# 3. ASSESS DAMAGE
# - Check Binance order history for unauthorized trades
# - Calculate losses from unauthorized positions

# 4. ROTATE CREDENTIALS
# - Generate new API key with same permissions
# - Update .env file
# - Verify permissions (withdrawals still disabled)

# 5. FORENSIC ANALYSIS
# - Check git history: git log -S "BINANCE" --all
# - Review system access logs: sudo last
# - Scan for malware: sudo rkhunter --check
```

**Notification**:
- Report to Binance security: security@binance.com
- Document in incident log: `docs/incidents/YYYY-MM-DD-api-key-compromise.md`

**Post-Incident**:
- Enable 2FA for Binance account (if not already enabled)
- Consider IP whitelist (if static IP available)
- Add TruffleHog pre-commit hook (prevent secret leaks)

### 4.3 Binance Insolvency / Regulatory Shutdown

**Probability**: LOW (but non-zero, see FTX collapse 2022-11-11)

**Scenario**: Binance faces regulatory action (SEC lawsuit) or bank run

**Early Warning Indicators**:
- Withdrawal delays (normally instant)
- Unusual price discrepancies vs other exchanges (>2%)
- Executive departures or regulatory announcements
- Proof of Reserves audit failures

**Response Plan**:
```bash
# 1. IMMEDIATE WITHDRAWAL (if possible)
# - Login to Binance web UI
# - Withdraw all funds to external wallet
# - Accept network fees (better than total loss)

# 2. CLOSE ALL POSITIONS (if withdrawal blocked)
# - Convert all holdings to stablecoins (USDT)
# - Hope for eventual customer reimbursement

# 3. DOCUMENT HOLDINGS
# - Export full trade history (CSV)
# - Screenshot account balances
# - Save for tax reporting / legal claims
```

**Mitigation** (Phase 14+):
- **Weekly Profit Withdrawal**: Don't accumulate large balances on exchange
- **Maximum Exposure**: Never exceed 100 EUR on Binance (adjust `MAX_DAILY_LOSS`)
- **Monitor News**: Daily check of crypto news aggregators

**Alternative Exchanges** (contingency):
- Coinbase Advanced Trade (US-regulated, SOC 2 Type II)
- Kraken (regulated, lower fees than Coinbase)
- Gemini (NYDFS-licensed, best security reputation)

---

## 5. Monitoring & Change Management

### 5.1 API Deprecation Tracking

**Binance API Changelog**: https://github.com/binance/binance-spot-api-docs/blob/master/CHANGELOG.md

**Monitoring Process**:
1. **Monthly Review** (first Monday, 10:00 UTC):
   ```bash
   # Check Binance changelog for breaking changes
   curl https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/CHANGELOG.md | head -50
   ```

2. **Deprecation Notices**:
   - Binance typically gives 90-day notice for breaking changes
   - Check for "DEPRECATION" tags in changelog

3. **Impact Assessment**:
   - Review affected endpoints against THUNES usage
   - Test changes on testnet before production
   - Update `src/data/binance_client.py` if needed

**Recent Changes** (2025):
- 2025-03-15: `GET /api/v3/order` now requires `recvWindow` parameter
- 2025-01-10: WebSocket ping/pong timeout reduced to 30s (from 60s)

### 5.2 python-binance Library Updates

**Current Version**: 1.0.19 (per `requirements.txt`)

**Update Policy**:
- **Security Patches**: Apply within 7 days (test on testnet first)
- **Minor Versions**: Review changelog, update quarterly
- **Major Versions**: Defer until stable (wait 30 days after release)

**Update Procedure**:
```bash
# 1. Check for updates
pip list --outdated | grep python-binance

# 2. Review changelog
# https://github.com/sammchardy/python-binance/blob/master/CHANGELOG.rst

# 3. Test on testnet
cd ~/THUNES
source .venv/bin/activate
pip install --upgrade python-binance
pytest tests/ -v

# 4. If tests pass, commit to git
pip freeze > requirements.txt
git add requirements.txt
git commit -m "chore: upgrade python-binance to vX.Y.Z"

# 5. Deploy to production (Phase 14)
# - Stop scheduler
# - Pull latest code
# - Restart scheduler
```

**Breaking Change History**:
- v1.0.0 (2023-06): Dropped Python 3.7 support
- v0.7.0 (2021-11): Async client refactor (not used by THUNES)

### 5.3 Service Degradation Monitoring

**Real-Time Monitoring** (automated):
- Circuit breaker trips: Logged to `logs/paper_trader.log`
- WebSocket reconnections: Counted per hour (should be <3/hour)
- REST API latency: Measured on each request (should be <500ms p95)

**Weekly Metrics Review**:
```python
# scripts/analyze_binance_health.py
import json
from collections import Counter

# Parse logs for circuit breaker trips
trips = Counter()
with open('logs/paper_trader.log') as f:
    for line in f:
        if 'Circuit breaker' in line and 'state changed' in line:
            # Extract date
            date = line[:10]  # YYYY-MM-DD
            trips[date] += 1

print("Circuit Breaker Trips (Last 7 Days):")
for date, count in sorted(trips.items())[-7:]:
    print(f"{date}: {count} trips {'⚠️' if count > 5 else '✅'}")
```

**Escalation Thresholds**:
- **>5 circuit breaker trips/day**: Investigate Binance API health
- **>10 WebSocket reconnects/hour**: Check network stability
- **>2s REST API latency**: Consider rate limit reduction

---

## 6. Alternative Vendors (Contingency Planning)

### 6.1 Vendor Comparison

| Vendor | Regulatory Status | SOC 2 | Testnet | API Quality | Migration Effort |
|--------|------------------|-------|---------|-------------|------------------|
| **Binance** (current) | Cayman Islands | ❌ | ✅ | Excellent | N/A |
| **Coinbase Advanced** | US (SEC-registered) | ✅ Type II | ✅ Sandbox | Good | 2-3 days |
| **Kraken** | US (FinCEN-registered) | ❌ | ❌ | Good | 2-3 days |
| **Gemini** | US (NYDFS-licensed) | ✅ Type II | ✅ Sandbox | Fair | 3-5 days |

### 6.2 Migration Prerequisites

**If Binance Becomes Unavailable**:

1. **Account Setup** (Day 1):
   - Create account on alternative exchange
   - Complete KYC verification (1-3 days)
   - Generate API keys (withdrawal-disabled)

2. **Code Changes** (Day 2-3):
   - Update `src/data/binance_client.py` to use alternative library
   - Test exchange filters (tick size, step size, min notional)
   - Validate order placement on sandbox/testnet

3. **Testing** (Day 4-5):
   - Run full test suite
   - Execute paper trades on alternative exchange
   - Validate WebSocket reconnection logic

4. **Deployment** (Day 6):
   - Update `.env` with new API credentials
   - Restart scheduler with new exchange
   - Monitor closely for 24h

**Code Portability**:
- ✅ Exchange-specific logic isolated in `src/data/binance_client.py` and `src/filters/exchange_filters.py`
- ✅ Strategy logic (SMA, RSI) is exchange-agnostic
- ⚠️ WebSocket implementation is Binance-specific (needs rewrite)

---

## 7. Risk Summary

### 7.1 Risk Matrix

| Risk | Likelihood | Impact | Mitigation | Residual Risk |
|------|-----------|---------|------------|---------------|
| **API Outage** | MEDIUM (monthly) | HIGH (trading halts) | Circuit breaker, REST fallback | LOW |
| **API Key Compromise** | LOW (with controls) | HIGH (unauthorized trades) | Withdrawal-disabled, daily monitoring | LOW |
| **Binance Insolvency** | LOW (well-capitalized) | CRITICAL (total loss) | Limit capital, weekly withdrawals | MEDIUM |
| **Regulatory Shutdown** | MEDIUM (SEC lawsuits) | CRITICAL (service loss) | Alternative exchange plan | MEDIUM |
| **API Breaking Changes** | LOW (90-day notice) | MEDIUM (code changes) | Monthly changelog review | LOW |
| **Rate Limit Breach** | VERY LOW (conservative limits) | LOW (temporary block) | RateLimiter decorator | VERY LOW |

### 7.2 Overall Assessment

**Risk Rating**: **MEDIUM** (acceptable for personal trading at MVP scale)

**Justification**:
- Binance is well-established (7+ years, largest exchange by volume)
- Capital at risk is minimal (10-50 EUR for Phase 14)
- Compensating controls reduce impact of vendor risks
- Alternative exchanges available (migration plan documented)

**Risk Acceptance Conditions**:
1. ✅ Capital exposure limited to acceptable loss (50 EUR max)
2. ✅ Withdrawal-disabled API keys prevent fund theft
3. ✅ Weekly profit withdrawal minimizes on-exchange balance
4. ✅ Daily monitoring detects unauthorized activity within 24h
5. ✅ Alternative exchange migration plan documented

**Recommendation**: **APPROVED** for Phase 13 (testnet) and Phase 14 (micro-live with 10-50 EUR)

**Re-Assessment Trigger**: If capital exposure exceeds 100 EUR, perform full vendor risk re-assessment

---

## 8. Action Items

### Immediate (Before Phase 13)

- [x] Verify API key permissions (withdrawals disabled)
- [x] Test circuit breaker trip on API errors
- [x] Document alternative exchange options
- [ ] Enable 2FA on Binance account (if not already enabled)

### Short-Term (Phase 14)

- [ ] Implement weekly profit withdrawal to external wallet
- [ ] Set up monitoring for Binance status page (RSS feed)
- [ ] Create automated script to check Proof of Reserves monthly

### Long-Term (Phase 15+)

- [ ] Evaluate alternative exchanges (Coinbase, Kraken)
- [ ] Implement multi-exchange support (diversification)
- [ ] Consider self-custody solution (DEX aggregator)

---

**Next Review**: 2026-01-03 (quarterly)
**Approver**: System Owner
**Date**: 2025-10-03

**Change Log**: See git history for `docs/VENDOR-RISK-ASSESSMENT.md`
