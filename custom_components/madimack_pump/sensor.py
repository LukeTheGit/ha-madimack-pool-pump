"""Sensor platform for Madimack Pool Pump integration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .const import DOMAIN, LOGGER, PUMP_CATEGORY_CODE
from .entity import FairlandEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import FairlandDataUpdateCoordinator
    from .data import FairlandConfigEntry


# Read-only data points discovered on the Madimack Inverflow Plus 1.5hp pump.
# Source: DATAPOINT_MAP.md.
SENSOR_TYPES = {
    "5": {
        "name": "Current Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:flash",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # dpId 102 ("Real-time running rate") is defined in the cloud schema but
    # never populated by this pump's firmware — even with the motor running at
    # 100 % the value comes back as null. Speed-% telemetry uses dpId 111 below.
    "111": {
        "name": "Speed Setpoint",
        "unit": PERCENTAGE,
        "icon": "mdi:speedometer",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "108": {
        "name": "Backwash Countdown",
        "unit": UnitOfTime.MINUTES,
        "icon": "mdi:timer-sand",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "109": {
        "name": "Energy Consumption",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FairlandConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Madimack pump sensors."""
    LOGGER.debug("Setting up Madimack pump sensors")

    entities = []
    devices = entry.runtime_data.coordinator.data

    for device_info in devices:
        if device_info.get("categoryCode") != PUMP_CATEGORY_CODE:
            continue
        if "dps" not in device_info:
            continue

        dp_map = {item["dpId"]: item for item in device_info["dps"]}

        for dp_id, sensor_config in SENSOR_TYPES.items():
            if dp_id not in dp_map:
                continue

            # dpProperty.scale tells us how to rescale raw integer values
            # (e.g. energy is reported as int with scale=2 → divide by 100).
            if "dpProperty" in dp_map[dp_id]:
                try:
                    prop = json.loads(dp_map[dp_id]["dpProperty"])
                    if "scale" in prop:
                        sensor_config = sensor_config.copy()
                        sensor_config["scale"] = int(prop["scale"])
                except (json.JSONDecodeError, KeyError, ValueError) as ex:
                    LOGGER.warning(
                        "Failed to parse dpProperty for dp %s: %s", dp_id, ex
                    )

            entities.append(
                MadimackPumpSensor(
                    coordinator=entry.runtime_data.coordinator,
                    device_info=device_info,
                    dp_id=dp_id,
                    sensor_config=sensor_config,
                )
            )

    async_add_entities(entities, True)


class MadimackPumpSensor(FairlandEntity, SensorEntity):
    """Representation of a Madimack pump sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FairlandDataUpdateCoordinator,
        device_info: dict[str, Any],
        dp_id: str,
        sensor_config: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._device_info = device_info
        self._device_id = device_info["id"]
        self.coordinator = coordinator

        self._dp_id = dp_id
        self._sensor_config = sensor_config
        self._scale = sensor_config.get("scale", 0)

        self._attr_name = sensor_config["name"]
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{dp_id}"
        self._attr_native_unit_of_measurement = sensor_config.get("unit")
        self._attr_icon = sensor_config.get("icon")
        self._attr_device_class = sensor_config.get("device_class")
        self._attr_state_class = sensor_config.get("state_class")
        self._attr_entity_category = sensor_config.get("entity_category")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device_info["deviceName"],
            manufacturer="Madimack",
            model=device_info.get("deviceName", "Unknown"),
            sw_version=device_info.get("version", "Unknown"),
        )

        self._update_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "dp_id": self._dp_id,
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    def _update_state(self):
        """Update state from device data."""
        if "dps" not in self._device_info:
            return

        dp_map = {item["dpId"]: item for item in self._device_info["dps"]}
        if self._dp_id not in dp_map:
            LOGGER.warning(
                "Data point %s not found in device status for device %s",
                self._dp_id,
                self._device_id,
            )
            self._attr_available = False
            return

        value = dp_map[self._dp_id]["dpValue"]
        if self._scale > 0 and value is not None:
            value = value / (10**self._scale)

        self._attr_native_value = value
        self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for device in self.coordinator.data:
            if device["id"] == self._device_id:
                self._device_info = device
                self._update_state()
                self.async_write_ha_state()
                break

    async def async_update(self) -> None:
        """Update the entity."""
        await self.coordinator.async_request_refresh()
