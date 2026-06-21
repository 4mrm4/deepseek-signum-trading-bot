# Graph Report - Deep-Onion-crybot-signum  (2026-06-21)

## Corpus Check
- 9 files · ~11,403 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 279 nodes · 450 edges · 16 communities (15 shown, 1 thin omitted)
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
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]

## God Nodes (most connected - your core abstractions)
1. `run()` - 44 edges
2. `SignumMCPClient` - 23 edges
3. `_retry_with_backoff()` - 16 edges
4. `PaperPortfolio` - 14 edges
5. `_norm_asset()` - 13 edges
6. `Any` - 12 edges
7. `OrderExecutor` - 12 edges
8. `verify_holdings()` - 11 edges
9. `Order` - 10 edges
10. `_iter_holdings()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `README.md - Project Overview` --references--> `requirements.txt - Python Dependencies`  [EXTRACTED]
  README.md → requirements.txt
- `CLAUDE.md - Project Rules` --references--> `graphify-out/GRAPH_REPORT.md`  [EXTRACTED]
  CLAUDE.md → graphify-out/GRAPH_REPORT.md

## Import Cycles
- None detected.

## Communities (16 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (44): _breakout_within_days(), _candle_close(), _candle_gc_upper(), _find_trend_radar_row(), _FlushingHandler, _get_ref_price(), _is_in_trend_radar(), _latest_candle() (+36 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (29): Any, Call an async function with exponential-backoff retries., Call an async function with exponential-backoff retries., Async client for Signum's MCP server.      Uses direct JSON-RPC 2.0 over HTTP (n, Async client for Signum's MCP server.      Uses direct JSON-RPC 2.0 over HTTP, Exchange the refresh token for a fresh access token via OAuth., Exchange the refresh token for a fresh access token via OAuth., Send a single JSON-RPC call and return the result. (+21 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (42): _compute_nav(), _get_quote_balance(), _is_fiat(), _is_stablecoin(), _iter_holdings(), _norm_asset(), OrderExecutor, PaperExecutor (+34 more)

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
Cohesion: 0.36
Nodes (12): compute_current_nav(), load_paper_state(), main(), nav_curve(), print_brief(), print_full(), print_trades(), Any (+4 more)

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
Cohesion: 0.17
Nodes (12): _build_telegram_summary(), _maybe_notify(), Send a Telegram message via Bot API. Returns True on success.      Failure is lo, Build a human-readable Telegram summary message., Return {asset_upper: usd_value} for all cash/stablecoin balances., Build a human-readable Telegram summary message., Send Telegram notification if configured; log failure but don't crash., Send a Telegram message via Bot API. Returns True on success.      Failure is (+4 more)

### Community 12 - "Community 12"
Cohesion: 0.40
Nodes (4): CRITICAL - Do not explore files directly, How to understand this project, Rules for this project, Workflow for every task

### Community 14 - "Community 14"
Cohesion: 0.29
Nodes (6): balances, USD, created, initial_balance, positions, trade_history

### Community 15 - "Community 15"
Cohesion: 0.40
Nodes (4): _prev_candle(), Initialize / refresh the local quote-balance tracker., Return the second-to-last candle from indicators.data[]., Return the second-to-last candle from indicators.data[].

## Knowledge Gaps
- **29 isolated node(s):** `created`, `initial_balance`, `USD`, `positions`, `trade_history` (+24 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run()` connect `Community 2` to `Community 0`, `Community 1`, `Community 4`, `Community 6`, `Community 11`, `Community 15`?**
  _High betweenness centrality (0.188) - this node is a cross-community bridge._
- **Why does `SignumMCPClient` connect `Community 1` to `Community 0`, `Community 2`, `Community 6`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `_retry_with_backoff()` connect `Community 1` to `Community 0`, `Community 2`, `Community 4`, `Community 6`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **What connects `Fetch a required secret; abort with a clear message if missing.`, `Persist a rotated refresh token back to the .env file.`, `StreamHandler that flushes after every emit — needed on Windows.` to the rest of the system?**
  _136 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.050241545893719805 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.06871035940803383 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.06291591046581972 - nodes in this community are weakly interconnected._