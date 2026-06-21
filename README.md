# DeepSeek Trading Bot — TR-GC-Crypto-9

Standalone Python automation script for Bot ID **25880**. Replaces Claude-dependent trading
with a cron-schedulable pipeline using **DeepSeek V4 Pro** for decisions,
**Signum MCP** for data, and **Signum REST** for order execution.

## Architecture

```
READ ──────► DECIDE ──────► WRITE ──────► VERIFY ──────► NOTIFY
Signum MCP    DeepSeek       Signum REST   Re-fetch       Telegram
              V4 Pro         (sequential)  HOLDINGS
```

1. **READ** — Fetch HOLDINGS + Crypto Trend Radar ("gc" detector) via Signum MCP
2. **DECIDE** — DeepSeek V4 Pro receives strategy rules + current data, returns structured JSON orders
3. **WRITE** — Orders sent one-at-a-time to Signum REST; sizing recomputed fresh before each order
4. **VERIFY** — Re-fetch HOLDINGS, compare expected vs actual, log mismatches
5. **NOTIFY** — Telegram summary: NAV before/after, orders sent/skipped, errors

## Quick Start

```bash
# Clone
git clone https://github.com/4mrm4/deepseek-signum-trading-bot.git
cd deepseek-signum-trading-bot

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — fill in your API keys (see below)

# Dry-run (default — logs trades, sends nothing)
python deepseek_trading_bot.py

# Live (sends real orders to the exchange)
python deepseek_trading_bot.py --live
```

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DEEPSEEK_API_KEY` | Yes | DeepSeek V4 Pro API key |
| `SIGNUM_MCP_TOKEN` | Yes | Signum MCP server Bearer token |
| `TELEGRAM_BOT_TOKEN` | No | Telegram Bot API token for notifications |
| `TELEGRAM_CHAT_ID` | No | Telegram chat ID to send notifications to |

Never commit `.env` — it's in `.gitignore`.

## Strategy (TR-GC-Crypto-9)

The bot follows the TR-GC-Crypto-9 ruleset encoded as DeepSeek's system prompt:

### Long Exits
Close 100% of any held asset (excluding stablecoins/fiat) when:
- The latest closed candle's **close is below** the upper GC band, or
- The asset is **no longer present** in Trend Radar results

Proceeds go to USDC, USDT, or USD (priority order).

### Long Entries
Enter a long position when:
- The latest closed candle's **close crossed above** the upper GC band
  (this candle close > GC upper AND previous candle close ≤ GC upper)
- Asset is **not already held** and was not exited earlier in the same run

### Entry Sizing
| Breakout recency | Size |
|---|---|
| `breakoutDate` ≤ 25 days ago | 8% of NAV |
| Older breakout or no breakout | 2% of NAV |

### Safety Guardrails (enforced in Python, never trusted to the model)

| Guard | Rule |
|---|---|
| Min order value | ≥ $10 and ≥ 1% of NAV for entries; ≥ $10 for exits |
| Ticker collision | Skip if exchange price diverges >50% from Trend Radar reference |
| Schema validation | Abort run if DeepSeek returns invalid JSON |
| Dry-run default | `--live` flag required to send real orders |
| Idempotency | Unique timestamps prevent duplicate signals on re-run |

## Scheduling

The script runs as a **single one-shot execution** — no internal loop.
Trigger it with:

- **cron** (Linux/macOS): `0 6 * * * cd /path/to/bot && python deepseek_trading_bot.py --live`
- **Task Scheduler** (Windows)
- **GitHub Actions** (schedule workflow)

Recommended: schedule ~30 minutes after the daily Trend Radar update.

## Files

| File | Purpose |
|---|---|
| `deepseek_trading_bot.py` | Main script (~1250 lines) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `.gitignore` | Prevents committing secrets |

## Dependencies

- `openai` ≥ 1.0 — DeepSeek API (OpenAI-compatible)
- `httpx` ≥ 0.25 — Signum REST + Telegram HTTP
- `pydantic` ≥ 2.0 — Schema validation
- `python-dotenv` ≥ 1.0 — .env loading
- `mcp` ≥ 1.0 — Signum MCP client

## License

MIT
