# Binance API Best Practices (2024)

**Source:** Binance Developer Documentation, 2024 updates
**Last Updated:** 2025-10-02

---

## Rate Limiting Structure

### IP Weight Limits
- **Maximum:** 1200 weight per minute = **20 per second**
- **Monitoring Header:** `X-MBX-USED-WEIGHT-(intervalNum)(intervalLetter)`
- **Example:** `X-MBX-USED-WEIGHT-1M: 850` means 850/1200 used in last minute

### Order Rate Limits
- **Maximum:** 50 orders per 10 seconds = **5 per second**
- **Account-based:** Applies to all order operations (create, cancel, modify)

### Current Limits Check
```python
import requests

response = requests.get('https://api.binance.com/api/v3/exchangeInfo')
rate_limits = response.json()['rateLimits']

for limit in rate_limits:
    print(f"{limit['rateLimitType']}: {limit['limit']} per {limit['intervalNum']}{limit['interval']}")
```

---

## Backoff Strategy (Critical!)

### HTTP 429 Response
```json
{
  "code": -1003,
  "msg": "Too many requests; current limit is 1200 requests per minute.",
  "retryAfter": 60000
}
```

### Exponential Backoff Implementation
```python
import time
from binance.client import Client
from binance.exceptions import BinanceAPIException

class RateLimitedBinanceClient:
    """Binance client with automatic exponential backoff."""

    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.base_delay = 1.0
        self.max_delay = 60.0

    def _execute_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff on rate limit."""
        delay = self.base_delay

        while True:
            try:
                return func(*args, **kwargs)

            except BinanceAPIException as e:
                if e.code == -1003:  # Rate limit error
                    retry_after = e.response.headers.get('Retry-After', delay)
                    sleep_time = min(float(retry_after) / 1000, self.max_delay)

                    print(f"Rate limited. Sleeping {sleep_time}s")
                    time.sleep(sleep_time)

                    # Exponential backoff
                    delay = min(delay * 2, self.max_delay)
                else:
                    raise

    def get_ticker(self, symbol):
        return self._execute_with_backoff(self.client.get_ticker, symbol=symbol)

    def create_order(self, **params):
        return self._execute_with_backoff(self.client.create_order, **params)
```

### Consequences of Violations
| Violation Count | Ban Duration |
|-----------------|--------------|
| First | 2 minutes |
| Second | 30 minutes |
| Third | 3 days |
| Repeated | Permanent IP ban |

**Critical:** Always implement exponential backoff. **Never** retry immediately after 429.

---

## Order Execution Best Practices

### 1. Price and Quantity Formatting

**Problem:** Invalid price/quantity causes `FILTER_FAILURE`

**Solution:** Round to exchange filters

```python
from decimal import Decimal

def format_order_params(symbol_info, price, quantity):
    """Format price and quantity according to exchange filters."""

    # Extract filters
    price_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
    lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')

    tick_size = Decimal(price_filter['tickSize'])
    step_size = Decimal(lot_size_filter['stepSize'])

    # Round price to tick_size
    price_decimal = Decimal(str(price))
    price_rounded = (price_decimal / tick_size).quantize(Decimal('1')) * tick_size

    # Round quantity to step_size
    qty_decimal = Decimal(str(quantity))
    qty_rounded = (qty_decimal / step_size).quantize(Decimal('1')) * step_size

    return float(price_rounded), float(qty_rounded)

# Usage
symbol_info = client.get_symbol_info('BTCUSDT')
formatted_price, formatted_qty = format_order_params(symbol_info, 50000.123, 0.0234567)

# Now create order safely
order = client.create_order(
    symbol='BTCUSDT',
    side='BUY',
    type='LIMIT',
    price=formatted_price,
    quantity=formatted_qty,
    timeInForce='GTC'
)
```

### 2. Partial Fill Handling

Monitor `executedQty` to track order completion:

```python
def wait_for_fill(client, symbol, order_id, timeout=30):
    """Wait for order to fill, handling partial fills."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        order = client.get_order(symbol=symbol, orderId=order_id)

        if order['status'] == 'FILLED':
            return {
                'filled': True,
                'executed_qty': Decimal(order['executedQty']),
                'avg_price': Decimal(order['cummulativeQuoteQty']) / Decimal(order['executedQty'])
            }

        elif order['status'] in ['CANCELED', 'REJECTED', 'EXPIRED']:
            return {'filled': False, 'status': order['status']}

        elif order['status'] == 'PARTIALLY_FILLED':
            # Decision point: wait or cancel?
            executed_pct = Decimal(order['executedQty']) / Decimal(order['origQty'])
            if executed_pct >= Decimal('0.95'):  # 95% filled - good enough
                client.cancel_order(symbol=symbol, orderId=order_id)
                return {
                    'filled': True,
                    'executed_qty': Decimal(order['executedQty']),
                    'avg_price': Decimal(order['cummulativeQuoteQty']) / Decimal(order['executedQty']),
                    'partial': True
                }

        time.sleep(0.5)

    # Timeout - cancel order
    client.cancel_order(symbol=symbol, orderId=order_id)
    return {'filled': False, 'status': 'TIMEOUT'}
```

