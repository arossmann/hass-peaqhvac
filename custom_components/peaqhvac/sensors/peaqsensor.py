from custom_components.peaqhvac.const import HEATINGDEMAND, WATERDEMAND
from custom_components.peaqhvac.sensors.sensorbase import SensorBase
from homeassistant.helpers.restore_state import RestoreEntity

class PeaqSensor(SensorBase, RestoreEntity):
    def __init__(
            self,
            hub,
            entry_id,
            name: str,
            icon: str = "mdi:thermometer"
    ):
        self._sensorname = name
        self._icon = icon
        self._attr_name = f"{hub.hubname} {name}"
        #self._attr_unit_of_measurement = '°C'
        super().__init__(hub, self._attr_name, entry_id)
        self._state = ""

    # @property
    # def unit_of_measurement(self):
    #     return self._attr_unit_of_measurement

    @property
    def state(self) -> str:
        return self._state

    @property
    def icon(self) -> str:
        return self._icon

    def update(self) -> None:
        if self._sensorname == HEATINGDEMAND:
            self._state = self._hub.hvac.heating_demand.value
        elif  self._sensorname == WATERDEMAND:
            self._state = self._hub.hvac.water_demand.value

    async def async_added_to_hass(self):
        state = await super().async_get_last_state()
        if state:
            self._state = state.state
        else:
            self._state = ""