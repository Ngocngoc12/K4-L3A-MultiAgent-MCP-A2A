from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .contracts import Contracts

logger = logging.getLogger(__name__)


class EvidenceGateway:
    def __init__(self, session: ClientSession, contracts: Contracts) -> None:
        self._session = session
        self._contracts = contracts

    async def list_tools(self) -> list[str]:
        response = await self._session.list_tools()
        return sorted(tool.name for tool in response.tools)

    async def call(self, tool_name: str, *, case_id: str, **arguments: str) -> dict[str, Any]:
        payload = {"case_id": case_id, **arguments}
        result = await asyncio.wait_for(
            self._session.call_tool(tool_name, arguments=payload),
            timeout=2.0
        )
        is_error = getattr(result, "isError", getattr(result, "is_error", False))
        if is_error:
            message = " ".join(
                block.text for block in result.content if getattr(block, "text", None)
            )
            raise RuntimeError(f"MCP tool {tool_name} failed: {message or 'unknown error'}")
        evidence = getattr(result, "structuredContent", None)
        if evidence is None:
            evidence = getattr(result, "structured_content", None)
        if evidence is None:
            text_blocks = [block.text for block in result.content if getattr(block, "text", None)]
            if len(text_blocks) != 1:
                raise ValueError(f"MCP tool {tool_name} did not return one evidence object")
            evidence = json.loads(text_blocks[0])
        self._contracts.validate_evidence(evidence, f"MCP tool {tool_name}")
        return evidence


class OfflineEvidenceGateway:
    """Fallback evidence gateway used when MCP server is unreachable."""

    def __init__(self, contracts: Contracts) -> None:
        self._contracts = contracts

    async def list_tools(self) -> list[str]:
        return []

    async def call(self, tool_name: str, *, case_id: str, **arguments: str) -> dict[str, Any]:
        raise RuntimeError(f"MCP server offline: tool {tool_name} unavailable")


@asynccontextmanager
async def connect_gateway(
    endpoint: str, team_api_key: str, contracts: Contracts
) -> AsyncIterator[EvidenceGateway | OfflineEvidenceGateway]:
    import asyncio
    import logging
    headers = {"Authorization": f"Bearer {team_api_key}"}
    timeout = httpx2.Timeout(300.0, connect=30.0, write=30.0, pool=30.0)

    for attempt in range(3):
        try:
            async with (
                httpx2.AsyncClient(headers=headers, timeout=timeout) as http_client,
                streamable_http_client(endpoint, http_client=http_client) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()
                yield EvidenceGateway(session, contracts)
                return
        except Exception as exc:
            logging.warning(f"MCP Gateway connection attempt {attempt + 1} failed: {exc}")
            if attempt < 2:
                await asyncio.sleep(1.0 * (attempt + 1))

    logging.warning("All MCP Gateway connection attempts failed. Using offline fallback gateway.")
    yield OfflineEvidenceGateway(contracts)
