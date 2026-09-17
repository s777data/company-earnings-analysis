#!/usr/bin/env python3
"""Call the profile-configured hosted Robinhood MCP directly.

This bridge intentionally runs under Hermes' Python environment because that
is where the profile-scoped MCP OAuth manager and compatible MCP SDK live.
It never accepts credentials on the command line.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


def _profile_config() -> Path:
    explicit = os.getenv("HERMES_PROFILE_CONFIG")
    if explicit:
        return Path(explicit).expanduser()
    home = Path(os.getenv("HERMES_PROFILE_HOME", "~/.hermes/profiles/options-wheel-agent")).expanduser()
    return home / "config.yaml"


def _load_config() -> tuple[Path, dict]:
    import yaml
    path = _profile_config()
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    server = (config.get("mcp_servers") or {}).get("robinhood-trading") or {}
    if not server.get("url") or server.get("auth") != "oauth":
        raise RuntimeError("profile robinhood-trading MCP must be configured as hosted OAuth")
    return path, server


def _decode(result):
    if getattr(result, "isError", getattr(result, "is_error", False)):
        raise RuntimeError("profile Robinhood MCP returned an error")
    structured = getattr(result, "structuredContent", getattr(result, "structured_content", None))
    if structured is not None:
        return structured
    content = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            try:
                content.append(json.loads(text))
            except json.JSONDecodeError:
                content.append(text)
    return content[0] if len(content) == 1 else content


async def _main(tool: str, arguments: dict):
    config_path, server = _load_config()
    # HermesTokenStorage derives its cache from HERMES_HOME.
    os.environ["HERMES_HOME"] = str(config_path.parent)
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from tools.mcp_oauth_manager import get_manager
    import httpx

    url = server["url"]
    auth = get_manager().get_or_build_provider("robinhood-trading", url, server.get("oauth"))
    headers = dict(server.get("headers") or {})
    headers.setdefault("mcp-protocol-version", "2025-03-26")
    timeout = float(server.get("connect_timeout", 60))
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout, read=float(server.get("timeout", 300))),
        verify=server.get("ssl_verify", True),
        headers=headers,
        auth=auth,
    ) as client:
        async with streamable_http_client(url, http_client=client) as (read, write, _session_id):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout)
                return _decode(await session.call_tool(tool, arguments))


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: profile_robinhood_mcp_bridge.py TOOL JSON_ARGUMENTS", file=sys.stderr)
        return 2
    try:
        result = asyncio.run(_main(sys.argv[1], json.loads(sys.argv[2])))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"profile Robinhood MCP bridge failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
