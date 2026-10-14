"""The Lily MCP integration.

Exposes a few simple Home Assistant tools to a Xiaozhi agent (e.g. Lily Box)
through the agent's MCP endpoint.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ENDPOINT, CONF_ENTITIES
from .server import LilyMcpServer


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to the endpoint; reconnects run in the background forever."""
    cfg = {**entry.data, **entry.options}
    server = LilyMcpServer(
        hass, entry, cfg[CONF_ENDPOINT], list(cfg.get(CONF_ENTITIES) or [])
    )
    entry.runtime_data = server
    server.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Options changed - reload so Xiaozhi gets the new tool list on reconnect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry. The background task is cancelled by HA."""
    return True