### 3. Unfilled Order Management

**Key insight:** Filled orders decrement from your limit
- If orders consistently fill via trades, you can place continuously
- Unfilled orders accumulate and hit the 50/10sec limit

**Best practice:** Cancel stale unfilled orders

```python
def cleanup_unfilled_orders(client, symbol, max_age_seconds=60):
    """Cancel orders that haven't filled within time limit."""
    open_orders = client.get_open_orders(symbol=symbol)
    current_time = time.time() * 1000  # milliseconds

    for order in open_orders:
        order_age = current_time - order['time']

        if order_age > max_age_seconds * 1000:
            try:
                client.cancel_order(symbol=symbol, orderId=order['orderId'])
                print(f"Cancelled stale order {order['orderId']}")
            except BinanceAPIException as e:
                if e.code == -2011:  # Order already filled
                    pass
                else:
                    raise
```

---

## WebSocket vs REST

### When to Use WebSocket
- ✅ Real-time price updates
- ✅ Order book streaming
- ✅ Trade execution updates
- ✅ Balance changes

### When to Use REST
- ✅ One-time data fetch (account info)
- ✅ Historical data
- ✅ Order placement (with WebSocket for updates)

### Hybrid Approach (Recommended)
```python
from binance import ThreadedWebsocketManager

class HybridBinanceClient:
    """Combine REST for commands, WebSocket for updates."""

    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
        self.wsm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret)
        self.wsm.start()

        self.latest_price = {}

    def start_price_stream(self, symbol):
        """Start WebSocket price stream (uses no weight!)."""

        def handle_socket_message(msg):
            if msg['e'] == 'trade':
                self.latest_price[symbol] = float(msg['p'])

        self.wsm.start_trade_socket(callback=handle_socket_message, symbol=symbol)

    def get_current_price(self, symbol):
        """Get latest price from WebSocket (instant, no API call)."""
        return self.latest_price.get(symbol)

    def place_order_rest(self, **params):
        """Use REST for order placement."""
        return self.client.create_order(**params)

    def start_user_stream(self):
        """Monitor order fills via WebSocket."""

        def handle_user_message(msg):
            if msg['e'] == 'executionReport':
                print(f"Order update: {msg['X']} - {msg['q']} @ {msg['p']}")

        self.wsm.start_user_socket(callback=handle_user_message)

# Usage
hybrid_client = HybridBinanceClient(api_key, api_secret)
hybrid_client.start_price_stream('BTCUSDT')
hybrid_client.start_user_stream()

# Get price without API weight
current_price = hybrid_client.get_current_price('BTCUSDT')

# Place order (uses weight)
order = hybrid_client.place_order_rest(
    symbol='BTCUSDT',
    side='BUY',
    type='MARKET',
    quoteOrderQty=100
)
```

---

## Conversion Rate & Weight Metrics

### Definitions (Anti-Abuse)

**Conversion Rate:**
```
conversion_rate = number_of_trades / (orders_created + orders_cancelled)
```

**Weight:**
```
weight = total_traded_quantity / (orders_created + orders_cancelled)
```

### Why This Matters
- Low conversion rate = many unfilled orders (suspicious)
- Low weight = many small orders relative to volume (quote stuffing)
- Binance may throttle or ban accounts with poor metrics

### Best Practices
- Aim for conversion rate > 0.3 (30% of orders result in trades)
- Use LIMIT orders with realistic prices (higher fill probability)
- Avoid excessive order cancellations
- Batch smaller trades if possible

---

## THUNES Integration Checklist

### Current Implementation (Phase A - Complete)
- [x] Basic rate limiting (TokenBucket)
- [x] IP weight tracking (1200/min)
- [x] Order rate tracking (50/10sec)
- [x] Circuit breaker for API failures

### Phase B Enhancements (Recommended)
- [ ] Exponential backoff on 429 errors
- [ ] WebSocket price streaming (reduce weight usage)
- [ ] Automatic price/quantity formatting to filters
- [ ] Partial fill handling logic
- [ ] Unfilled order cleanup (cancel stale orders > 60s)
- [ ] User stream for order updates
- [ ] Conversion rate monitoring

### Code Locations
- Rate limiting: `src/utils/rate_limiter.py`
- Circuit breaker: `src/utils/circuit_breaker.py`
- API client wrapper: `src/live/paper_trader.py`

---

## References

1. **Binance API Documentation** - https://developers.binance.com/docs
   - Rate Limits: `/docs/binance-spot-api-docs/rest-api/limits`
   - Exchange Info: `/api/v3/exchangeInfo`
   - WebSocket Streams: `/docs/binance-spot-api-docs/web-socket-streams`

2. **python-binance Library** - https://github.com/sammchardy/python-binance
   - Current THUNES dependency
   - Version: 1.0.19

3. **Binance Academy** - "How to Avoid Getting Banned by Rate Limits"
   - Best practices guide (2024)

---

**Last Updated:** 2025-10-02
**Next Review:** Quarterly or after Binance API changes
