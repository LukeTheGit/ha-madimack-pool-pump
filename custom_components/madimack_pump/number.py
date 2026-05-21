"""Number platform for Madimack Pool Pump integration."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .api import FairlandApiClientCommunicationError, FairlandApiClientError
from .const import DOMAIN, LOGGER, PUMP_CATEGORY_CODE
from .entity import FairlandEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import FairlandDataUpdateCoordinator
    from .data import FairlandConfigEntry


# Writable numeric data points. Empty until Phase F — speed setpoint (dpId 111)
# and backwash duration (dpId 104) require write-payload capture before wiring.
NUMBER_TYPES: dict[str, dict[str, Any]] = {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FairlandConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Madimack pump number controls."""
    LOGGER.debug("Setting up Madimack pump number controls")

    if not NUMBER_TYPES:
        return

    entities = []
    devices = entry.runtime_data.coordinator.data

    for device_info in devices:
        if device_info.get("categoryCode") != PUMP_CATEGORY_CODE:
            continue
        if "dps" not in device_info:
            continue

        dp_map = {item["dpId"]: item for item in device_info["dps"]}

        for dp_id, config in NUMBER_TYPES.items():
            if dp_id not in dp_map:
                continue
            if dp_map[dp_id].get("dpMode") != "rw":
                continue

            if "dpProperty" in dp_map[dp_id]:
                try:
                    prop = json.loads(dp_map[dp_id]["dpProperty"])
                    config = config.copy()
                    if "min" in prop:
                        config["min"] = float(prop["min"])
                    if "max" in prop:
                        config["max"] = float(prop["max"])
                    if "step" in prop:
                        config["step"] = float(prop["step"])
                except (json.JSONDecodeError, KeyError, ValueError) as ex:
                    LOGGER.warning(
                        "Failed to parse dpProperty for number entity: %s",
                        ex,
                    )

            entities.append(
                MadimackPumpNumber(
                    coordinator=entry.runtime_data.coordinator,
                    device_info=device_info,
                    dp_id=dp_id,
                    config=config,
                )
            )

    async_add_entities(entities, True)


class MadimackPumpNumber(FairlandEntity, NumberEntity):
    """Representation of a configurable Madimack pump parameter."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FairlandDataUpdateCoordinator,
        device_info: dict[str, Any],
        dp_id: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)

        self._device_info = device_info
        self._device_id = device_info["id"]
        self._dp_id = dp_id
        self._config = config

        self._attr_name = config["name"]
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{dp_id}_control"
        self._attr_native_unit_of_measurement = config.get("unit")
        self._attr_icon = config.get("icon")
        self._attr_entity_category = config.get("entity_category")
        self._attr_native_min_value = config["min"]
        self._attr_native_max_value = config["max"]
        self._attr_native_step = config["step"]
        self._attr_mode = config.get("mode", NumberMode.SLIDER)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device_info["deviceName"],
            manufacturer="Madimack",
            model=device_info.get("deviceName", "Unknown"),
            sw_version=device_info.get("version", "Unknown"),
        )

        self._update_value()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    def _update_value(self):
        """Update value from device data."""
        if "dps" not in self._device_info:
            return
        for dp in self._device_info["dps"]:
            if dp["dpId"] == self._dp_id:
                self._attr_native_value = dp["dpValue"]
                self._attr_available = True
                return
        self._attr_available = False

    async def async_set_native_value(self, value: float) -> None:
        """Set new value, clamped to the discovered range."""
        clamped = max(
            self._attr_native_min_value,
            min(self._attr_native_max_value, value),
        )
        if self._attr_native_step.is_integer():
            rounded_value = int(round(clamped))
        else:
            rounded_value = round(clamped, 2)

        try:
            await self.coordinator.config_entry.runtime_data.client.set_device_status(
                self._device_id,
                self._dp_id,
                rounded_value,
            )
            self._attr_native_value = rounded_value
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except (FairlandApiClientCommunicationError, FairlandApiClientError) as ex:
            LOGGER.error("Error setting value: %s", ex)

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
                self._update_value()
                self.async_write_ha_state()
                break

    async def async_update(self) -> None:
        """Update the entity."""
        await self.coordinator.async_request_refresh()
