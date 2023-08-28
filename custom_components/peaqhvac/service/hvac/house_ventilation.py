from datetime import datetime, timedelta
import logging
from custom_components.peaqhvac.service.hvac.const import LOW_DEGREE_MINUTES, SUMMER_TEMP, NIGHT_HOURS, VERY_COLD_TEMP, \
    WAITTIMER_TIMEOUT
from peaqevcore.common.wait_timer import WaitTimer
from custom_components.peaqhvac.service.models.enums.hvac_presets import HvacPresets
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)


class HouseVentilation:
    def __init__(self, hvac):
        self._hvac = hvac
        self._wait_timer_boost = WaitTimer(timeout=WAITTIMER_TIMEOUT)
        self._current_vent_state: bool = False
        async_track_time_interval(self._hvac.hub.hass, self.check_vent_boost, timedelta(seconds=30))

    @property
    def vent_boost(self) -> bool:
        return self._current_vent_state

    async def check_vent_boost(self, caller=None) -> None:
        if self._hvac.hub.sensors.temp_trend_indoors.is_clean and self._wait_timer_boost.is_timeout():
            if self._vent_boost_warmth():
                self._vent_boost_start("Vent boosting because of warmth.")
            elif self._vent_boost_night_cooling():
                self._vent_boost_start("Vent boost night cooling")
            elif self._vent_boost_low_dm():
                self._vent_boost_start("Vent boosting because of low degree minutes.")
            else:
                self._current_vent_state = False
        else:
            self._current_vent_state = False

        if self._hvac.hvac_dm > LOW_DEGREE_MINUTES + 100 or self._hvac.hub.sensors.average_temp_outdoors.value < VERY_COLD_TEMP:
            # If HVAC degree minutes are high or outdoor temperature is very cold, stop vent boosting
            self._current_vent_state = False

    def _vent_boost_warmth(self) -> bool:
        return all(
                    [
                        self._hvac.hub.sensors.get_tempdiff() > 1,
                        self._hvac.hub.sensors.temp_trend_indoors.gradient > 0.5,
                        self._hvac.hub.sensors.temp_trend_outdoors.gradient > 0,
                        self._hvac.hub.sensors.average_temp_outdoors.value >= 0,
                        self._hvac.hub.sensors.set_temp_indoors.preset != HvacPresets.Away,
                        #not self._current_vent_state
                    ]
                )

    def _vent_boost_night_cooling(self) -> bool:
        return all(
                    [
                        self._hvac.hub.sensors.get_tempdiff_in_out() > 4,
                        self._hvac.hub.sensors.average_temp_outdoors.value >= SUMMER_TEMP,
                        datetime.now().hour in NIGHT_HOURS,
                        self._hvac.hub.sensors.set_temp_indoors.preset != HvacPresets.Away,
                        #not self._current_vent_state
                    ]
                )


    def _vent_boost_low_dm(self) -> bool:
        return all(
                    [
                        self._hvac.hvac_dm <= LOW_DEGREE_MINUTES,
                        self._hvac.hub.sensors.average_temp_outdoors.value >= VERY_COLD_TEMP,
                        #not self._current_vent_state
                    ]
                )



    def _vent_boost_start(self, msg) -> None:
        if not self._current_vent_state:
            _LOGGER.debug(msg)
            self._wait_timer_boost.update()
            self._current_vent_state = True
            self._hvac.hub.observer.broadcast("update operation")