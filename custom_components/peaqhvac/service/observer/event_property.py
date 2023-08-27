class EventProperty:
    def __init__(self, name, prop_type: type, hub):
        self._value = None
        self._hub = hub
        self.name = name
        self._prop_type = prop_type

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        if self._value != val:
            self._value = val
            self._hub.hass.bus.fire(f"peaqhvac.{self.name}_changed", {"new": val})