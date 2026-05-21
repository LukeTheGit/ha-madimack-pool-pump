"""Constants for the Madimack Pool Pump integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "madimack_pump"
DEFAULT_SCAN_INTERVAL = 30
ATTRIBUTION = "Data provided by iGarden cloud"

PUMP_CATEGORY_CODE = "waterPump"
