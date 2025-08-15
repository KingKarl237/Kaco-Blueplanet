from __future__ import annotations
import logging
import aiohttp
import async_timeout
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_HOST, CONF_SERIAL, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

INVERTER_DEFINITIONS = [
    # name, JSON key, unit, device_class, state_class, transform
    ("Power AC", "pac", "W", "power", "measurement", lambda v: v),
    ("Day Energy", "etd", "kWh", "energy", "total_increasing", lambda v: int(v)/10),
    ("Total Energy", "eto", "kWh", "energy", "total_increasing", lambda v: int(v)/10),
    ("WR Hours", "hto", "h", None, "measurement", lambda v: v),
    ("Voltage S1", "vpv", "V", "voltage", "measurement", lambda v: float(v[0])/10 if isinstance(v, list) else float(v)/10),
    ("Voltage S2", "vpv", "V", "voltage", "measurement", lambda v: float(v[1])/10 if isinstance(v, list) else float(v)/10),
    ("Current S1", "ipv", "A", "current", "measurement", lambda v: float(v[0])/100 if isinstance(v, list) else float(v)/100),
    ("Current S2", "ipv", "A", "current", "measurement", lambda v: float(v[1])/100 if isinstance(v, list) else float(v)/100),
    ("AC Voltage L1", "vac", "V", "voltage", "measurement", lambda v: float(v[0])/10 if isinstance(v, list) else float(v)/10),
    ("AC Voltage L2", "vac", "V", "voltage", "measurement", lambda v: float(v[1])/10 if isinstance(v, list) else float(v)/10),
    ("AC Voltage L3", "vac", "V", "voltage", "measurement", lambda v: float(v[2])/10 if isinstance(v, list) else float(v)/10),
    ("AC Current L1", "iac", "A", "current", "measurement", lambda v: float(v[0])/10 if isinstance(v, list) else float(v)/10),
    ("AC Current L2", "iac", "A", "current", "measurement", lambda v: float(v[1])/10 if isinstance(v, list) else float(v)/10),
    ("AC Current L3", "iac", "A", "current", "measurement", lambda v: float(v[2])/10 if isinstance(v, list) else float(v)/10),
    ("WR Temp", "tmp", "°C", "temperature", "measurement", lambda v: int(v)/10),
    ("Power Factor", "pf", None, None, "measurement", lambda v: int(v)/100),
    ("WR Error", "err", None, None, "measurement", lambda v: v),
    # Virtuelle Sensoren
    ("String 1 Power", None, "W", "power", "measurement", lambda data: (float(data["vpv"][0])/10) * (float(data["ipv"][0])/100)),
    ("String 2 Power", None, "W", "power", "measurement", lambda data: (float(data["vpv"][1])/10) * (float(data["ipv"][1])/100)),
]

METER_DEFINITIONS = [
    ("Meter Power AC", "pac", "W", "power", "measurement", lambda v: -v),
    ("Meter Energy In Today", "itd", "kWh", "energy", "total_increasing", lambda v: int(v)/10),
    ("Meter Energy Out Today", "otd", "kWh", "energy", "total_increasing", lambda v: int(v)/10),
    ("Meter Energy In", "iet", "kWh", "energy", "total_increasing", lambda v: int(v)/10),
    ("Meter Energy Out", "oet", "kWh", "energy", "total_increasing", lambda v: int(v)/10),
    ("Meter Mode", "mod", None, None, None, lambda v: v),
    ("Meter Enabled", "enb", None, None, None, lambda v: bool(v)),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    host = entry.data[CONF_HOST]
    serial = entry.data[CONF_SERIAL]
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = KacoCoordinator(hass, host, serial, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for name, key, unit, device_class, state_class, transform in INVERTER_DEFINITIONS:
        entities.append(KacoSensor(coordinator, definition=(name, key, unit, device_class, state_class, transform), block="inverter"))

    for name, key, unit, device_class, state_class, transform in METER_DEFINITIONS:
        entities.append(KacoSensor(coordinator, definition=(name, key, unit, device_class, state_class, transform), block="meter"))

    async_add_entities(entities, True)


class KacoCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, host, serial, interval):
        self.host = host
        self.serial = serial
        super().__init__(
            hass,
            _LOGGER,
            name=f"Kaco Blueplanet {serial}",
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self):
        """Fetch data from Kaco inverter."""
        try:
            # erster Call
            inverter_data = await self._fetch_inverter_data()

            # zweiter Call
            meter_data = await self._fetch_meter_data()

            # beide Ergebnisse zusammenführen
            return {
                "inverter": inverter_data,
                "meter": meter_data
            }

        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def _fetch_inverter_data(self):
        url = f"http://{self.host}:8484/getdevdata.cgi?device=2&sn={self.serial}"  # Pfad anpassen
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def _fetch_meter_data(self):
        url = f"http://{self.host}:8484/getdevdata.cgi?device=3&sn={self.serial}"  # Pfad anpassen
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                resp.raise_for_status()
                return await resp.json()

class KacoSensor(SensorEntity):
    def __init__(self, coordinator: KacoCoordinator, definition, block="inverter"):
        self.coordinator = coordinator
        self._name = definition[0]
        self._json_key = definition[1]
        self._unit = definition[2]
        self._device_class = definition[3]
        self._state_class = definition[4]
        self._transform = definition[5]
        self._block = block

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial)},
            name=f"Kaco Blueplanet {coordinator.serial}",
            manufacturer="Kaco",
            model="Blueplanet",
        )

    @property
    def name(self):
        return f"Kaco {self._name}"

    @property
    def native_unit_of_measurement(self):
        return self._unit

    @property
    def device_class(self):
        return self._device_class

    @property
    def state_class(self):
        return self._state_class

    @property
    def native_value(self):
        if self._json_key is None:
            # Virtueller Sensor: ganze Daten an Transform übergeben
            return self._transform(self.coordinator.data[self._block])
        else:
            value = self.coordinator.data[self._block].get(self._json_key)
            if value is None:
                return None
            return self._transform(value)

    async def async_update(self):
        await self.coordinator.async_request_refresh()

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this sensor."""
        if self._json_key is None:
            return f"{self.coordinator.serial}_{self._block}_{self._name}"
        # Wenn der Sensor aus einer Liste kommt, füge Index/Phase an
        if self._json_key in ["ipv", "vpv", "vac", "iac"]:
            # letzten Teil des Namens nutzen (S1, S2, L1, L2, L3)
            suffix = self._name.split()[-1].lower()
            return f"{self.coordinator.serial}_{self._block}_{self._json_key}_{suffix}"
        # sonst normale ID
        return f"{self.coordinator.serial}_{self._block}_{self._json_key}"

        
