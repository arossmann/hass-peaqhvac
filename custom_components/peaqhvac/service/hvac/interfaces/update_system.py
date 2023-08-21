from __future__ import annotations
from typing import TYPE_CHECKING
import time
from datetime import datetime

if TYPE_CHECKING:
    from custom_components.peaqhvac.service.hub.hub import Hub
    from custom_components.peaqhvac.service.hvac.interfaces.ihvac import IHvac

from homeassistant.core import HomeAssistant
from custom_components.peaqhvac.service.models.enums.hvacoperations import HvacOperations
import logging

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVALS = {
    HvacOperations.Offset: 900,
    HvacOperations.WaterBoost: 60,
    HvacOperations.VentBoost: 1800,
}


class UpdateSystem:
    def __init__(self, hass: HomeAssistant, hub: Hub, hvac:IHvac):
        self._hass = hass
        self.hub = hub
        self.hvac = hvac
        self._force_update: bool = False
        self.current_water_boost_state: int = 0
        self.current_vent_boost_state: int = 0
        self.update_list: list = []
        self.periodic_update_timers: dict = {
            HvacOperations.Offset:     0,
            HvacOperations.WaterBoost: 0,
            HvacOperations.VentBoost:  0,
        }

    async def request_periodic_updates(self) -> None:
        if self.hub.hvac.water_heater.control_module:
            await self.async_update_water()
        if self.hub.hvac.house_heater.control_module:
            await self.async_update_heat()
        await self.async_update_ventilation()
        await self.async_perform_periodic_updates()

    async def async_update_ventilation(self) -> None:
        _vent_state = int(self.hvac.house_ventilation.vent_boost)
        if _vent_state != self.current_vent_boost_state:
            if await self.async_ready_to_update(HvacOperations.VentBoost):
                self.update_list.append((HvacOperations.VentBoost, _vent_state))
                self.current_vent_boost_state = _vent_state

    async def async_update_heat(self) -> None:
        if await self._hass.async_add_executor_job(self.hvac.update_offset):
            if await self.async_ready_to_update(HvacOperations.Offset):
                self.update_list.append(
                    (HvacOperations.Offset, self.hvac.current_offset)
                )

    async def async_update_water(self) -> None:
        if self.hvac.water_heater.water_boost or self.hvac.water_heater.water_heating:
            if await self.async_ready_to_update(HvacOperations.WaterBoost):
                if self.current_water_boost_state != int(self.hvac.water_heater.water_boost):
                    self.update_list.append(
                        (
                            HvacOperations.WaterBoost,
                            int(self.hvac.water_heater.water_boost),
                        )
                    )
                    self.current_water_boost_state = int(self.hvac.water_heater.water_boost)

    async def async_perform_periodic_updates(self) -> None:
        for u in self.update_list:
            await self.async_update_system(operation=u[0], set_val=u[1])
            self.periodic_update_timers[u[0]] = time.time()
        self.update_list = []

    async def async_update_system(self, operation: HvacOperations, set_val: any = None):
        if self.hub.sensors.peaq_enabled.value:
            _value = 0
            if self.hub.sensors.average_temp_outdoors.initialized_percentage > 0.5:
                _value = await self.hvac._get_operation_value(operation, set_val)
                (
                    call_operation,
                    params,
                    domain,
                ) = self.hvac._get_operation_call_parameters(operation, _value)

                _LOGGER.debug(
                    f"Requesting to update hvac-{operation.name} with value {set_val}"
                )
                await self._hass.services.async_call(domain, call_operation, params)

    async def async_ready_to_update(self, operation) -> bool:
        match operation:
            case HvacOperations.WaterBoost | HvacOperations.VentBoost:
                return any(
                    [
                        time.time() - self.periodic_update_timers[operation]
                        > UPDATE_INTERVALS[operation],
                        self.hub.sensors.peaqev_facade.exact_threshold >= 100,
                    ]
                )
            case HvacOperations.Offset:
                if self._force_update:
                    self._force_update = False
                    return True
                return any(
                    [
                        time.time() - self.periodic_update_timers[operation]
                        > UPDATE_INTERVALS[operation],
                        datetime.now().minute == 0,
                        self.hub.sensors.peaqev_facade.exact_threshold >= 100,
                    ]
                )
            case _:
                return False