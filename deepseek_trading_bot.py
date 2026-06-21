#!/usr/bin/env python3
"""
DeepSeek Trading Bot — TR-GC-Crypto-9
======================================
Standalone Python automation script for Bot ID 25880.

Architecture:
  1. READ  — Fetch HOLDINGS + Crypto Trend Radar ("gc") via Signum MCP
  2. DECIDE — Send strategy rules + data to DeepSeek V4 Pro; get JSON orders
  3. WRITE — POST orders one-at-a-time to Signum REST (sequential, size-recomputed)
  4. VERIFY — Re-fetch HOLDINGS, compare expected vs actual, alert on mismatch
  5. NOTIFY — Telegram summary (NAV before/after, orders sent/skipped, errors)

Safety:
  - --dry-run (default) logs intended actions; --live sends real orders
  - All guardrails enforced in Python, NOT trusted to DeepSeek
  - Schema validation via Pydantic; abort on invalid model output
  - Ticker collision guard (price divergence > 50 % → skip)
  - Minimum order value checks ($10 and 1 % NAV)
  - Idempotent timestamp usage
  - Retry + backoff on all network calls

Usage:
  python deepseek_trading_bot.py          # dry-run
  python deepseek_trading_bot.py --live    # send real orders
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator

# ═══════════════════════════════════════════════════════════════════════════
# 0. Environment
# ═══════════════════════════════════════════════════════════════════════════

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# 1. Configuration
# ═══════════════════════════════════════════════════════════════════════════

CONFIG: dict[str, Any] = {
    # --- Thresholds (from TR-GC-Crypto-9) ---
    "MIN_ORDER_USD": 10.0,
    "MIN_ORDER_NAV_PCT": 1.0,         # 1 % of NAV minimum entry value
    "MIN_ORDER_NAV_PCT_DECIMAL": 0.01,
    "MAX_TREND_RADAR_ROWS": 50,       # sort by market rank, take first N
    "TREND_RADAR_MIN_ROWS": 50,       # if < 50 rows, re-fetch up to 3 times
    "BREAKOUT_RECENT_DAYS": 25,       # breakout within this → larger size
    "BREAKOUT_RECENT_SIZE_PCT": 8.0,  # 8 % of NAV for recent breakouts
    "DEFAULT_ENTRY_SIZE_PCT": 2.0,    # 2 % of NAV for older/no breakout
    "TICKER_PRICE_DIVERGENCE_MAX": 0.5,  # 50 % divergence → skip
    "MCP_MAX_RETRIES": 3,             # retries for trend-radar fetch
    "NETWORK_RETRIES": 3,             # general retry count
    "NETWORK_BACKOFF_BASE": 2.0,      # seconds, exponential
    "NETWORK_TIMEOUT": 60,            # seconds

    # --- Endpoints ---
    "MCP_SERVER_URL": "https://api.signum.money/mcp",
    "OAUTH_TOKEN_URL": "https://api.signum.money/oauth/token",
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
    "DEEPSEEK_MODEL": "deepseek-v4-pro",
    "TELEGRAM_API_BASE": "https://api.telegram.org",
    # Signum REST webhook for orders (configurable)
    "SIGNUM_ORDER_ENDPOINT": "https://api.signum.money/v1/bots/{bot_id}/orders",

    # --- MCP tool names (adjust if Signum uses different names) ---
    "MCP_TOOL_HOLDINGS": "get-holdings",
    "MCP_TOOL_TREND_RADAR": "get-crypto-trend-radar",
    "MCP_TOOL_GET_PAIR_PRICE": "get-pair-price",
    "MCP_TOOL_EDIT_BOT": "edit-bot",
    "MCP_TOOL_LIST_PAIRS": "list-trading-pairs",

    # --- Stablecoins (fallback list; prefer asset-type field if present) ---
    "STABLECOINS": [
        "USDC", "USDT", "DAI", "BUSD", "TUSD", "USDP", "FDUSD", "PYUSD",
    ],
    # Assets treated as fiat/quote (never traded as base)
    "FIAT": ["USD", "EUR", "GBP", "JPY", "KRW"],

    # Quote-coin priority for exit proceeds
    "QUOTE_PRIORITY": ["USDC", "USDT", "USD"],

    # Bot identity
    "BOT_ID": 25880,
}


def _require_secret(name: str) -> str:
    """Fetch a required secret; abort with a clear message if missing."""
    value = os.getenv(name)
    if not value:
        sys.exit(f"FATAL: environment variable {name} is not set. Aborting.")
    return value


def _update_env_refresh_token(new_token: str) -> None:
    """Persist a rotated refresh token back to the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        log.warning("Cannot update refresh token: .env file not found at %s", env_path)
        return
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    found = False
    with open(env_path, "w", encoding="utf-8") as f:
        for line in lines:
            if line.startswith("SIGNUM_REFRESH_TOKEN="):
                f.write(f"SIGNUM_REFRESH_TOKEN={new_token}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"\nSIGNUM_REFRESH_TOKEN={new_token}\n")
    log.info("Refresh token updated in .env")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Logging
# ═══════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("deepseek_bot")

# ═══════════════════════════════════════════════════════════════════════════
# 3. Pydantic Schemas
# ═══════════════════════════════════════════════════════════════════════════

VALID_ACTIONS = frozenset({"buy", "sell"})


class Order(BaseModel):
    """A single trading order produced by DeepSeek."""

    asset: str
    ticker: str = ""
    action: str
    order_size: float = Field(ge=0.0, alias="order_size", description="Order size as % of quote balance")
    position_size: float = Field(alias="position_size", description="Final position size (> 0 = long, 0 = closed)")
    reasoning: str = ""

    @field_validator("action")
    @classmethod
    def _validate_action(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in VALID_ACTIONS:
            raise ValueError(f"action must be 'buy' or 'sell', got '{v}'")
        return v_lower

    @field_validator("order_size")
    @classmethod
    def _validate_order_size(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"order_size must be >= 0, got {v}")
        return v


class OrdersResponse(BaseModel):
    """Wrapper for the DeepSeek JSON response."""

    orders: list[Order]

    @field_validator("orders")
    @classmethod
    def _validate_orders_non_empty(cls, v: list[Order]) -> list[Order]:
        # Empty list is valid (no signals)
        return v


# Schema enforced on DeepSeek output via response_format json_object.
# We additionally validate with Pydantic post-receive.

# ═══════════════════════════════════════════════════════════════════════════
# 4. Strategy System Prompt (TR-GC-Crypto-9)
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = textwrap.dedent("""\
    You are managing a crypto portfolio via these rules (TR-GC-Crypto-9) for Bot ID = 25880.

    ## 1. Context
    You will receive:
    - **HOLDINGS**: current positions (asset, quantity, USD value).
    - **Trend Radar**: daily Crypto Trend Radar for the "gc" detector with indicators.
      Each row has: asset, marketRank, indicators.data[] (candles with ohlc.c = close,
      gc.upper = upper GC band), breakoutDate, cmcRefPriceUsd (optional).

    ## 2. Long Exits
    Iterate through all HOLDINGS (excluding fiat and stablecoins).
    EXIT a LONG (close 100 %) when:
    - The asset's latest CLOSED candle CLOSE is BELOW the upper GC band, OR
    - The asset is no longer present in the Trend Radar results (drifted out).
    Take proceeds in USDC, USDT, or USD priority.

    ## 3. Long Entries
    Iterate through Trend Radar assets sorted by marketRank ascending (first 50 rows).
    ENTER a LONG when:
    - The asset's latest closed candle CLOSE crossed ABOVE the upper GC band.
      This means: this candle's close > gc.upper AND previous candle's close ≤ gc.upper.
    - NEVER enter an asset you already long-exited earlier in this same run.
    - Skip any asset already held (one position per coin) unless it's dust.
    - If indicator data needed to evaluate crossover is missing, skip that asset.

    Sizing:
    - breakoutDate within last 25 calendar days → 8 % of NAV
    - Otherwise (older or no breakout) → 2 % of NAV
    A breakout is NOT required to enter — it only sets the entry size.

    ## 4. Output Format
    Return a single JSON object with key "orders" set to a JSON array.
    Each order object must have these exact keys:
      - "asset": string (e.g. "BTC")
      - "ticker": string (e.g. "BTC/USDT") — the trading pair
      - "action": "buy" or "sell"
      - "order_size": number (percentage of quote balance, see sizing rules)
      - "position_size": number (final position state: >0 = long, 0 = exit)
      - "reasoning": string (short rationale for audit log, ≤ 200 chars)

    Example:
    {
      "orders": [
        {
          "asset": "BTC",
          "ticker": "BTC/USDT",
          "action": "buy",
          "order_size": 8.0,
          "position_size": 8.0,
          "reasoning": "BTC crossed above GC upper band, recent breakout 2026-06-20"
        }
      ]
    }

    If no trades are warranted, return: {"orders": []}

    ## 5. Constraints
    - Never output EXIT and ENTER for the same asset in the same run.
    - Do not include dust positions (value < $10) in orders.
    - One position per coin maximum.
    - Do NOT worry about execution details (bot editing, pair availability checking,
      quote conversion, price divergence checks) — those are handled by the Python
      automation layer. Focus purely on the trading decision logic above.
    """)

# ═══════════════════════════════════════════════════════════════════════════
# 5. Network utilities (retry + backoff)
# ═══════════════════════════════════════════════════════════════════════════

async def _retry_with_backoff(
    name: str,
    fn,
    *args,
    max_retries: int = CONFIG["NETWORK_RETRIES"],
    base_delay: float = CONFIG["NETWORK_BACKOFF_BASE"],
    **kwargs,
) -> Any:
    """Call an async function with exponential-backoff retries."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            delay = base_delay ** attempt
            log.warning(
                "%s attempt %d/%d failed: %s — retrying in %.1fs",
                name, attempt, max_retries, exc, delay,
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
    log.error("%s failed after %d attempts.", name, max_retries)
    raise last_exc  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════
# 6. Signum MCP Client
# ═══════════════════════════════════════════════════════════════════════════

class SignumMCPClient:
    """
    Async client for Signum's MCP server.

    Auth: OAuth 2.0 refresh_token grant.
    On connect(), exchanges the stored refresh token for a fresh access token.
    If the access token expires mid-session, auto-refreshes and retries once.
    """

    def __init__(self, server_url: str, client_id: str, refresh_token: str):
        self.server_url = server_url
        self.client_id = client_id
        self.refresh_token = refresh_token
        self._access_token: Optional[str] = None
        self._session: Optional[Any] = None     # MCP ClientSession
        self._read: Optional[Any] = None
        self._write: Optional[Any] = None
        self._available_tools: dict[str, Any] = {}
        self._mcp_bot_edit_supported: Optional[bool] = None

    async def _get_access_token(self) -> str:
        """Exchange the refresh token for a fresh access token via OAuth."""
        log.info("Refreshing OAuth access token via %s…", CONFIG["OAUTH_TOKEN_URL"])
        async with httpx.AsyncClient(timeout=CONFIG["NETWORK_TIMEOUT"]) as client:
            resp = await _retry_with_backoff(
                "oauth_refresh",
                client.post,
                CONFIG["OAUTH_TOKEN_URL"],
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()
            access_token = data.get("access_token")
            if not access_token:
                raise RuntimeError(f"OAuth token response missing access_token: {list(data.keys())}")
            # If a new refresh token is issued, store it (rotation)
            new_refresh = data.get("refresh_token")
            if new_refresh and new_refresh != self.refresh_token:
                log.info("Refresh token rotated — updating stored token.")
                self.refresh_token = new_refresh
                _update_env_refresh_token(new_refresh)
            expires_in = data.get("expires_in")
            log.info(
                "Access token obtained%s.",
                f" (expires in {expires_in}s)" if expires_in else "",
            )
            return access_token

    async def connect(self) -> None:
        """
        Establish an MCP session.

        Obtains an OAuth access token, then connects via streamable HTTP
        with Bearer auth.
        """
        self._access_token = await self._get_access_token()

        try:
            # Lazy-import so the rest of the script can at least start without mcp installed
            from mcp import ClientSession                       # type: ignore[import-untyped]
            from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-untyped]

            headers = {"Authorization": f"Bearer {self._access_token}"}
            self._stream_ctx = streamablehttp_client(
                self.server_url,
                headers=headers,
            )
            read, write, _ = await self._stream_ctx.__aenter__()
            self._read = read
            self._write = write
            self._session = ClientSession(read, write)
            await self._session.initialize()
            # Discover available tools
            tools_result = await self._session.list_tools()
            for tool in (tools_result.tools if hasattr(tools_result, "tools") else tools_result):
                self._available_tools[tool.name] = tool
            log.info("MCP connected. Available tools: %s", sorted(self._available_tools.keys()))

            # Check whether bot-editing tools exist
            edit_tools = {CONFIG["MCP_TOOL_EDIT_BOT"], "set-bot-trading-pair", "update-bot-title"}
            self._mcp_bot_edit_supported = bool(edit_tools & self._available_tools.keys())

        except ImportError:
            log.error(
                "The 'mcp' Python package is not installed. "
                "Install it with: pip install mcp"
            )
            raise
        except Exception as exc:
            log.error(
                "Failed to connect to Signum MCP at %s. "
                "Underlying error: %s",
                self.server_url, exc,
            )
            raise

    async def close(self) -> None:
        """Tear down the MCP session."""
        if self._stream_ctx:
            try:
                await self._stream_ctx.__aexit__(None, None, None)
            except Exception:
                pass
        self._session = None
        self._read = None
        self._write = None

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool by name. Returns parsed JSON content."""
        if not self._session:
            raise RuntimeError("MCP session not connected — call connect() first.")
        if tool_name not in self._available_tools:
            raise ValueError(
                f"MCP tool '{tool_name}' not found. Available: {sorted(self._available_tools.keys())}"
            )
        result = await self._session.call_tool(tool_name, arguments=arguments)
        # MCP tool results are Content objects; extract text
        content_parts = result.content if hasattr(result, "content") else result
        texts: list[str] = []
        for part in content_parts:
            if hasattr(part, "text"):
                texts.append(part.text)
        raw = "".join(texts)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Some MCP tools return non-JSON; return raw string
            return raw

    async def fetch_holdings(self) -> dict[str, Any]:
        """Fetch current HOLDINGS / positions for Bot ID 25880."""
        log.info("Fetching HOLDINGS via MCP tool '%s'…", CONFIG["MCP_TOOL_HOLDINGS"])
        data = await _retry_with_backoff(
            "fetch_holdings",
            self._call_tool,
            CONFIG["MCP_TOOL_HOLDINGS"],
            {"bot_id": CONFIG["BOT_ID"]},
        )
        # Normalise: the MCP may return {holdings: [...]} or a raw list
        if isinstance(data, list):
            return {"holdings": data}
        return data

    async def fetch_trend_radar(self) -> list[dict[str, Any]]:
        """
        Fetch Crypto Trend Radar for the "gc" detector with includeIndicators=true.

        Retries up to MCP_MAX_RETRIES if fewer than TREND_RADAR_MIN_ROWS rows returned.
        """
        for attempt in range(1, CONFIG["MCP_MAX_RETRIES"] + 1):
            log.info(
                "Fetching Trend Radar (gc) via MCP tool '%s', attempt %d…",
                CONFIG["MCP_TOOL_TREND_RADAR"], attempt,
            )
            data = await _retry_with_backoff(
                "fetch_trend_radar",
                self._call_tool,
                CONFIG["MCP_TOOL_TREND_RADAR"],
                {
                    "detector": "gc",
                    "includeIndicators": True,
                },
            )
            rows: list[dict[str, Any]] = data if isinstance(data, list) else data.get("assets", data.get("data", []))
            if len(rows) >= CONFIG["TREND_RADAR_MIN_ROWS"]:
                log.info("Trend Radar: %d rows received.", len(rows))
                return rows
            log.warning(
                "Trend Radar returned %d rows (< %d minimum). Attempt %d/%d.",
                len(rows), CONFIG["TREND_RADAR_MIN_ROWS"], attempt, CONFIG["MCP_MAX_RETRIES"],
            )
        raise RuntimeError(
            f"Trend Radar fetch failed: got < {CONFIG['TREND_RADAR_MIN_ROWS']} rows "
            f"after {CONFIG['MCP_MAX_RETRIES']} attempts."
        )

    async def fetch_available_pairs(self) -> list[dict[str, Any]]:
        """Fetch available trading pairs for the bot."""
        tool = CONFIG["MCP_TOOL_LIST_PAIRS"]
        if tool not in self._available_tools:
            log.warning("MCP tool '%s' not available — skipping pair listing.", tool)
            return []
        data = await _retry_with_backoff(
            "fetch_pairs",
            self._call_tool,
            tool,
            {"bot_id": CONFIG["BOT_ID"]},
        )
        return data if isinstance(data, list) else data.get("pairs", data.get("data", []))

    async def fetch_pair_price(self, pair: str) -> Optional[float]:
        """Fetch current USD price for a trading pair. Returns None on failure."""
        tool = CONFIG["MCP_TOOL_GET_PAIR_PRICE"]
        if tool not in self._available_tools:
            log.warning("MCP tool '%s' not available — cannot verify pair price.", tool)
            return None
        try:
            data = await _retry_with_backoff(
                "fetch_pair_price",
                self._call_tool,
                tool,
                {"pair": pair},
            )
            # Try common response shapes
            if isinstance(data, (int, float)):
                return float(data)
            if isinstance(data, dict):
                return float(data.get("priceUsd", data.get("price", data.get("last", 0))))
        except Exception as exc:
            log.warning("Failed to fetch price for %s: %s", pair, exc)
        return None

    async def edit_bot_field(self, field: str, value: Any) -> bool:
        """
        Attempt to edit a bot config field. Returns True on success, False if unsupported.

        If the MCP does not expose edit-bot tools, logs a warning and returns False.
        """
        if not self._mcp_bot_edit_supported:
            log.warning("Bot editing via MCP is not supported — skipping field '%s'.", field)
            return False
        try:
            await _retry_with_backoff(
                f"edit_bot_{field}",
                self._call_tool,
                CONFIG["MCP_TOOL_EDIT_BOT"],
                {"bot_id": CONFIG["BOT_ID"], field: value},
            )
            log.info("Bot field '%s' updated successfully.", field)
            return True
        except Exception as exc:
            log.warning("Failed to edit bot field '%s': %s", field, exc)
            return False

    async def set_trading_pair(self, pair: str) -> bool:
        """Set the bot's active trading pair. Returns True on success."""
        if "set-bot-trading-pair" in self._available_tools:
            try:
                await _retry_with_backoff(
                    "set_trading_pair",
                    self._call_tool,
                    "set-bot-trading-pair",
                    {"bot_id": CONFIG["BOT_ID"], "pair": pair},
                )
                log.info("Trading pair set to '%s'.", pair)
                return True
            except Exception as exc:
                log.warning("Failed to set trading pair '%s': %s", pair, exc)
                return False
        return await self.edit_bot_field("trading_pair", pair)

    async def update_bot_title_suffix(self, suffix: str = "(TR-GC-Crypto-9)") -> bool:
        """Ensure the bot title ends with the strategy suffix."""
        if "update-bot-title" in self._available_tools:
            try:
                await _retry_with_backoff(
                    "update_bot_title",
                    self._call_tool,
                    "update-bot-title",
                    {"bot_id": CONFIG["BOT_ID"], "suffix": suffix},
                )
                return True
            except Exception as exc:
                log.warning("Failed to update bot title suffix: %s", exc)
                return False
        return await self.edit_bot_field("title_suffix", suffix)

    @property
    def bot_edit_supported(self) -> bool:
        return bool(self._mcp_bot_edit_supported)


# ═══════════════════════════════════════════════════════════════════════════
# 7. DeepSeek V4 Pro Client
# ═══════════════════════════════════════════════════════════════════════════

class DeepSeekClient:
    """Async client for DeepSeek V4 Pro (OpenAI-compatible API)."""

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=CONFIG["DEEPSEEK_BASE_URL"],
            timeout=CONFIG["NETWORK_TIMEOUT"],
        )

    async def get_orders(self, holdings: dict, trend_radar: list) -> OrdersResponse:
        """
        Send holdings + trend radar data, receive structured JSON orders.

        Uses response_format json_object to enforce structured output.
        """
        user_message = json.dumps({
            "holdings": holdings,
            "trend_radar": trend_radar[: CONFIG["MAX_TREND_RADAR_ROWS"]],
        }, indent=2, default=str)

        log.info("Calling DeepSeek V4 Pro for trading decisions…")
        try:
            response = await _retry_with_backoff(
                "deepseek_chat",
                self.client.chat.completions.create,
                model=CONFIG["DEEPSEEK_MODEL"],
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,  # deterministic for trading
                max_tokens=4096,
            )
        except Exception as exc:
            log.error("DeepSeek API call failed: %s", exc)
            raise

        raw_text = response.choices[0].message.content
        if not raw_text:
            raise RuntimeError("DeepSeek returned empty response content.")

        log.info("DeepSeek raw response: %s", raw_text[:500])

        # Parse + validate
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            log.error("DeepSeek returned invalid JSON: %s", exc)
            raise

        try:
            orders_resp = OrdersResponse.model_validate(parsed)
        except ValidationError as exc:
            log.error(
                "DeepSeek output failed Pydantic validation — aborting run.\n%s",
                exc,
            )
            raise

        log.info("DeepSeek returned %d order(s).", len(orders_resp.orders))
        return orders_resp


# ═══════════════════════════════════════════════════════════════════════════
# 8. Data helpers
# ═══════════════════════════════════════════════════════════════════════════

def _is_stablecoin(asset: str, holdings_data: dict | None = None) -> bool:
    """
    Check whether an asset ticker is a stablecoin.

    Prefers an asset-type/category field from holdings data if present;
    falls back to the hardcoded STABLECOINS list.
    """
    # Try HOLDINGS metadata first
    if holdings_data:
        for item in _iter_holdings(holdings_data):
            if _norm_asset(item.get("asset", item.get("ticker", ""))) == _norm_asset(asset):
                atype = item.get("type", item.get("assetType", item.get("category", "")))
                if atype and atype.lower() in ("stablecoin", "stable", "fiat"):
                    return True
                elif atype:
                    return False  # explicitly typed as something else
    # Fallback
    return _norm_asset(asset) in {a.upper() for a in CONFIG["STABLECOINS"]}


def _is_fiat(asset: str) -> bool:
    return _norm_asset(asset) in {a.upper() for a in CONFIG["FIAT"]}


def _norm_asset(name: str) -> str:
    return (name or "").strip().upper()


def _iter_holdings(holdings_data: dict) -> list[dict[str, Any]]:
    """Extract holdings list from various response shapes."""
    if isinstance(holdings_data, list):
        return holdings_data
    return holdings_data.get("holdings", holdings_data.get("positions", holdings_data.get("data", [])))


def _get_quote_balance(holdings_data: dict) -> dict[str, float]:
    """
    Extract available quote-coin balances from HOLDINGS.

    Returns {asset_upper: usd_value}.
    """
    balances: dict[str, float] = {}
    for item in _iter_holdings(holdings_data):
        asset = _norm_asset(item.get("asset", item.get("ticker", "")))
        if not asset:
            continue
        usd_val = float(item.get("valueUsd", item.get("usdValue", item.get("value", 0))) or 0)
        balances[asset] = usd_val
    return balances


def _compute_nav(holdings_data: dict) -> float:
    """Compute total NAV in USD from HOLDINGS."""
    total = 0.0
    for item in _iter_holdings(holdings_data):
        total += float(item.get("valueUsd", item.get("usdValue", item.get("value", 0))) or 0)
    return total


def _find_trend_radar_row(asset: str, radar: list) -> Optional[dict]:
    """Find a Trend Radar row for the given asset (case-insensitive)."""
    needle = _norm_asset(asset)
    for row in radar:
        if _norm_asset(row.get("asset", row.get("ticker", row.get("symbol", "")))) == needle:
            return row
    return None


def _is_in_trend_radar(asset: str, radar: list) -> bool:
    return _find_trend_radar_row(asset, radar) is not None


def _latest_candle(row: dict) -> Optional[dict]:
    """Return the latest (newest) candle from indicators.data[]."""
    indicators = row.get("indicators", {})
    data = indicators.get("data", [])
    if not data:
        return None
    return data[-1]  # assume chronological, last = newest


def _prev_candle(row: dict) -> Optional[dict]:
    """Return the second-to-last candle from indicators.data[]."""
    indicators = row.get("indicators", {})
    data = indicators.get("data", [])
    if len(data) < 2:
        return None
    return data[-2]


def _candle_close(candle: dict) -> Optional[float]:
    """Extract ohlc.c (close) from a candle."""
    ohlc = candle.get("ohlc", candle)
    c = ohlc.get("c", ohlc.get("close"))
    return float(c) if c is not None else None


def _candle_gc_upper(candle: dict) -> Optional[float]:
    """Extract gc.upper from a candle."""
    gc = candle.get("gc", {})
    upper = gc.get("upper")
    return float(upper) if upper is not None else None


def _get_ref_price(row: dict) -> Optional[float]:
    """
    Get the USD reference price for ticker-collision guard.

    Priority: cmcRefPriceUsd → newest indicator close.
    """
    ref = row.get("cmcRefPriceUsd")
    if ref is not None:
        return float(ref)
    candle = _latest_candle(row)
    if candle:
        return _candle_close(candle)
    return None


def _breakout_within_days(row: dict, days: int = CONFIG["BREAKOUT_RECENT_DAYS"]) -> bool:
    """Check if breakoutDate is within the last N calendar days."""
    bd = row.get("breakoutDate")
    if not bd:
        return False
    try:
        if isinstance(bd, str):
            bd_date = datetime.fromisoformat(bd.replace("Z", "+00:00")).date()
        else:
            bd_date = datetime.fromtimestamp(float(bd), tz=timezone.utc).date()
    except (ValueError, TypeError):
        return False
    today = datetime.now(timezone.utc).date()
    return (today - bd_date).days <= days


# ═══════════════════════════════════════════════════════════════════════════
# 9. Guardrails
# ═══════════════════════════════════════════════════════════════════════════

def validate_min_order(
    order: Order,
    nav: float,
    quote_balance_usd: float,
) -> Optional[str]:
    """
    Check minimum order value guardrails. Returns an error string if the order
    should be skipped, or None if it passes.
    """
    if order.action == "buy":
        order_value_usd = (order.order_size / 100.0) * quote_balance_usd
        if order.position_size != 0:
            min_nav_value = nav * CONFIG["MIN_ORDER_NAV_PCT_DECIMAL"]
            if order_value_usd < CONFIG["MIN_ORDER_USD"]:
                return (
                    f"order value ${order_value_usd:.2f} < minimum ${CONFIG['MIN_ORDER_USD']:.2f}"
                )
            if order_value_usd < min_nav_value:
                return (
                    f"order value ${order_value_usd:.2f} < {CONFIG['MIN_ORDER_NAV_PCT']}% "
                    f"NAV (${min_nav_value:.2f})"
                )
    elif order.action == "sell":
        order_value_usd = (order.order_size / 100.0) * quote_balance_usd
        if order_value_usd < CONFIG["MIN_ORDER_USD"]:
            return f"exit value ${order_value_usd:.2f} < minimum ${CONFIG['MIN_ORDER_USD']:.2f} (dust)"

    return None  # passes


# ═══════════════════════════════════════════════════════════════════════════
# 10. Order Execution (Signum REST)
# ═══════════════════════════════════════════════════════════════════════════

class OrderExecutor:
    """Posts orders to the Signum REST webhook endpoint one-at-a-time, sequentially."""

    def __init__(self, bot_id: int, endpoint_template: str, dry_run: bool = True):
        self.bot_id = bot_id
        self.endpoint = endpoint_template.format(bot_id=bot_id)
        self.dry_run = dry_run
        self._quote_balances: dict[str, float] = {}  # tracked locally, debited per order

    def update_balances(self, balances: dict[str, float]) -> None:
        """Initialize / refresh the local quote-balance tracker."""
        self._quote_balances = {k: v for k, v in balances.items()}

    def _get_quote_balance(self, quote_asset: str) -> float:
        """Get currently available balance for a quote asset."""
        return self._quote_balances.get(_norm_asset(quote_asset), 0.0)

    def _debit_quote(self, quote_asset: str, amount_usd: float) -> None:
        """Deduct from local quote balance after an order is sent."""
        key = _norm_asset(quote_asset)
        current = self._quote_balances.get(key, 0.0)
        self._quote_balances[key] = max(0.0, current - amount_usd)

    def compute_order_pct(
        self,
        nav: float,
        size_pct_of_nav: float,
        quote_asset: str,
    ) -> float:
        """
        Recompute order_size as a fresh % of currently available quote balance.

        Formula (per strategy):
          target_usd = size_pct_of_nav % of NAV
          order_size_pct = (target_usd / current_quote_balance) * 100
          capped at 100 %
        """
        target_usd = nav * (size_pct_of_nav / 100.0)
        current_balance = self._get_quote_balance(quote_asset)
        if current_balance <= 0:
            log.warning(
                "Quote balance for %s is $%.2f — cannot size order. "
                "You may need to convert stablecoins first.",
                quote_asset, current_balance,
            )
            return 0.0
        pct = (target_usd / current_balance) * 100.0
        return min(pct, 100.0)

    async def send_order(self, order: Order, timestamp: str) -> bool:
        """
        POST a single order to Signum. Returns True on success.

        In dry-run mode, logs the order without POSTing.
        """
        payload = {
            "bot_id": self.bot_id,
            "ticker": order.ticker,
            "action": order.action,
            "order_size": order.order_size,
            "position_size": order.position_size,
            "timestamp": timestamp,
            "schema": "2",
        }

        if self.dry_run:
            log.info(
                "[DRY-RUN] Would POST: %s %s order_size=%.2f%% pos_size=%.2f | %s",
                order.action.upper(), order.ticker, order.order_size,
                order.position_size, order.reasoning,
            )
            return True

        log.info(
            "POST order: %s %s order_size=%.2f%% pos_size=%.2f",
            order.action.upper(), order.ticker, order.order_size, order.position_size,
        )
        try:
            async with httpx.AsyncClient(timeout=CONFIG["NETWORK_TIMEOUT"]) as client:
                resp = await _retry_with_backoff(
                    f"send_order_{order.ticker}",
                    client.post,
                    self.endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                log.info("Order accepted: %s %s — HTTP %d", order.action, order.ticker, resp.status_code)
                return True
        except Exception as exc:
            log.error("Order FAILED [%s %s]: %s", order.action, order.ticker, exc)
            return False


# ═══════════════════════════════════════════════════════════════════════════
# 11. Verification
# ═══════════════════════════════════════════════════════════════════════════

async def verify_holdings(
    mcp: SignumMCPClient,
    expected_holdings: set[str],  # set of assets we expect to hold after trades
    exited_assets: set[str],       # assets we exited
    entered_assets: set[str],      # assets we entered
) -> list[str]:
    """
    Re-fetch HOLDINGS and compare against expected end-state.

    Returns a list of mismatch descriptions (empty = all good).
    """
    mismatches: list[str] = []
    try:
        data = await mcp.fetch_holdings()
    except Exception as exc:
        return [f"cannot re-fetch HOLDINGS for verification: {exc}"]

    actual_assets: set[str] = set()
    for item in _iter_holdings(data):
        asset = _norm_asset(item.get("asset", item.get("ticker", "")))
        if asset and not _is_stablecoin(asset, data) and not _is_fiat(asset):
            usd_val = float(item.get("valueUsd", item.get("usdValue", item.get("value", 0))) or 0)
            if usd_val >= CONFIG["MIN_ORDER_USD"]:  # dust threshold
                actual_assets.add(asset)

    # Check exited assets are gone
    for asset in exited_assets:
        if asset in actual_assets:
            mismatches.append(f"ASSET STILL HELD after exit: {asset}")

    # Check entered assets are present
    for asset in entered_assets:
        if asset not in actual_assets:
            mismatches.append(f"ASSET MISSING after entry: {asset}")

    if mismatches:
        log.warning("Post-trade verification MISMATCHES:\n  %s", "\n  ".join(mismatches))
    else:
        log.info("Post-trade verification: all holdings match expected end-state.")

    return mismatches


# ═══════════════════════════════════════════════════════════════════════════
# 12. Telegram Notification
# ═══════════════════════════════════════════════════════════════════════════

async def send_telegram(
    bot_token: str,
    chat_id: str,
    message: str,
) -> bool:
    """
    Send a Telegram message via Bot API. Returns True on success.

    Failure is logged but never crashes the run.
    """
    url = f"{CONFIG['TELEGRAM_API_BASE']}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        async with httpx.AsyncClient(timeout=CONFIG["NETWORK_TIMEOUT"]) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            log.info("Telegram notification sent.")
            return True
    except Exception as exc:
        log.error("Failed to send Telegram notification: %s", exc)
        return False


def _build_telegram_summary(
    nav_before: float,
    nav_after: Optional[float],
    orders_sent: list[dict],
    orders_skipped: list[dict],
    errors: list[str],
    dry_run: bool,
) -> str:
    """Build a human-readable Telegram summary message."""
    mode = "DRY-RUN" if dry_run else "LIVE"
    lines = [
        f"*DeepSeek Trading Bot — TR-GC-Crypto-9* ({mode})",
        f"*Time:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]
    lines.append(f"*NAV before:* ${nav_before:,.2f}")
    if nav_after is not None:
        lines.append(f"*NAV after:*  ${nav_after:,.2f}")
    lines.append("")

    if orders_sent:
        lines.append(f"*Orders Sent ({len(orders_sent)}):*")
        for o in orders_sent:
            lines.append(
                f"  • {o['action'].upper()} {o['ticker']} "
                f"({o['size_pct']:.1f}% → pos {o['pos_size']:.1f}) — {o['reason']}"
            )
    else:
        lines.append("*Orders Sent:* (none)")

    lines.append("")

    if orders_skipped:
        lines.append(f"*Orders Skipped ({len(orders_skipped)}):*")
        for s in orders_skipped:
            lines.append(f"  • {s['asset']} — {s['reason']}")
    else:
        lines.append("*Orders Skipped:* (none)")

    if errors:
        lines.append("")
        lines.append(f"*Errors ({len(errors)}):*")
        for e in errors:
            lines.append(f"  ❌ {e}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# 13. Main Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

async def run(dry_run: bool = True) -> None:
    """Execute one full run of the trading bot."""
    # --- Collect errors/warnings for final report ---
    errors: list[str] = []
    orders_sent: list[dict] = []
    orders_skipped: list[dict] = []

    # --- Validate secrets ---
    deepseek_key = _require_secret("DEEPSEEK_API_KEY")
    mcp_client_id = _require_secret("SIGNUM_CLIENT_ID")
    mcp_refresh_token = _require_secret("SIGNUM_REFRESH_TOKEN")

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Connect MCP ---
    log.info("=== DeepSeek Trading Bot (TR-GC-Crypto-9) starting === mode=%s", "dry-run" if dry_run else "LIVE")
    mcp = SignumMCPClient(CONFIG["MCP_SERVER_URL"], mcp_client_id, mcp_refresh_token)
    try:
        await mcp.connect()
    except Exception as exc:
        errors.append(f"MCP connection failed: {exc}")
        # Try to notify Telegram even on fatal errors
        await _maybe_notify(telegram_token, telegram_chat_id, 0.0, None, [], [], errors, dry_run)
        sys.exit(1)

    try:
        # --- Step 1: Fetch HOLDINGS ---
        holdings_data = await mcp.fetch_holdings()
        nav_before = _compute_nav(holdings_data)
        log.info("NAV before: $%.2f", nav_before)

        # --- Step 2: Fetch Trend Radar ---
        trend_radar = await mcp.fetch_trend_radar()

        # --- Step 3: Fetch available trading pairs (best-effort) ---
        available_pairs = await mcp.fetch_available_pairs()
        pair_set: set[str] = set()
        for p in available_pairs:
            pair_set.add(p.get("symbol", p.get("pair", p.get("ticker", ""))))

        # --- Step 4: Get DeepSeek decisions ---
        deepseek = DeepSeekClient(deepseek_key)
        try:
            orders_resp = await deepseek.get_orders(holdings_data, trend_radar)
        except Exception as exc:
            errors.append(f"DeepSeek decision failed: {exc}")
            await _maybe_notify(telegram_token, telegram_chat_id, nav_before, None, [], [], errors, dry_run)
            return

        # --- Step 5: Set up order executor ---
        executor = OrderExecutor(CONFIG["BOT_ID"], CONFIG["SIGNUM_ORDER_ENDPOINT"], dry_run=dry_run)
        initial_balances = _get_quote_balance(holdings_data)
        executor.update_balances(initial_balances)

        # Track what we do this run
        exited_assets: set[str] = set()
        entered_assets: set[str] = set()
        held_assets_now: set[str] = set()
        for item in _iter_holdings(holdings_data):
            asset = _norm_asset(item.get("asset", item.get("ticker", "")))
            if asset and not _is_stablecoin(asset, holdings_data) and not _is_fiat(asset):
                val = float(item.get("valueUsd", item.get("usdValue", item.get("value", 0))) or 0)
                if val > 0:
                    held_assets_now.add(asset)

        # --- Step 6: Process each order sequentially ---
        # Rule: process exits BEFORE entries (per strategy)
        exit_orders = [o for o in orders_resp.orders if o.action == "sell"]
        entry_orders = [o for o in orders_resp.orders if o.action == "buy"]

        timestamp_base = datetime.now(timezone.utc)

        for order in exit_orders + entry_orders:
            asset_key = _norm_asset(order.asset)

            # ---- 6a. Skip if asset already processed this run ----
            if order.action == "sell" and asset_key in exited_assets:
                orders_skipped.append({"asset": order.asset, "reason": "already exited this run"})
                continue
            if order.action == "buy" and asset_key in exited_assets:
                orders_skipped.append({
                    "asset": order.asset,
                    "reason": "was long-exited earlier this run — cannot re-enter",
                })
                continue
            if order.action == "buy" and asset_key in held_assets_now:
                orders_skipped.append({"asset": order.asset, "reason": "already held (one position per coin)"})
                continue

            # ---- 6b. Ticker collision guard ----
            radar_row = _find_trend_radar_row(order.asset, trend_radar)
            if order.ticker:
                ref_price = _get_ref_price(radar_row) if radar_row else None
                if ref_price is not None:
                    pair_price = await mcp.fetch_pair_price(order.ticker)
                    if pair_price is not None:
                        divergence = abs(pair_price - ref_price) / ref_price
                        if divergence > CONFIG["TICKER_PRICE_DIVERGENCE_MAX"]:
                            reason = (
                                f"ticker collision: {order.ticker} price ${pair_price:.4f} "
                                f"vs ref ${ref_price:.4f} ({divergence:.1%} divergence)"
                            )
                            orders_skipped.append({"asset": order.asset, "reason": reason})
                            log.warning("SKIP %s: %s", order.asset, reason)
                            continue
                # If ref_price is None and pair_price is also None → can't verify
                # Strategy says: "SKIP if priceUsd or the reference is missing"
                if ref_price is None:
                    pair_price = await mcp.fetch_pair_price(order.ticker)
                    if pair_price is None:
                        reason = "cannot verify price — both ref and pair_price missing"
                        orders_skipped.append({"asset": order.asset, "reason": reason})
                        log.warning("SKIP %s: %s", order.asset, reason)
                        continue

            # ---- 6c. Determine quote asset and recompute order_size ----
            ticker = order.ticker or ""
            quote_asset = ticker.split("/")[-1] if "/" in ticker else "USDT"
            if _is_stablecoin(quote_asset) or _is_fiat(quote_asset):
                pass  # usable as quote
            else:
                # Quote is not a stablecoin — we'd need conversion. Skip.
                reason = f"quote asset {quote_asset} is not a stablecoin/fiat — conversion needed"
                orders_skipped.append({"asset": order.asset, "reason": reason})
                log.warning("SKIP %s: %s", order.asset, reason)
                continue

            # For exits: size = 100 % of position (close full position)
            # For entries: size comes from strategy rules
            if order.action == "sell":
                # Exit: close 100 % of the position
                order.order_size = 100.0
            else:
                # Entry: determine size from breakout recency
                if radar_row and _breakout_within_days(radar_row):
                    size_pct_of_nav = CONFIG["BREAKOUT_RECENT_SIZE_PCT"]
                else:
                    size_pct_of_nav = CONFIG["DEFAULT_ENTRY_SIZE_PCT"]
                fresh_pct = executor.compute_order_pct(nav_before, size_pct_of_nav, quote_asset)
                if fresh_pct <= 0:
                    reason = f"insufficient quote balance for {quote_asset}"
                    orders_skipped.append({"asset": order.asset, "reason": reason})
                    log.warning("SKIP %s: %s", order.asset, reason)
                    continue
                order.order_size = fresh_pct

            # ---- 6d. Minimum order value guardrail ----
            quote_balance = executor._get_quote_balance(quote_asset)
            min_err = validate_min_order(order, nav_before, quote_balance)
            if min_err:
                orders_skipped.append({"asset": order.asset, "reason": min_err})
                log.warning("SKIP %s: %s", order.asset, min_err)
                continue

            # ---- 6e. Set trading pair (best-effort, warn if unsupported) ----
            if order.ticker:
                await mcp.set_trading_pair(order.ticker)

            # ---- 6f. Send order ----
            # Use unique timestamp per order (idempotency)
            ts = (timestamp_base + timedelta(seconds=len(orders_sent))).isoformat()
            success = await executor.send_order(order, ts)
            if success:
                # Debit local balance tracker
                order_value = (order.order_size / 100.0) * quote_balance
                executor._debit_quote(quote_asset, order_value)

                orders_sent.append({
                    "action": order.action,
                    "ticker": order.ticker,
                    "size_pct": order.order_size,
                    "pos_size": order.position_size,
                    "reason": order.reasoning[:150],
                })

                if order.action == "sell":
                    exited_assets.add(asset_key)
                    held_assets_now.discard(asset_key)
                elif order.action == "buy":
                    entered_assets.add(asset_key)
                    held_assets_now.add(asset_key)
            else:
                reason = f"order POST failed for {order.ticker}"
                orders_skipped.append({"asset": order.asset, "reason": reason})

        # --- Step 7: Bot title suffix (best-effort) ---
        if not dry_run:
            updated = await mcp.update_bot_title_suffix("(TR-GC-Crypto-9)")
            if not updated:
                log.warning("Could not update bot title suffix — MCP may not support edit-bot.")

        # --- Step 8: Verification ---
        nav_after: Optional[float] = None
        try:
            post_holdings = await mcp.fetch_holdings()
            nav_after = _compute_nav(post_holdings)
            log.info("NAV after: $%.2f", nav_after)
            verification_errors = await verify_holdings(
                mcp, held_assets_now, exited_assets, entered_assets,
            )
            errors.extend(verification_errors)
        except Exception as exc:
            errors.append(f"Verification failed: {exc}")

    finally:
        await mcp.close()

    # --- Step 9: Telegram notification ---
    await _maybe_notify(
        telegram_token, telegram_chat_id, nav_before, nav_after,
        orders_sent, orders_skipped, errors, dry_run,
    )

    log.info("=== Run complete === mode=%s orders_sent=%d skipped=%d errors=%d",
             "dry-run" if dry_run else "LIVE", len(orders_sent), len(orders_skipped), len(errors))


async def _maybe_notify(
    token: str, chat_id: str, nav_before: float, nav_after: Optional[float],
    orders_sent: list, orders_skipped: list, errors: list, dry_run: bool,
) -> None:
    """Send Telegram notification if configured; log failure but don't crash."""
    if not token or not chat_id:
        log.info("Telegram not configured — skipping notification.")
        return
    msg = _build_telegram_summary(nav_before, nav_after, orders_sent, orders_skipped, errors, dry_run)
    await send_telegram(token, chat_id, msg)


# ═══════════════════════════════════════════════════════════════════════════
# 14. CLI Entrypoint
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="DeepSeek Trading Bot — TR-GC-Crypto-9 (Bot ID 25880)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Send real orders to Signum (default: dry-run, which only logs intended actions).",
    )
    args = parser.parse_args()
    live = args.live

    if live:
        log.warning("=" * 60)
        log.warning("  LIVE MODE — real orders will be sent to the exchange.")
        log.warning("=" * 60)

    asyncio.run(run(dry_run=not live))


if __name__ == "__main__":
    main()
