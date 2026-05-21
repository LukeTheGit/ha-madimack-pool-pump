"""Switch platform for Madimack Pool Pump integration.

The power switch maps to dpId 105 (bool). Implementation deferred to Phase E
until the write payload shape is captured via MITM against the iGarden app —
see DATAPOINT_MAP.md and TEST_PLAN.md §2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo

from .api import FairlandApiClientCommunicationError, FairlandApiClientError
from .const import DOMAIN, LOGGER, PUMP_CATEGORY_CODE
from .entity import FairlandEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import FairlandDataUpdateCoordinator
    from .data import FairlandConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FairlandConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Madimack pump switch platform."""
    LOGGER.debug("Setting up Madimack pump switch platform (Phase B: no entities)")
    # Phase E will populate this once dpId 105 write payload is confirmed.
    async_add_entities([], True)


class MadimackPumpSwitch(FairlandEntity, SwitchEntity):
    """Power switch for the Madimack pump (dpId 105). Wired in Phase E."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FairlandDataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the switch class."""
        super().__init__(coordinator)

        self._device_info = device_info
        self._device_id = device_info["id"]

        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_switch"
        self._attr_name = "Power"
        self._attr_icon = "mdi:power"
        self._is_on = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device_info["deviceName"],
            manufacturer="Madimack",
            model=device_info.get("deviceName", "Unknown"),
            sw_version=device_info.get("version", "Unknown"),
        )

        self._update_state()

    def _update_state(self):
        """Update state from device data."""
        if "dps" not in self._device_info:
            return
        for dp in self._device_info["dps"]:
            if dp["dpId"] == "105":
                self._is_on = bool(dp["dpValue"])
                self._attr_available = True
                return

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

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

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the pump on (Phase E: payload shape unconfirmed)."""
        try:
            await self.coordinator.config_entry.runtime_data.client.set_device_status(
                self._device_id,
                "105",
                True,
            )
            self._is_on = True
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except (FairlandApiClientCommunicationError, FairlandApiClientError) as ex:
            LOGGER.error("Error turning on switch: %s", ex)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the pump off (Phase E: payload shape unconfirmed)."""
        try:
            await self.coordinator.config_entry.runtime_data.client.set_device_status(
                self._device_id,
                "105",
                False,
            )
            self._is_on = False
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        except (FairlandApiClientCommunicationError, FairlandApiClientError) as ex:
            LOGGER.error("Error turning off switch: %s", ex)
