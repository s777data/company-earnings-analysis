#!/usr/bin/env python3
"""Read-only Robinhood MCP client. No unofficial API and no invented fallback data."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


# The previous implementation launched /home/s777data/robinhood-mcp as a local
# stdio server. That path is deprecated. Calls now go through the profile-scoped
# OAuth bridge, which reads the active hosted robinhood-trading MCP config.
_PROFILE_HOME = Path(os.getenv("HERMES_PROFILE_HOME", "~/.hermes/profiles/options-wheel-agent")).expanduser()
_BRIDGE = Path(__file__).with_name("profile_robinhood_mcp_bridge.py")


def _hermes_python() -> str:
    explicit = os.getenv("HERMES_PYTHON")
    if explicit:
        return explicit
    hermes = shutil.which("hermes")
    if hermes:
        first_line = Path(hermes).read_text(encoding="utf-8").splitlines()[0]
        if first_line.startswith("#!"):
            return first_line[2:].strip()
    raise RuntimeError("Hermes Python interpreter is required for hosted MCP OAuth")


def _translate_call(tool: str, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    symbol = str(arguments.get("symbol", "")).upper()
    if tool == "get_account_info":
        return "get_accounts", {}
    if tool == "get_quote":
        return "get_equity_quotes", {"symbols": [symbol]}
    if tool == "get_fundamentals":
        return "get_equity_fundamentals", {"symbols": [symbol], "bounds": "regular"}
    if tool == "get_historicals":
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=35)
        return "get_equity_historicals", {
            "symbols": [symbol],
            "start_time": start.isoformat().replace("+00:00", "Z"),
            "end_time": end.isoformat().replace("+00:00", "Z"),
            "interval": "day",
            "bounds": "regular",
        }
    return tool, arguments


async def _call(tool: str, arguments: dict[str, Any]) -> Any:
    remote_tool, remote_args = _translate_call(tool, arguments)
    env = os.environ.copy()
    env["HERMES_PROFILE_HOME"] = str(_PROFILE_HOME)
    env["HERMES_PROFILE_CONFIG"] = str(_PROFILE_HOME / "config.yaml")
    proc = await asyncio.create_subprocess_exec(
        _hermes_python(), str(_BRIDGE), remote_tool, json.dumps(remote_args),
        cwd=str(_PROFILE_HOME), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "hosted Robinhood MCP bridge failed")
    try:
        return json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("hosted Robinhood MCP bridge returned invalid JSON") from exc


def _decode(result: Any) -> Any:
    """Compatibility decoder retained for existing unit-test imports."""
    if isinstance(result, (dict, list)):
        return result
    structured = getattr(result, "structuredContent", getattr(result, "structured_content", None))
    if structured is not None:
        return structured
    texts = [getattr(item, "text", "") for item in getattr(result, "content", []) if getattr(item, "text", None)]
    if not texts:
        return None
    try:
        return json.loads("\n".join(texts))
    except json.JSONDecodeError:
        return {"text": "\n".join(texts)}


def _first_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        if not data or not isinstance(data[0], dict):
            return {}
        first = data[0]
        for key in ("quote", "fundamentals", "data", "result"):
            if isinstance(first.get(key), dict):
                return first[key]
        return first
    if isinstance(data, dict):
        for key in ("quote", "fundamentals"):
            if isinstance(data.get(key), dict): return data[key]
        for key in ("result", "data", "results"):
            value = data.get(key)
            if isinstance(value, dict): return _first_dict(value)
            if isinstance(value, list): return _first_dict(value)
        return data
    return {}


def _account_matches(data: Any, expected: str) -> bool:
    if not isinstance(data, dict):
        return False
    container = data.get("data") if isinstance(data.get("data"), dict) else data
    accounts = container.get("accounts") if isinstance(container, dict) else None
    if not isinstance(accounts, list):
        accounts = data.get("results") if isinstance(data.get("results"), list) else []
    for account in accounts:
        if not isinstance(account, dict):
            continue
        number = account.get("account_number") or account.get("account")
        if str(number) == str(expected) and account.get("agentic_allowed") is True:
            return True
    return False


def _expected_account(explicit: str | None = None) -> str | None:
    if explicit or os.getenv("ROBINHOOD_EXPECTED_ACCOUNT"):
        return explicit or os.getenv("ROBINHOOD_EXPECTED_ACCOUNT")
    env_path = Path("~/.hermes/.env").expanduser()
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            if line.startswith("ROBINHOOD_EXPECTED_ACCOUNT="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def get_quote(symbol: str, expected_account: str | None = None) -> dict[str, Any]:
    expected = _expected_account(expected_account)
    if not expected:
        raise RuntimeError("ROBINHOOD_EXPECTED_ACCOUNT is required to verify the authorized account")
    account_data = asyncio.run(_call("get_account_info", {}))
    if not _account_matches(account_data, expected):
        raise RuntimeError("Robinhood MCP account does not match the authorized agentic account")
    quote = _first_dict(asyncio.run(_call("get_quote", {"symbol": symbol.upper()})))
    fundamentals = _first_dict(asyncio.run(_call("get_fundamentals", {"symbol": symbol.upper()})))
    regular_close_price = None
    regular_close_timestamp = None
    try:
        historicals = asyncio.run(_call("get_historicals", {
            "symbol": symbol.upper(), "interval": "day", "span": "month",
        }))
        if isinstance(historicals, dict):
            historicals = historicals.get("result") or historicals.get("data") or historicals.get("results") or []
        completed = [row for row in historicals if isinstance(row, dict) and row.get("close_price")]
        if completed:
            candle = completed[-1]
            regular_close_price = float(candle["close_price"])
            regular_close_timestamp = candle.get("begins_at")
    except Exception:
        pass
    def number(*keys):
        for source in (quote, fundamentals):
            for key in keys:
                value = source.get(key)
                if value not in (None, ""):
                    try: return float(value)
                    except (TypeError, ValueError): pass
        return None
    live_regular_price = number("last_trade_price", "price", "mark_price")
    live_regular_timestamp = quote.get("venue_last_trade_time") or quote.get("updated_at") or quote.get("last_updated_at")
    use_daily_close = regular_close_price is not None
    if use_daily_close and live_regular_timestamp and regular_close_timestamp:
        try:
            live_day = datetime.fromisoformat(live_regular_timestamp.replace("Z", "+00:00")).date()
            candle_day = datetime.fromisoformat(regular_close_timestamp.replace("Z", "+00:00")).date()
            use_daily_close = candle_day >= live_day
        except ValueError:
            pass
    selected_price = regular_close_price if use_daily_close else live_regular_price
    selected_timestamp = regular_close_timestamp if use_daily_close else live_regular_timestamp
    selected_source = ("robinhood-trading MCP completed daily regular-session close" if use_daily_close
                       else "robinhood-trading MCP regular-session last trade")
    if not use_daily_close and live_regular_timestamp:
        try:
            trade_time = datetime.fromisoformat(live_regular_timestamp.replace("Z", "+00:00")).astimezone(
                ZoneInfo("America/New_York")
            )
            now_et = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
            minutes = trade_time.hour * 60 + trade_time.minute
            if 15 * 60 + 55 <= minutes <= 16 * 60 + 5 and now_et >= trade_time and now_et.date() == trade_time.date():
                selected_source = "robinhood-trading MCP completed regular-session closing trade"
        except ValueError:
            pass
    result = {
        "symbol": symbol.upper(), "price": selected_price,
        "market_cap": number("market_cap"), "enterprise_value": number("enterprise_value", "enterpriseValue"),
        "shares_outstanding": number("shares_outstanding"),
        "public_float": number("public_float", "float", "float_shares", "shares_float"),
        "pe_ratio": number("pe_ratio"), "forward_pe_ratio": number("forward_pe_ratio", "forward_pe"),
        "peg_ratio": number("peg_ratio", "peg"),
        "high_52": number("high_52_weeks", "high_52"),
        "low_52": number("low_52_weeks", "low_52"),
        "updated_at": selected_timestamp,
        "source": selected_source,
    }
    if not result["price"]:
        raise RuntimeError("Robinhood MCP did not return a usable quote")
    return result
