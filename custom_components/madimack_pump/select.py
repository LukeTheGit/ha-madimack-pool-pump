"""Select platform for Madimack Pool Pump integration.

Exposes the operating-mode enum (dpId 103) as a writable select entity.
Probe confirmed the cloud accepts native ``int`` values (0 = Manual Inverter,
1 = Backwash). See DATAPOINT_MAP.md.

NOTE: selecting ``Backwash`` will start a real backwash cycle on the pump for
the duration set by the ``Backwash Duration`` number entity (dpId 104). Treat
this as a deliberate user action.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo

from .api import FairlandApiClientCommunicationError, FairlandApiClientError
from .const import DOMAIN, LOGGER, PUMP_CATEGORY_CODE
from .entity import FairlandEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import FairlandDataUpdateCoordinator
    from .data import FairlandConfigEntry


MODE_DP_ID = "103"

# Server-side enum int → user-facing label.
MODE_INT_TO_LABEL: dict[int, str] = {
    0: "Manual Inverter",
    1: "Backwash",
}
MODE_LABEL_TO_INT: dict[str, int] = {v: k for k, v in MODE_INT_TO_LABEL.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FairlandConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Madimack pump mode select."""
    LOGGER.debug("Setting up Madimack pump select platform")

    entities = []
    for device_info in entry.runtime_data.coordinator.data:
        if device_info.get("categoryCode") != PUMP_CATEGORY_CODE:
            continue
        if "dps" not in device_info:
            continue
        if not any(dp.get("dpId") == MODE_DP_ID for dp in device_info["dps"]):
            continue
        entities.append(
            MadimackPumpModeSelect(
                coordinator=entry.runtime_data.coordinator,
                device_info=device_info,
            )
        )
    async_add_entities(entities, True)


class MadimackPumpModeSelect(FairlandEntity, SelectEntity):
    """Operating mode select for the Madimack pump (dpId 103)."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:tune"

    def __init__(
        self,
        coordinator: FairlandDataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)

        self._device_info = device_info
        self._device_id = device_info["id"]

        self._attr_name = "Mode"
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_mode"
        self._attr_options = list(MODE_INT_TO_LABEL.values())

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device_info["deviceName"],
            manufacturer="Madimack",
            model=device_info.get("deviceName", "Unknown"),
            sw_version=device_info.get("version", "Unknown"),
        )

        self._update_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    def _update_state(self) -> None:
        """Update current option from device data."""
        if "dps" not in self._device_info:
            return
        for dp in self._device_info["dps"]:
            if dp["dpId"] == MODE_DP_ID:
                raw = dp.get("dpValue")
                try:
                    self._attr_current_option = MODE_INT_TO_LABEL.get(int(raw))
                except (TypeError, ValueError):
                    self._attr_current_option = None
                self._attr_available = self._attr_current_option is not None
                return
        self._attr_available = False

    async def async_select_option(self, option: str) -> None:
        """Write a new mode to the pump."""
        if option not in MODE_LABEL_TO_INT:
            LOGGER.error("Refusing to set unknown mode option: %r", option)
            return
        target_int = MODE_LABEL_TO_INT[option]
        try:
            await self.coordinator.config_entry.runtime_data.client.set_device_status(
                self._device_id,
                MODE_DP_ID,
                target_int,
            )
            self._attr_current_option = option
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except (FairlandApiClientCommunicationError, FairlandApiClientError) as ex:
            LOGGER.error("Error setting mode: %s", ex)

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
