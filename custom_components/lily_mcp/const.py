"""Constants for the Lily MCP integration."""

DOMAIN = "lily_mcp"

CONF_ENDPOINT = "endpoint"
CONF_ENTITIES = "entities"

# Domains offered in the entity picker. Sensors are read-only: get_state and
# list_devices see them, turn_on / turn_off refuse them.
SUPPORTED_DOMAINS = [
    "light",
    "switch",
    "fan",
    "climate",
    "media_player",
    "vacuum",
    "cover",
    "input_boolean",
    "scene",
    "script",
    "button",
    "sensor",
    "binary_sensor",
]
READ_ONLY_DOMAINS = {"sensor", "binary_sensor"}

SERVER_NAME = "lily-mcp"
SERVER_VERSION = "1.0.0"
# Used when the client does not say which MCP revision it speaks.
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

# Reconnect backoff after the endpoint drops or refuses us, in seconds.
RECONNECT_MIN = 5
RECONNECT_MAX = 300
# aiohttp sends a ping this often and drops the socket if no pong comes back,
# which is what turns a silently dead connection into a reconnect.
HEARTBEAT = 30
