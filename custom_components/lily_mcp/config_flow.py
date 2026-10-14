"""Config and options flow for Lily MCP."""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_ENDPOINT, CONF_ENTITIES, DOMAIN, SUPPORTED_DOMAINS


def _schema(current: dict[str, Any], with_name: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if with_name:
        fields[vol.Required(CONF_NAME, default=current.get(CONF_NAME, "Lily Box"))] = (
            selector.TextSelector()
        )
    fields[vol.Required(CONF_ENDPOINT, default=current.get(CONF_ENDPOINT, ""))] = (
        selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )
    )
    fields[vol.Required(CONF_ENTITIES, default=current.get(CONF_ENTITIES, []))] = (
        selector.EntitySelector(
            selector.EntitySelectorConfig(domain=SUPPORTED_DOMAINS, multiple=True)
        )
    )
    return vol.Schema(fields)


def _agent_id(endpoint: str) -> str | None:
    """Agent id from the endpoint's JWT, so one agent cannot be added twice."""
    try:
        token = parse_qs(urlparse(endpoint).query)["token"][0]
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return str(claims.get("endpointId") or claims["agentId"])
    except (KeyError, IndexError, ValueError):
        return None


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    url = urlparse(user_input[CONF_ENDPOINT].strip())
    if url.scheme not in ("ws", "wss") or "token=" not in url.query:
        errors[CONF_ENDPOINT] = "invalid_endpoint"
    if not user_input.get(CONF_ENTITIES):
        errors[CONF_ENTITIES] = "no_entities"
    return errors


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    data[CONF_ENDPOINT] = data[CONF_ENDPOINT].strip()
    return data


class LilyMcpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle adding an agent from the UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                data = _normalize(user_input)
                if agent := _agent_id(data[CONF_ENDPOINT]):
                    await self.async_set_unique_id(agent)
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}, with_name=True),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return LilyMcpOptionsFlow()


class LilyMcpOptionsFlow(OptionsFlow):
    """Change the endpoint or the device list via Configure."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data=_normalize(user_input))

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or current, with_name=False),
            errors=errors,
        )
