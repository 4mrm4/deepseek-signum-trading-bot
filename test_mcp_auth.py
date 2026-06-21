#!/usr/bin/env python3
"""
Diagnostic script: probe Signum MCP server to discover auth method.

Usage:
  python test_mcp_auth.py          # run all probes
  python test_mcp_auth.py --raw    # also print raw response bodies
"""

import argparse
import json
import sys
import textwrap

import httpx

MCP_URL = "https://api.signum.money/mcp"
ROOT_URL = "https://api.signum.money"

OAUTH_PATHS = [
    "/.well-known/oauth-authorization-server",
    "/.well-known/openid-configuration",
]

MCP_PATHS = [
    "/mcp/.well-known/oauth-authorization-server",
    "/mcp/.well-known/openid-configuration",
]

TIMEOUT = 15.0

# Minimal MCP initialize request (JSON-RPC per MCP spec)
MCP_INITIALIZE_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test_mcp_auth", "version": "1.0.0"},
    },
}


def hr(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def print_response(resp: httpx.Response, raw: bool = False) -> None:
    print(f"  Status: {resp.status_code} {resp.reason_phrase}")
    print(f"  URL:    {resp.url}")
    print(f"  Headers:")
    for key, value in resp.headers.items():
        # Truncate long header values
        val = value[:200] + "..." if len(value) > 200 else value
        print(f"    {key}: {val}")
    if raw:
        body = resp.text[:2000]
        print(f"  Body ({len(resp.text)} chars):")
        try:
            parsed = resp.json()
            print(json.dumps(parsed, indent=2)[:2000])
        except Exception:
            print(textwrap.indent(body, "    "))
    else:
        ct = resp.headers.get("content-type", "")
        body_preview = resp.text[:500]
        print(f"  Content-Type: {ct}")
        print(f"  Body preview ({len(resp.text)} chars):")
        print(textwrap.indent(body_preview, "    "))
        if len(resp.text) > 500:
            print(f"    ... ({len(resp.text) - 500} more chars, use --raw for full)")


# ────────────────────────────────────────────────────────────────
# Probe 1: raw GET + POST to MCP endpoint (no auth)
# ────────────────────────────────────────────────────────────────

async def probe_mcp_no_auth(client: httpx.AsyncClient, raw: bool) -> None:
    hr("Probe 1: MCP endpoint — unauthenticated GET")

    try:
        resp = await client.get(MCP_URL)
        print_response(resp, raw)
    except Exception as exc:
        print(f"  GET FAILED: {exc}")

    hr("Probe 1b: MCP endpoint — unauthenticated POST (empty body)")

    try:
        resp = await client.post(MCP_URL)
        print_response(resp, raw)
    except Exception as exc:
        print(f"  POST FAILED: {exc}")


# ────────────────────────────────────────────────────────────────
# Probe 2: OAuth / OpenID discovery
# ────────────────────────────────────────────────────────────────

async def probe_discovery(client: httpx.AsyncClient, raw: bool) -> None:
    hr("Probe 2: OAuth / OpenID discovery — root-level paths")

    for path in OAUTH_PATHS:
        url = f"{ROOT_URL}{path}"
        print(f"\n  GET {url}")
        try:
            resp = await client.get(url)
            print_response(resp, raw)
        except Exception as exc:
            print(f"  FAILED: {exc}")

    hr("Probe 2b: OAuth / OpenID discovery — under /mcp")

    for path in MCP_PATHS:
        url = f"{ROOT_URL}{path}"
        print(f"\n  GET {url}")
        try:
            resp = await client.get(url)
            print_response(resp, raw)
        except Exception as exc:
            print(f"  FAILED: {exc}")


# ────────────────────────────────────────────────────────────────
# Probe 3: MCP initialize (JSON-RPC POST + SSE GET)
# ────────────────────────────────────────────────────────────────

async def probe_mcp_protocol(client: httpx.AsyncClient, raw: bool) -> None:
    hr("Probe 3: MCP initialize — JSON-RPC POST (no auth)")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    try:
        resp = await client.post(
            MCP_URL,
            json=MCP_INITIALIZE_BODY,
            headers=headers,
        )
        print_response(resp, raw)
    except Exception as exc:
        print(f"  FAILED: {exc}")

    hr("Probe 3b: MCP SSE — GET with Accept: text/event-stream")

    sse_headers = {
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
    }
    try:
        resp = await client.get(MCP_URL, headers=sse_headers)
        print_response(resp, raw)
    except Exception as exc:
        print(f"  FAILED: {exc}")

    hr("Probe 3c: Re-check response headers from POST for auth scheme hints")

    try:
        resp = await client.post(
            MCP_URL,
            json=MCP_INITIALIZE_BODY,
            headers={"Content-Type": "application/json"},
        )
        www_auth = resp.headers.get("www-authenticate", "")
        if www_auth:
            print(f"  www-authenticate: {www_auth}")
            if "Bearer" in www_auth:
                print("  → Server wants Bearer token auth")
                # Parse realm, scope if present
                for part in www_auth.split(","):
                    print(f"    {part.strip()}")
            elif "Basic" in www_auth:
                print("  → Server wants Basic auth")
            else:
                print("  → Unknown auth scheme")
        else:
            print("  No www-authenticate header — server may use cookie/OAuth/session auth")
            # Check for Set-Cookie
            set_cookie = resp.headers.get("set-cookie", "")
            if set_cookie:
                print(f"  Set-Cookie present: {set_cookie[:200]}")

        # Also check common custom auth headers
        for hdr in ["x-api-key", "x-auth-token", "x-mcp-token", "authorization"]:
            val = resp.headers.get(hdr, "")
            if val:
                print(f"  Response had {hdr}: {val[:100]}")
    except Exception as exc:
        print(f"  FAILED: {exc}")


# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────

async def main(raw: bool) -> None:
    print("Signum MCP Auth Diagnostic")
    print(f"Target: {MCP_URL}")
    print(f"Time:   {__import__('datetime').datetime.now().isoformat()}")

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        await probe_mcp_no_auth(client, raw)
        await probe_discovery(client, raw)
        await probe_mcp_protocol(client, raw)

    hr("Done")
    print("Review the output above to determine the auth scheme Signum uses.")
    print("Key things to look for:")
    print("  - www-authenticate header → Bearer / Basic / other")
    print("  - OAuth discovery → token endpoint URL")
    print("  - 401 vs 403 vs 404 → whether endpoint exists at all")
    print("  - Set-Cookie → if session-based auth")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Probe Signum MCP auth scheme")
    parser.add_argument("--raw", action="store_true", help="Print full response bodies")
    args = parser.parse_args()

    import asyncio

    asyncio.run(main(raw=args.raw))
