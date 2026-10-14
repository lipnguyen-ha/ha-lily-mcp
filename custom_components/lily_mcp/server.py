"""MCP server that dials out to a Xiaozhi MCP endpoint.

The roles are inverted compared to a normal MCP server: we open the WebSocket
to wss://api.xiaozhi.me/mcp/?token=..., and Xiaozhi then acts as the MCP
client over it (initialize -> tools/list -> tools/call). Each text frame is one
JSON-RPC message. Only the handful of methods Xiaozhi uses are implemented.
"""

from __future__ import annotations

import asyncio
import json
import logging
import unicodedata
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DEFAULT_PROTOCOL_VERSION,
    HEARTBEAT,
    READ_ONLY_DOMAINS,
    RECONNECT_MAX,
    RECONNECT_MIN,
    SERVER_NAME,
    SERVER_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def _fold(text: str) -> str:
    """Lowercase and strip Vietnamese accents so 'Den' matches 'Đèn'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


class LilyMcpServer:
    """One connection to one Xiaozhi agent, serving a fixed list of entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        endpoint: str,
        entity_ids: list[str],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.endpoint = endpoint
        self.entity_ids = entity_ids

    def async_start(self) -> None:
        """Run the connect loop until the entry unloads (which cancels it)."""
        self.entry.async_create_background_task(
            self.hass, self._run(), f"lily_mcp {self.entry.entry_id}"
        )

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        session = async_get_clientsession(self.hass)
        delay = RECONNECT_MIN
        while True:
            try:
                async with session.ws_connect(
                    self.endpoint, heartbeat=HEARTBEAT
                ) as ws:
                    _LOGGER.info("Connected to Xiaozhi MCP endpoint")
                    delay = RECONNECT_MIN
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            # A service call can take a while; handling it
                            # inline would stop us reading pongs and the
                            # heartbeat would drop the socket.
                            self.entry.async_create_background_task(
                                self.hass,
                                self._handle(ws, msg.data),
                                "lily_mcp request",
                            )
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
                    _LOGGER.warning(
                        "Xiaozhi MCP endpoint closed the connection (code %s)",
                        ws.close_code,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - any failure means retry
                _LOGGER.warning("Cannot reach Xiaozhi MCP endpoint: %s", err)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    async def _handle(self, ws: aiohttp.ClientWebSocketResponse, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except ValueError:
            _LOGGER.warning("Ignoring non-JSON frame: %s", raw[:200])
            return
        if not isinstance(msg, dict) or "method" not in msg:
            # Responses to requests we never send, or batches - not used.
            return

        _LOGGER.debug("<- %s", raw[:500])
        method = msg["method"]
        params = msg.get("params") or {}
        req_id = msg.get("id")

        if req_id is None:
            # Notification (notifications/initialized etc.) - no reply allowed.
            return

        try:
            result = await self._dispatch(method, params)
        except _MethodNotFound:
            reply = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        except Exception as err:  # noqa: BLE001 - always answer, never hang the client
            _LOGGER.exception("Failed to handle %s", method)
            reply = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(err)},
            }
        else:
            reply = {"jsonrpc": "2.0", "id": req_id, "result": result}

        text = json.dumps(reply, ensure_ascii=False)
        _LOGGER.debug("-> %s", text[:500])
        if not ws.closed:
            await ws.send_str(text)

    async def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return {
                "protocolVersion": params.get(
                    "protocolVersion", DEFAULT_PROTOCOL_VERSION
                ),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": self._tools()}
        if method == "tools/call":
            return await self._call_tool(
                params.get("name", ""), params.get("arguments") or {}
            )
        raise _MethodNotFound

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    def _states(self) -> list[State]:
        return [
            s for e in self.entity_ids if (s := self.hass.states.get(e)) is not None
        ]

    def _aliases(self, entity_id: str) -> list[str]:
        entry = er.async_get(self.hass).async_get(entity_id)
        # Newer cores may keep a None placeholder in aliases; skip it.
        return sorted(a for a in entry.aliases if a) if entry else []

    @staticmethod
    def _name(state: State) -> str:
        return state.attributes.get("friendly_name") or state.entity_id

    def _find(self, name: str) -> State | str:
        """Resolve a spoken name to a state, or return an error for the model."""
        want = _fold(name)
        candidates: list[tuple[State, list[str]]] = [
            (s, [_fold(self._name(s)), _fold(s.entity_id)]
             + [_fold(a) for a in self._aliases(s.entity_id)])
            for s in self._states()
        ]

        exact = [s for s, names in candidates if want in names]
        if len(exact) == 1:
            return exact[0]

        partial = [
            s for s, names in candidates if any(want in n or n in want for n in names)
        ]
        if len(partial) == 1:
            return partial[0]

        known = ", ".join(self._name(s) for s, _ in candidates)
        if partial:
            many = ", ".join(self._name(s) for s in partial)
            return f"Tên '{name}' khớp nhiều thiết bị: {many}. Hãy nói rõ hơn."
        return f"Không tìm thấy thiết bị '{name}'. Các thiết bị có: {known}."

    def _describe(self, state: State) -> str:
        text = f"{self._name(state)}: {state.state}"
        if unit := state.attributes.get("unit_of_measurement"):
            text += f" {unit}"
        if state.domain == "climate":
            extra = [
                f"{label} {value}"
                for label, key in (
                    ("nhiệt độ phòng", "current_temperature"),
                    ("đặt", "temperature"),
                )
                if (value := state.attributes.get(key)) is not None
            ]
            if extra:
                text += " (" + ", ".join(extra) + ")"
        return text

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def _tools(self) -> list[dict[str, Any]]:
        names = sorted({self._name(s) for s in self._states()})
        controllable = sorted(
            {self._name(s) for s in self._states() if s.domain not in READ_ONLY_DOMAINS}
        )
        climates = sorted(
            {self._name(s) for s in self._states() if s.domain == "climate"}
        )

        def name_arg(options: list[str]) -> dict[str, Any]:
            schema: dict[str, Any] = {
                "type": "string",
                "description": "Tên thiết bị, chọn đúng một tên trong danh sách.",
            }
            if options:
                schema["enum"] = options
            return {
                "type": "object",
                "properties": {"name": schema},
                "required": ["name"],
            }

        tools = [
            {
                "name": "list_devices",
                "description": (
                    "Liệt kê tất cả thiết bị trong nhà (Home Assistant) và trạng "
                    "thái hiện tại. Dùng khi người dùng hỏi trong nhà có gì, "
                    "cái gì đang bật, hoặc khi chưa chắc tên thiết bị."
                ),
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "turn_on",
                "description": (
                    "Bật một thiết bị trong nhà: đèn, công tắc, quạt, điều hoà, "
                    "TV, ổ cắm. Với robot hút bụi là bắt đầu dọn."
                ),
                "inputSchema": name_arg(controllable),
            },
            {
                "name": "turn_off",
                "description": (
                    "Tắt một thiết bị trong nhà. Với robot hút bụi là cho về dock."
                ),
                "inputSchema": name_arg(controllable),
            },
            {
                "name": "get_state",
                "description": (
                    "Xem trạng thái hoặc giá trị của một thiết bị hay cảm biến "
                    "(đang bật/tắt, nhiệt độ, độ ẩm...)."
                ),
                "inputSchema": name_arg(names),
            },
        ]
        if climates:
            schema = name_arg(climates)
            schema["properties"]["temperature"] = {
                "type": "number",
                "description": "Nhiệt độ muốn đặt, độ C.",
            }
            schema["required"] = ["name", "temperature"]
            tools.append(
                {
                    "name": "set_temperature",
                    "description": "Đặt nhiệt độ cho điều hoà (độ C).",
                    "inputSchema": schema,
                }
            )
        return tools

    async def _call_tool(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        _LOGGER.info("Tool call %s %s", tool, args)
        try:
            text = await self._run_tool(tool, args)
        except _ToolError as err:
            return _result(str(err), error=True)
        except HomeAssistantError as err:
            return _result(f"Home Assistant báo lỗi: {err}", error=True)
        return _result(text)

    async def _run_tool(self, tool: str, args: dict[str, Any]) -> str:
        if tool == "list_devices":
            states = self._states()
            if not states:
                return "Chưa có thiết bị nào được chọn trong Lily MCP."
            return "\n".join(self._describe(s) for s in states)

        if tool not in ("turn_on", "turn_off", "get_state", "set_temperature"):
            raise _ToolError(f"Không có công cụ '{tool}'.")

        found = self._find(str(args.get("name", "")))
        if isinstance(found, str):
            raise _ToolError(found)
        state = found

        if tool == "get_state":
            return self._describe(state)

        if tool == "set_temperature":
            if state.domain != "climate":
                raise _ToolError(f"{self._name(state)} không phải điều hoà.")
            try:
                temperature = float(args["temperature"])
            except (KeyError, TypeError, ValueError) as err:
                raise _ToolError("Thiếu hoặc sai nhiệt độ.") from err
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": state.entity_id, "temperature": temperature},
                blocking=True,
            )
            return f"Đã đặt {self._name(state)} {temperature:g}°C."

        if state.domain in READ_ONLY_DOMAINS:
            raise _ToolError(f"{self._name(state)} là cảm biến, chỉ xem được.")

        domain, service = _service_for(state.domain, tool == "turn_on")
        await self.hass.services.async_call(
            domain, service, {"entity_id": state.entity_id}, blocking=True
        )
        verb = "bật" if tool == "turn_on" else "tắt"
        # Read the state back so the model can tell the user what really
        # happened (an offline device stays 'unavailable').
        await asyncio.sleep(0.5)
        now = self.hass.states.get(state.entity_id) or state
        return f"Đã {verb} {self._name(state)}. Trạng thái hiện tại: {now.state}."


def _service_for(domain: str, on: bool) -> tuple[str, str]:
    """Map turn_on / turn_off onto what each domain actually calls it."""
    if domain == "vacuum":
        return ("vacuum", "start" if on else "return_to_base")
    if domain == "cover":
        return ("cover", "open_cover" if on else "close_cover")
    if domain == "button":
        if not on:
            raise _ToolError("Nút bấm chỉ bấm được, không tắt được.")
        return ("button", "press")
    if domain == "scene":
        if not on:
            raise _ToolError("Ngữ cảnh (scene) chỉ kích hoạt được, không tắt được.")
        return ("scene", "turn_on")
    return ("homeassistant", "turn_on" if on else "turn_off")


def _result(text: str, error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": error}


class _MethodNotFound(Exception):
    """JSON-RPC method we do not implement."""


class _ToolError(Exception):
    """A tool failure explained in words the model can read back to the user."""
