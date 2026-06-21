# Graph Report - C:\Deep-Onion-crybot-signum  (2026-06-21)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 168 nodes · 274 edges · 11 communities (10 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6bc6afd4`
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

## God Nodes (most connected - your core abstractions)
1. `run()` - 32 edges
2. `SignumMCPClient` - 20 edges
3. `_retry_with_backoff()` - 14 edges
4. `OrderExecutor` - 9 edges
5. `verify_holdings()` - 9 edges
6. `Order` - 8 edges
7. `Any` - 8 edges
8. `_norm_asset()` - 8 edges
9. `_iter_holdings()` - 8 edges
10. `_get_quote_balance()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `README.md - Project Overview` --references--> `requirements.txt - Python Dependencies`  [EXTRACTED]
  README.md → requirements.txt
- `CLAUDE.md - Project Rules` --references--> `graphify-out/GRAPH_REPORT.md`  [EXTRACTED]
  CLAUDE.md → graphify-out/GRAPH_REPORT.md

## Import Cycles
- None detected.

## Communities (11 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (38): _breakout_within_days(), _build_telegram_summary(), _candle_gc_upper(), _find_trend_radar_row(), _FlushingHandler, _is_in_trend_radar(), main(), _maybe_notify() (+30 more)

### Community 1 - "Community 1"
Cohesion: 0.12
Nodes (16): Any, Call an async function with exponential-backoff retries., Async client for Signum's MCP server.      Uses direct JSON-RPC 2.0 over HTTP (n, Exchange the refresh token for a fresh access token via OAuth., Send a single JSON-RPC call and return the result., Establish an MCP session via JSON-RPC over HTTP.          1. Get OAuth access to, Call an MCP tool by name via tools/call. Returns parsed result., Fetch current HOLDINGS / positions for Bot ID 25880. (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (22): _compute_nav(), _get_quote_balance(), _is_fiat(), _is_stablecoin(), _iter_holdings(), _norm_asset(), OrderExecutor, Re-fetch HOLDINGS and compare against expected end-state.      Returns a list of (+14 more)

### Community 3 - "Community 3"
Cohesion: 0.14
Nodes (16): BaseHTTPRequestHandler, _build_authorize_url(), CallbackHandler, _exchange_code(), main(), _pkce_challenge(), _print_token_summary(), Register a new OAuth client at Signum. Returns the JSON response. (+8 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (12): BaseModel, DeepSeekClient, Order, OrdersResponse, A single trading order produced by DeepSeek., Wrapper for the DeepSeek JSON response., Async client for DeepSeek V4 Pro (OpenAI-compatible API)., Send holdings + trend radar data, receive structured JSON orders.          Uses (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.58
Nodes (8): AsyncClient, Response, hr(), main(), print_response(), probe_discovery(), probe_mcp_no_auth(), probe_mcp_protocol()

### Community 6 - "Community 6"
Cohesion: 0.25
Nodes (7): balance, positions, prompt_snapshot, holdings, trend_radar, response_raw, timestamp

### Community 7 - "Community 7"
Cohesion: 0.33
Nodes (6): _candle_close(), _get_ref_price(), _latest_candle(), Return the latest (newest) candle from indicators.data[]., Extract ohlc.c (close) from a candle., Get the USD reference price for ticker-collision guard.      Priority: cmcRefPri

### Community 8 - "Community 8"
Cohesion: 0.40
Nodes (5): DECIDE Phase, NOTIFY Phase, READ Phase, VERIFY Phase, WRITE Phase

### Community 9 - "Community 9"
Cohesion: 0.67
Nodes (3): CLAUDE.md - Project Rules, graphify query tool, graphify-out/GRAPH_REPORT.md

## Knowledge Gaps
- **12 isolated node(s):** `timestamp`, `balance`, `positions`, `trend_radar`, `response_raw` (+7 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run()` connect `Community 2` to `Community 0`, `Community 1`, `Community 4`, `Community 7`?**
  _High betweenness centrality (0.163) - this node is a cross-community bridge._
- **Why does `SignumMCPClient` connect `Community 1` to `Community 0`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Why does `_retry_with_backoff()` connect `Community 1` to `Community 0`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **What connects `timestamp`, `balance`, `positions` to the rest of the system?**
  _66 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05897435897435897 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.11954022988505747 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.1225071225071225 - nodes in this community are weakly interconnected._