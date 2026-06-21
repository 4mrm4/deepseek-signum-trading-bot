# Graph Report - Deep-Onion-crybot-signum  (2026-06-21)

## Corpus Check
- 7 files · ~8,933 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 230 nodes · 346 edges · 14 communities (13 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `880bbd2a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]

## God Nodes (most connected - your core abstractions)
1. `run()` - 34 edges
2. `SignumMCPClient` - 22 edges
3. `_retry_with_backoff()` - 15 edges
4. `OrderExecutor` - 11 edges
5. `verify_holdings()` - 10 edges
6. `Order` - 9 edges
7. `_norm_asset()` - 9 edges
8. `_iter_holdings()` - 9 edges
9. `_get_quote_balance()` - 9 edges
10. `DeepSeek Trading Bot — TR-GC-Crypto-9` - 9 edges

## Surprising Connections (you probably didn't know these)
- `README.md - Project Overview` --references--> `requirements.txt - Python Dependencies`  [EXTRACTED]
  README.md → requirements.txt
- `CLAUDE.md - Project Rules` --references--> `graphify-out/GRAPH_REPORT.md`  [EXTRACTED]
  CLAUDE.md → graphify-out/GRAPH_REPORT.md

## Import Cycles
- None detected.

## Communities (14 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (34): _breakout_within_days(), _candle_gc_upper(), _find_trend_radar_row(), _FlushingHandler, _is_in_trend_radar(), main(), _prev_candle(), Fetch a required secret; abort with a clear message if missing. (+26 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (35): Any, _normalise_holdings(), Persist a rotated refresh token back to the .env file., Call an async function with exponential-backoff retries., Call an async function with exponential-backoff retries., Async client for Signum's MCP server.      Uses direct JSON-RPC 2.0 over HTTP (n, Async client for Signum's MCP server.      Uses direct JSON-RPC 2.0 over HTTP, Exchange the refresh token for a fresh access token via OAuth. (+27 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (27): _compute_nav(), _get_quote_balance(), _is_fiat(), _is_stablecoin(), _iter_holdings(), _norm_asset(), OrderExecutor, Sends orders via Signum's MCP 'send-trading-signal' tool, one-at-a-time, sequent (+19 more)

### Community 3 - "Community 3"
Cohesion: 0.14
Nodes (16): BaseHTTPRequestHandler, _build_authorize_url(), CallbackHandler, _exchange_code(), main(), _pkce_challenge(), _print_token_summary(), Register a new OAuth client at Signum. Returns the JSON response. (+8 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (12): BaseModel, Order, OrdersResponse, Send a single order via Signum's MCP send-trading-signal tool.         Returns, A single trading order produced by DeepSeek., A single trading order produced by DeepSeek., Wrapper for the DeepSeek JSON response., Wrapper for the DeepSeek JSON response. (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.58
Nodes (8): AsyncClient, Response, hr(), main(), print_response(), probe_discovery(), probe_mcp_no_auth(), probe_mcp_protocol()

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (13): DeepSeekClient, _extract_json_from_text(), Async client for DeepSeek V4 Pro (OpenAI-compatible API)., Async client for DeepSeek V4 Pro (OpenAI-compatible API)., Send holdings + trend radar data, receive structured JSON orders.          Uses, Send holdings + trend radar data, receive structured JSON orders.          Use, Persist the DeepSeek prompt + response to decisions/ for audit trail., Remove markdown code fences (```json ... ```) from DeepSeek output. (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (9): _candle_close(), _get_ref_price(), _latest_candle(), Return the latest (newest) candle from indicators.data[]., Extract ohlc.c (close) from a candle., Get the USD reference price for ticker-collision guard.      Priority: cmcRefPri, Return the latest (newest) candle from indicators.data[]., Extract ohlc.c (close) from a candle. (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.40
Nodes (5): DECIDE Phase, NOTIFY Phase, READ Phase, VERIFY Phase, WRITE Phase

### Community 9 - "Community 9"
Cohesion: 0.67
Nodes (3): CLAUDE.md - Project Rules, graphify query tool, graphify-out/GRAPH_REPORT.md

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (15): Architecture, Audit Trail, DeepSeek Trading Bot — TR-GC-Crypto-9, Dependencies, Entry Sizing (computed from NAV snapshot, never recomputed mid-run), Environment Variables, Files, License (+7 more)

### Community 11 - "Community 11"
Cohesion: 0.22
Nodes (9): _build_telegram_summary(), _maybe_notify(), Send a Telegram message via Bot API. Returns True on success.      Failure is lo, Build a human-readable Telegram summary message., Send a Telegram message via Bot API. Returns True on success.      Failure is, Build a human-readable Telegram summary message., Send Telegram notification if configured; log failure but don't crash., Send Telegram notification if configured; log failure but don't crash. (+1 more)

### Community 12 - "Community 12"
Cohesion: 0.40
Nodes (4): CRITICAL - Do not explore files directly, How to understand this project, Rules for this project, Workflow for every task

## Knowledge Gaps
- **24 isolated node(s):** `_comment`, `orders`, `Response`, `CRITICAL - Do not explore files directly`, `How to understand this project` (+19 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run()` connect `Community 2` to `Community 0`, `Community 1`, `Community 4`, `Community 6`, `Community 7`, `Community 11`?**
  _High betweenness centrality (0.181) - this node is a cross-community bridge._
- **Why does `SignumMCPClient` connect `Community 1` to `Community 0`, `Community 2`, `Community 6`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Why does `_retry_with_backoff()` connect `Community 1` to `Community 0`, `Community 4`, `Community 6`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **What connects `Fetch a required secret; abort with a clear message if missing.`, `Persist a rotated refresh token back to the .env file.`, `StreamHandler that flushes after every emit — needed on Windows.` to the rest of the system?**
  _116 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06349206349206349 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.05725490196078432 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.10752688172043011 - nodes in this community are weakly interconnected._