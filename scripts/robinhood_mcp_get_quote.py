#!/usr/bin/env python3
"""Read-only Robinhood MCP client. No unofficial API and no invented fallback data."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _server_parameters() -> StdioServerParameters:
    config_path = Path(os.getenv("HERMES_CONFIG", "~/.hermes/config.yaml")).expanduser()
    config = yaml.safe_load(config_path.read_text())
    server = config.get("mcp_servers", {}).get("robinhood-trading")
    if not server:
        raise RuntimeError("robinhood-trading MCP is not configured")
    env = os.environ.copy()
    for key, value in (server.get("env") or {}).items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            resolved = os.getenv(value[2:-1])
            if resolved is not None: env[key] = resolved
        else: env[key] = str(value)
    return StdioServerParameters(command=server["command"], args=server.get("args", []), env=env)


def _decode(result: Any) -> Any:
    if getattr(result, "isError", getattr(result, "is_error", False)):
        raise RuntimeError("Robinhood MCP returned an error")
    structured = getattr(result, "structuredContent", getattr(result, "structured_content", None))
    if structured is not None: return structured
    texts = [getattr(item, "text", "") for item in getattr(result, "content", []) if getattr(item, "text", None)]
    if not texts: return None
    text = "\n".join(texts)
    if text.lower().startswith("error executing tool"):
        raise RuntimeError(text.splitlines()[0])
    try: return json.loads(text)
    except json.JSONDecodeError:
        import ast
        try: return ast.literal_eval(text)
        except (ValueError, SyntaxError): return {"text": text}


async def _call(tool: str, arguments: dict[str, Any]) -> Any:
    params = _server_parameters()
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            return _decode(await session.call_tool(tool, arguments))


def _first_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, list): return data[0] if data and isinstance(data[0], dict) else {}
    if isinstance(data, dict):
        for key in ("result", "quote", "data"):
            if isinstance(data.get(key), dict): return data[key]
        return data
    return {}


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
    account = _first_dict(asyncio.run(_call("get_account_info", {})))
    actual = str(account.get("account_number") or account.get("account") or "")
    if actual != str(expected):
        raise RuntimeError("Robinhood MCP account does not match the authorized account")
    quote = _first_dict(asyncio.run(_call("get_quote", {"symbol": symbol.upper()})))
    fundamentals = _first_dict(asyncio.run(_call("get_fundamentals", {"symbol": symbol.upper()})))
    regular_close_price = None
    regular_close_timestamp = None
    try:
        historicals = asyncio.run(_call("get_historicals", {
            "symbol": symbol.upper(), "interval": "day", "span": "month",
        }))
        if isinstance(historicals, dict):
            historicals = historicals.get("result") or historicals.get("data") or []
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
