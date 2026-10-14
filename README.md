# Lily MCP

[Tiếng Việt](README.vi.md)

A Home Assistant custom integration that lets a [Xiaozhi](https://xiaozhi.me) voice agent (for example a
Lily Box) control your home through the agent's **MCP endpoint**.

Instead of handing the agent Home Assistant's full Assist tool set, it exposes five simple tools for a
list of devices you pick:

| Tool | What it does |
|---|---|
| `list_devices` | Lists the picked devices and their current state |
| `turn_on` | Turns a device on (vacuum: start cleaning, cover: open) |
| `turn_off` | Turns a device off (vacuum: return to dock, cover: close) |
| `get_state` | Reads one device or sensor |
| `set_temperature` | Sets the target temperature of a climate device (only offered if you picked one) |

The `name` argument is an enum of your device names, so even small models pick the right one. Names are
matched without Vietnamese accents, and entity aliases are accepted too.

No pip dependencies. Home Assistant opens the WebSocket to Xiaozhi, so nothing has to be reachable from
the internet.

## Install

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/lipnguyen-ha/ha-lily-mcp`, type
   **Integration**.
2. Download **Lily MCP**, then restart Home Assistant.

Manual install: copy `custom_components/lily_mcp/` to `<config>/custom_components/lily_mcp/`.

## Set up

1. On xiaozhi.me open your agent → *Configure* → *Extensions* → *MCP Endpoint* and copy the address
   (`wss://api.xiaozhi.me/mcp/?token=...`). Keep it secret: whoever has it controls your devices.
2. *Settings → Devices & services → Add integration → Lily MCP*. Paste the endpoint and pick the devices.
3. Refresh the MCP Endpoint page on xiaozhi.me: the status turns *Online* and the tools are listed.
4. Restart the Xiaozhi device so a new conversation picks up the tools.

To change the devices or the endpoint later, use *Configure* on the integration. It reconnects with the
new tool list.

If another integration (for example *MCP Server for Xiaozhi*) is connected to the same endpoint, disable
it so the agent only sees one set of tools.

## Troubleshooting

```yaml
logger:
  logs:
    custom_components.lily_mcp: debug
```

Every tool call is logged at `info` level as `Tool call <name> <arguments>`. At `debug` level every
JSON-RPC message in and out is logged as well.

## License

MIT
