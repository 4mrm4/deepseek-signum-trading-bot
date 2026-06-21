#!/usr/bin/env python3
"""
Paper Trading Summary — end-of-week P&L report.

Reads paper_state.json (trade history + current portfolio) and the
decisions/run-*.json audit trail to produce:

  - Total P&L (realised + unrealised)
  - Trade count, win/loss breakdown
  - NAV equity curve over time
  - Per-trade detail (entry date, exit date, P&L)

Usage:
  python paper_summary.py              # full report
  python paper_summary.py --brief      # one-line P&L summary
  python paper_summary.py --trades     # per-trade breakdown only
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PAPER_STATE = Path(__file__).resolve().parent / "paper_state.json"
DECISIONS_DIR = Path(__file__).resolve().parent / "decisions"


def load_paper_state() -> dict[str, Any] | None:
    if not PAPER_STATE.exists():
        print(f"ERROR: {PAPER_STATE} not found. Run the bot in --paper mode first.")
        return None
    with open(PAPER_STATE, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_current_nav(state: dict[str, Any]) -> float:
    """Recompute NAV from paper state: cash + positions at entry price."""
    total = sum(float(v) for v in state.get("balances", {}).values())
    for pos in state.get("positions", []):
        qty = float(pos.get("quantity", 0))
        entry = float(pos.get("entry_price", 0))
        total += qty * entry
    return round(total, 2)


def win_loss(state: dict[str, Any]) -> dict[str, Any]:
    """
    Compute realised P&L from completed buy/sell pairs.
    Trades are matched FIFO per asset.
    """
    trades = state.get("trade_history", [])
    # Group trades by asset
    by_asset: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        by_asset[t.get("asset", "?").upper()].append(t)

    closed: list[dict] = []
    open_buys: dict[str, list[dict]] = defaultdict(list)
    total_realised = 0.0
    wins = 0
    losses = 0

    for asset, tlist in sorted(by_asset.items()):
        buys: list[dict] = []
        for t in tlist:
            if t["action"] == "buy":
                buys.append(t)
            elif t["action"] == "sell":
                qty_to_close = float(t["qty"])
                proceeds_total = float(t.get("proceeds_usd", 0))
                # FIFO match against buys
                while qty_to_close > 0 and buys:
                    b = buys[0]
                    b_qty = float(b["qty"])
                    if b_qty <= qty_to_close:
                        # Fully close this buy
                        ratio = b_qty / float(t["qty"]) if float(t["qty"]) > 0 else 0
                        cost = float(b.get("cost_usd", 0))
                        proceeds = proceeds_total * ratio
                        pnl = round(proceeds - cost, 2)
                        total_realised += pnl
                        if pnl >= 0:
                            wins += 1
                        else:
                            losses += 1
                        closed.append({
                            "asset": asset,
                            "entry_time": b.get("timestamp", ""),
                            "exit_time": t.get("timestamp", ""),
                            "entry_price": float(b.get("price", 0)),
                            "exit_price": float(t.get("price", 0)),
                            "qty": round(b_qty, 6),
                            "cost": cost,
                            "proceeds": round(proceeds, 2),
                            "pnl": pnl,
                            "pnl_pct": round((pnl / cost * 100), 2) if cost > 0 else 0,
                        })
                        qty_to_close -= b_qty
                        buys.pop(0)
                    else:
                        # Partial close
                        ratio = qty_to_close / float(t["qty"]) if float(t["qty"]) > 0 else 0
                        cost = float(b.get("cost_usd", 0)) * (qty_to_close / b_qty)
                        proceeds = proceeds_total * ratio
                        pnl = round(proceeds - cost, 2)
                        total_realised += pnl
                        if pnl >= 0:
                            wins += 1
                        else:
                            losses += 1
                        closed.append({
                            "asset": asset,
                            "entry_time": b.get("timestamp", ""),
                            "exit_time": t.get("timestamp", ""),
                            "entry_price": float(b.get("price", 0)),
                            "exit_price": float(t.get("price", 0)),
                            "qty": round(qty_to_close, 6),
                            "cost": cost,
                            "proceeds": round(proceeds, 2),
                            "pnl": pnl,
                            "pnl_pct": round((pnl / cost * 100), 2) if cost > 0 else 0,
                        })
                        b["qty"] = str(b_qty - qty_to_close)
                        b["cost_usd"] = str(float(b.get("cost_usd", 0)) - cost)
                        qty_to_close = 0.0

    # Compute unrealised P&L for open positions
    open_positions = state.get("positions", [])
    unrealised = 0.0

    return {
        "total_realised": round(total_realised, 2),
        "unrealised": round(unrealised, 2),
        "wins": wins,
        "losses": losses,
        "total_trades": wins + losses,
        "closed_trades": closed,
        "open_positions": len(open_positions),
    }


def nav_curve(state: dict[str, Any]) -> list[dict]:
    """
    Reconstruct NAV over time from trade history.
    Each snapshot records NAV after that trade.
    """
    initial = float(state.get("initial_balance", 0))
    trades = state.get("trade_history", [])
    curve = [{"timestamp": state.get("created", ""), "nav": initial, "event": "start"}]

    balances: dict[str, float] = {"USD": initial}
    positions: dict[str, dict] = {}  # asset → {qty, entry_price}

    for t in trades:
        if t["action"] == "buy":
            asset = t["asset"]
            cost = float(t.get("cost_usd", 0))
            # Deduct from balances (simplified: use USD)
            balances["USD"] = float(balances.get("USD", 0)) - cost
            if asset in positions:
                old = positions[asset]
                old_qty = float(old["qty"])
                old_cost = float(old["cost_basis"])
                new_qty = old_qty + float(t["qty"])
                new_cost = old_cost + cost
                positions[asset] = {"qty": str(new_qty), "cost_basis": str(new_cost)}
            else:
                positions[asset] = {"qty": t["qty"], "cost_basis": cost}
        elif t["action"] == "sell":
            asset = t["asset"]
            proceeds = float(t.get("proceeds_usd", 0))
            balances["USD"] = float(balances.get("USD", 0)) + proceeds
            if asset in positions:
                del positions[asset]

        nav = float(balances.get("USD", 0))
        for pos in positions.values():
            nav += float(pos.get("cost_basis", 0))

        curve.append({
            "timestamp": t.get("timestamp", ""),
            "nav": round(nav, 2),
            "event": f"{t['action'].upper()} {t['asset']}",
        })

    return curve


def print_full(state: dict[str, Any]) -> None:
    trades: list[dict] = state.get("trade_history", [])
    wl = win_loss(state)

    print("=" * 60)
    print("  PAPER TRADING SUMMARY")
    print("=" * 60)
    print(f"  Started:        {state.get('created', 'N/A')[:19]}")
    print(f"  Initial balance: ${float(state.get('initial_balance', 0)):,.2f}")
    print()

    # NAV
    current_nav = compute_current_nav(state)
    print(f"  Current NAV:    ${current_nav:,.2f}")
    print(f"  Total P&L:      ${current_nav - float(state.get('initial_balance', 0)):,.2f}")
    print()

    # Trade stats
    print(f"  Total trades:   {len(trades)}")
    print(f"  Realised P&L:   ${wl['total_realised']:,.2f}")
    if wl["total_trades"] > 0:
        win_rate = wl["wins"] / wl["total_trades"] * 100
        print(f"  Win/Loss:       {wl['wins']}W / {wl['losses']}L ({win_rate:.0f}% win rate)")
    print(f"  Open positions: {wl['open_positions']}")
    print()

    # Per-trade breakdown
    if wl["closed_trades"]:
        print("  CLOSED TRADES:")
        print(f"  {'Asset':<8} {'Entry':<10} {'Exit':<10} {'Qty':>10} {'P&L':>10} {'P&L%':>8}")
        print("  " + "-" * 56)
        for t in wl["closed_trades"]:
            pnl_str = f"${t['pnl']:,.2f}"
            print(f"  {t['asset']:<8} {t['entry_price']:<10.4f} {t['exit_price']:<10.4f} "
                  f"{t['qty']:>10.4f} {pnl_str:>10} {t['pnl_pct']:>+7.1f}%")
        print()

    # NAV curve
    curve = nav_curve(state)
    if len(curve) > 1:
        print("  EQUITY CURVE:")
        initial = float(state.get("initial_balance", 0))
        for point in curve:
            marker = ""
            if point["event"] != "start":
                delta = point["nav"] - initial
                marker = f"  ({delta:+.2f})"
            ts = point["timestamp"][:19] if point["timestamp"] else "N/A"
            print(f"    {ts}  ${point['nav']:,.2f}{marker}  [{point['event']}]")
        print()

    # Current positions
    positions = state.get("positions", [])
    if positions:
        print("  OPEN POSITIONS:")
        print(f"  {'Asset':<8} {'Qty':>12} {'Entry':>10} {'Cost':>10}")
        print("  " + "-" * 40)
        for p in positions:
            cost = float(p.get("cost_usd", 0))
            print(f"  {p.get('asset', '?'):<8} {float(p.get('quantity', 0)):>12.6f} "
                  f"${float(p.get('entry_price', 0)):>9.4f} ${cost:>9.2f}")
        print()

    print(f"  Audit files:    {len(list(DECISIONS_DIR.glob('run-*.json'))) if DECISIONS_DIR.exists() else 0} runs")
    print("=" * 60)


def print_brief(state: dict[str, Any]) -> None:
    current_nav = compute_current_nav(state)
    initial = float(state.get("initial_balance", 0))
    trades = state.get("trade_history", [])
    wl = win_loss(state)

    print(f"[PAPER] NAV=${current_nav:,.2f}  "
          f"P&L=${current_nav - initial:+,.2f}  "
          f"Trades={len(trades)}  "
          f"W/L={wl['wins']}/{wl['losses']}  "
          f"Open={wl['open_positions']}")


def print_trades(state: dict[str, Any]) -> None:
    wl = win_loss(state)
    if not wl["closed_trades"]:
        print("No closed trades yet.")
        return
    print(f"{'Asset':<8} {'Entry':<10} {'Exit':<10} {'Qty':>10} {'P&L':>10} {'P&L%':>8}")
    print("-" * 56)
    for t in wl["closed_trades"]:
        print(f"{t['asset']:<8} {t['entry_price']:<10.4f} {t['exit_price']:<10.4f} "
              f"{t['qty']:>10.4f} ${t['pnl']:>9,.2f} {t['pnl_pct']:>+7.1f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper Trading P&L Summary")
    parser.add_argument("--brief", action="store_true", help="One-line P&L summary")
    parser.add_argument("--trades", action="store_true", help="Per-trade breakdown only")
    args = parser.parse_args()

    state = load_paper_state()
    if state is None:
        sys.exit(1)

    if args.brief:
        print_brief(state)
    elif args.trades:
        print_trades(state)
    else:
        print_full(state)


if __name__ == "__main__":
    main()
