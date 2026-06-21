#!/usr/bin/env python3
"""
Signum OAuth Setup — one-time PKCE flow to get a refresh token.

Usage:
  python setup_oauth.py

This script:
  1. Registers a new OAuth client at Signum (no auth required)
  2. Generates PKCE code_verifier + S256 code_challenge
  3. Opens your browser to Signum's authorize page
  4. Starts a local HTTP server on port 8080 to catch the redirect
  5. Exchanges the auth code for access_token + refresh_token
  6. Prints the full token response (tokens redacted) so you can verify
     that offline_access scope actually granted a refresh_token
  7. Saves the refresh_token to your .env file

You only run this ONCE. After that, the main bot uses the refresh token
to get fresh access tokens automatically.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

# ── Config ───────────────────────────────────────────────────────

AUTHORIZE_URL = "https://api.signum.money/oauth/authorize"
TOKEN_URL = "https://api.signum.money/oauth/token"
REGISTER_URL = "https://api.signum.money/oauth/register"

REDIRECT_URI = "http://localhost:8080/callback"
LOCAL_PORT = 8080

SCOPES = "read write trading offline_access"

ENV_FILE = ".env"
ENV_KEY_REFRESH = "SIGNUM_REFRESH_TOKEN"
ENV_KEY_CLIENT_ID = "SIGNUM_CLIENT_ID"

# ═══════════════════════════════════════════════════════════════════

# Global to pass the auth code from the HTTP handler back to main
_auth_code: str | None = None
_auth_error: str | None = None
_state: str = ""


def _pkce_challenge() -> tuple[str, str]:
    """Generate PKCE code_verifier and S256 code_challenge.

    Returns (verifier, challenge) — both base64url-encoded (no padding).
    """
    verifier = secrets.token_urlsafe(64)  # 64 bytes → 86 chars base64url
    # Truncate to exactly between 43-128 chars for spec compliance
    verifier = verifier[:96]

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class CallbackHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler to catch the OAuth redirect."""

    def log_message(self, format, *args):
        # Silence HTTP server logs
        pass

    def do_GET(self):
        global _auth_code, _auth_error, _state

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/callback":
            if "error" in params:
                _auth_error = params["error"][0]
                desc = params.get("error_description", [""])[0]
                self._respond(400, f"<h1>Authorization Failed</h1><p>{desc}</p>")
            elif "code" not in params:
                _auth_error = "no_code"
                self._respond(400, "<h1>Error</h1><p>No authorization code received.</p>")
            else:
                # Verify state to prevent CSRF
                returned_state = params.get("state", [""])[0]
                if returned_state != _state:
                    _auth_error = "state_mismatch"
                    self._respond(400, "<h1>Error</h1><p>State mismatch — possible CSRF.</p>")
                    return

                _auth_code = params["code"][0]
                self._respond(200, "<h1>Success!</h1><p>You can close this window.</p>")
        else:
            self._respond(404, "<h1>Not Found</h1>")

    def _respond(self, code: int, body: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


def _register_client() -> dict:
    """Register a new OAuth client at Signum. Returns the JSON response."""
    print("Registering OAuth client...")
    payload = {
        "client_name": "DeepSeek Trading Bot",
        "redirect_uris": [REDIRECT_URI],
        "scope": SCOPES,
    }
    resp = httpx.post(REGISTER_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    print(f"  Client ID: {data['client_id']}")
    print(f"  Token auth method: {data.get('token_endpoint_auth_method', 'unknown')}")
    print(f"  Redirect URIs: {data.get('redirect_uris')}")
    return data


def _build_authorize_url(client_id: str, challenge: str) -> str:
    """Build the full authorize URL with PKCE challenge."""
    global _state
    _state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": _state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _exchange_code(client_id: str, code: str, verifier: str) -> dict:
    """Exchange authorization code for tokens. Returns the full JSON response."""
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = httpx.post(TOKEN_URL, data=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _print_token_summary(token_response: dict) -> None:
    """Print token response with secrets redacted so the user can verify it."""
    print("\n" + "=" * 60)
    print("  TOKEN RESPONSE (secrets redacted)")
    print("=" * 60)

    for key in sorted(token_response.keys()):
        value = token_response[key]
        if key in ("access_token", "refresh_token"):
            # Redact but show presence + first/last 6 chars
            val_str = str(value)
            if len(val_str) > 12:
                shown = f"{val_str[:6]}...{val_str[-6:]} ({len(val_str)} chars)"
            else:
                shown = f"*** ({len(val_str)} chars)"
            print(f"  {key}: {shown}")
        elif isinstance(value, (int, float)):
            print(f"  {key}: {value}")
        elif isinstance(value, str):
            print(f"  {key}: {value}")
        elif isinstance(value, list):
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {json.dumps(value)}")

    # Check for refresh_token presence
    has_refresh = bool(token_response.get("refresh_token"))
    has_access = bool(token_response.get("access_token"))
    print(f"\n  access_token present:  {'YES' if has_access else 'NO — FAILED'}")
    print(f"  refresh_token present: {'YES' if has_refresh else 'NO — FAILED'}")

    if has_refresh:
        print("\n  offline_access scope WORKED — refresh token granted.")
        print("  This refresh token can be used indefinitely by the main bot.")
    else:
        print("\n  WARNING: No refresh_token in response!")
        print("  The offline_access scope may not have been honored.")
        print("  Check that you authorized ALL requested scopes.")


def _save_to_env(client_id: str, refresh_token: str) -> None:
    """Save client_id and refresh_token to the .env file."""
    # Read existing .env if any
    existing: dict[str, str] = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

    # Update/add the Signum values
    existing[ENV_KEY_CLIENT_ID] = client_id
    existing[ENV_KEY_REFRESH] = refresh_token

    # Write back
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        # Preserve a header comment
        f.write("# DeepSeek Trading Bot — Environment Variables\n")
        f.write("# Generated by setup_oauth.py\n\n")
        for k, v in sorted(existing.items()):
            if k in (ENV_KEY_CLIENT_ID, ENV_KEY_REFRESH):
                f.write(f"# Signum OAuth (auto-generated)\n")
                f.write(f"{k}={v}\n\n")
            else:
                f.write(f"{k}={v}\n")

    print(f"\nSaved to {ENV_FILE}:")
    print(f"  {ENV_KEY_CLIENT_ID}={client_id}")
    print(f"  {ENV_KEY_REFRESH}={refresh_token[:6]}...{refresh_token[-6:]}")


# ═══════════════════════════════════════════════════════════════════


def main() -> None:
    global _auth_code, _auth_error

    print("Signum OAuth Setup — PKCE Flow")
    print("=" * 60)
    print(f"Scopes requested: {SCOPES}")
    print(f"Redirect URI:     {REDIRECT_URI}")
    print()

    # ── Step 1: Register client ──
    registration = _register_client()
    client_id = registration["client_id"]

    # ── Step 2: Generate PKCE ──
    verifier, challenge = _pkce_challenge()
    print(f"PKCE verifier:  {verifier[:20]}... ({len(verifier)} chars)")
    print(f"PKCE challenge: {challenge[:20]}... ({len(challenge)} chars)")

    # ── Step 3: Build authorize URL ──
    auth_url = _build_authorize_url(client_id, challenge)
    print(f"\nAuthorize URL:\n  {auth_url}\n")

    # ── Step 4: Open browser + start local server ──
    print("Opening browser for Signum authorization...")
    print(f"Listening on http://localhost:{LOCAL_PORT}/callback ...")
    print("(If the browser doesn't open, copy the URL above and paste it.)\n")

    webbrowser.open(auth_url)

    server = HTTPServer(("127.0.0.1", LOCAL_PORT), CallbackHandler)
    server.timeout = 120  # 2-minute timeout

    # Wait for the callback (the handler sets _auth_code or _auth_error)
    while _auth_code is None and _auth_error is None:
        server.handle_request()

    server.server_close()

    if _auth_error:
        print(f"\nAuthorization FAILED: {_auth_error}")
        if _auth_error == "state_mismatch":
            print("Possible CSRF attack — state parameter didn't match.")
        sys.exit(1)

    print(f"\nAuthorization code received: {_auth_code[:10]}...")

    # ── Step 5: Exchange code for tokens ──
    print("Exchanging authorization code for tokens...")
    try:
        token_response = _exchange_code(client_id, _auth_code, verifier)
    except httpx.HTTPStatusError as exc:
        print(f"Token exchange FAILED: {exc.response.status_code}")
        try:
            print(json.dumps(exc.response.json(), indent=2))
        except Exception:
            print(exc.response.text[:500])
        sys.exit(1)

    # ── Step 6: Print results ──
    _print_token_summary(token_response)

    refresh_token = token_response.get("refresh_token")
    if not refresh_token:
        print("\nFATAL: No refresh_token in response. Cannot proceed.")
        print("Make sure you approved ALL scopes (especially offline_access).")
        sys.exit(1)

    # ── Step 7: Save to .env ──
    _save_to_env(client_id, refresh_token)

    print("\nDone! The main bot can now use the refresh token automatically.")
    print("You do NOT need to run this setup again unless the token is revoked.")


if __name__ == "__main__":
    main()
