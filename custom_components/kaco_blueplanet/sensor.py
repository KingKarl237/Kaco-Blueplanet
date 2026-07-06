from __future__ import annotations

import logging
import numbers
from datetime import datetime, timedelta, timezone

import aiohttp
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Inverter limit with a small headroom for brief measurement jitter.
MAX_INVERTER_POWER_KW = 12.0
# Total Energy is reported in 0.1 kWh steps, so allow at least one step.
MIN_ALLOWED_DELTA_KWH = 0.1
# Floating-point tolerance so 0.1-step deltas are not rejected due to rounding.
DELTA_TOLERANCE_KWH = 0.001

INVERTER_DEFINITIONS = [
    # name, JSON key, unit, device_class, state_class, transform
    ("Power AC", "pac", "W", "power", "measurement", lambda v: v),
    ("Day Energy", "etd", "kWh", "energy", "total_increasing", lambda v: int(v) / 10),
    ("Total Energy", "eto", "kWh", "energy", "total_increasing", lambda v: int(v) / 10),
    ("WR Hours", "hto", "h", None, "measurement", lambda v: v),
    (
        "Voltage S1",
        "vpv",
        "V",
        "voltage",
        "measurement",
        lambda v: float(v[0]) / 10 if isinstance(v, list) else float(v) / 10,
    ),
    (
        "Voltage S2",
        "vpv",
        "V",
        "voltage",
        "measurement",
        lambda v: float(v[1]) / 10 if isinstance(v, list) else float(v) / 10,
    ),
    (
        "Current S1",
        "ipv",
        "A",
        "current",
        "measurement",
        lambda v: float(v[0]) / 100 if isinstance(v, list) else float(v) / 100,
    ),
    (
        "Current S2",
        "ipv",
        "A",
        "current",
        "measurement",
        lambda v: float(v[1]) / 100 if isinstance(v, list) else float(v) / 100,
    ),
    (
        "AC Voltage L1",
        "vac",
        "V",
        "voltage",
        "measurement",
        lambda v: float(v[0]) / 10 if isinstance(v, list) else float(v) / 10,
    ),
    (
        "AC Voltage L2",
        "vac",
        "V",
        "voltage",
        "measurement",
        lambda v: float(v[1]) / 10 if isinstance(v, list) else float(v) / 10,
    ),
    (
        "AC Voltage L3",
        "vac",
        "V",
        "voltage",
        "measurement",
        lambda v: float(v[2]) / 10 if isinstance(v, list) else float(v) / 10,
    ),
    (
        "AC Current L1",
        "iac",
        "A",
        "current",
        "measurement",
        lambda v: float(v[0]) / 10 if isinstance(v, list) else float(v) / 10,
    ),
    (
        "AC Current L2",
        "iac",
        "A",
        "current",
        "measurement",
        lambda v: float(v[1]) / 10 if isinstance(v, list) else float(v) / 10,
    ),
    (
        "AC Current L3",
        "iac",
        "A",
        "current",
        "measurement",
        lambda v: float(v[2]) / 10 if isinstance(v, list) else float(v) / 10,
    ),
    ("WR Temp", "tmp", "°C", "temperature", "measurement", lambda v: int(v) / 10),
    ("Power Factor", "pf", None, None, "measurement", lambda v: int(v) / 100),
    ("WR Error", "err", None, None, "measurement", lambda v: v),
    # Virtuelle Sensoren
    (
        "String 1 Power",
        None,
        "W",
        "power",
        "measurement",
        lambda data: (float(data["vpv"][0]) / 10) * (float(data["ipv"][0]) / 100),
    ),
    (
        "String 2 Power",
        None,
        "W",
        "power",
        "measurement",
        lambda data: (float(data["vpv"][1]) / 10) * (float(data["ipv"][1]) / 100),
    ),
    (
        "Last updated",
        None,
        None,
        "timestamp",
        None,
        lambda data: data.get("last_updated"),
    ),
]

METER_DEFINITIONS = [
    ("Meter Power AC", "pac", "W", "power", "measurement", lambda v: -v),
    (
        "Meter Energy In Today",
        "itd",
        "kWh",
        "energy",
        "total_increasing",
        lambda v: int(v) / 100,
    ),
    (
        "Meter Energy Out Today",
        "otd",
        "kWh",
        "energy",
        "total_increasing",
        lambda v: int(v) / 100,
    ),
    (
        "Meter Energy In",
        "iet",
        "kWh",
        "energy",
        "total_increasing",
        lambda v: int(v) / 10,
    ),
    (
        "Meter Energy Out",
        "oet",
        "kWh",
        "energy",
        "total_increasing",
        lambda v: int(v) / 10,
    ),
    ("Meter Mode", "mod", None, None, None, lambda v: v),
    ("Meter Enabled", "enb", None, None, None, lambda v: bool(v)),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for name, key, unit, device_class, state_class, transform in INVERTER_DEFINITIONS:
        entities.append(
            KacoSensor(
                coordinator,
                definition=(name, key, unit, device_class, state_class, transform),
                block="inverter",
            )
        )

    for name, key, unit, device_class, state_class, transform in METER_DEFINITIONS:
        entities.append(
            KacoSensor(
                coordinator,
                definition=(name, key, unit, device_class, state_class, transform),
                block="meter",
            )
        )

    async_add_entities(entities, True)


class KacoCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, host, serial, interval):
        _LOGGER.info(f"Using scan interval: {interval} seconds")
        self.host = host
        self.serial = serial
        self.last_successful_update = None
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

            self.last_successful_update = datetime.now(timezone.utc)

            # beide Ergebnisse zusammenführen
            return {"inverter": inverter_data, "meter": meter_data}

        except Exception as err:
            if self.data is not None:
                _LOGGER.warning(f"Error fetching data, keeping last state: {err}")
                return self.data  # alte Werte behalten
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def _fetch_inverter_data(self):
        url = f"http://{self.host}:8484/getdevdata.cgi?device=2&sn={self.serial}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                resp.raise_for_status()
                text = await resp.text()

                if not text.strip():
                    raise UpdateFailed("Empty response from inverter")

                try:
                    return await resp.json()
                except Exception as err:
                    snippet = text[:200].replace("\n", "")
                    raise UpdateFailed(
                        f"Invalid JSON from inverter: {err}. Response starts with: {snippet}"
                    )

    async def _fetch_meter_data(self):
        url = f"http://{self.host}:8484/getdevdata.cgi?device=3&sn={self.serial}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                resp.raise_for_status()
                text = await resp.text()

                if not text.strip():
                    raise UpdateFailed("Empty response from meter")

                try:
                    return await resp.json()
                except Exception as err:
                    snippet = text[:200].replace("\n", "")
                    raise UpdateFailed(
                        f"Invalid JSON from meter: {err}. Response starts with: {snippet}"
                    )


class KacoSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: KacoCoordinator, definition, block="inverter"):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._name = definition[0]
        self._json_key = definition[1]
        self._unit = definition[2]
        self._device_class = definition[3]
        self._state_class = definition[4]
        self._transform = definition[5]
        self._block = block
        self._last_valid_total: float | None = None
        self._last_valid_total_at: datetime | None = None

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

        if self._json_key is None and self._name == "Last updated":
            return self.coordinator.last_successful_update

        if self._json_key is None:
            # Virtueller Sensor: ganze Daten an Transform übergeben
            return self._transform(self.coordinator.data[self._block])
        else:
            value = self.coordinator.data[self._block].get(self._json_key)
            if value is None:
                return None
            transformed = self._transform(value)
            if (
                self._state_class == "total_increasing"
                and self._block == "inverter"
                and self._json_key == "eto"
            ):
                return self._plausible_total_increasing(transformed)
            return transformed

    def _plausible_total_increasing(self, value):
        """Keep cumulative energy sensors monotonic and ignore implausible spikes."""
        if not isinstance(value, numbers.Real):
            return value

        now = datetime.now(timezone.utc)
        current = float(value)
        previous = self._last_valid_total
        if previous is None:
            self._last_valid_total = current
            self._last_valid_total_at = now
            return current

        # total_increasing must never go backwards (outside tiny rounding noise)
        if current + 0.001 < previous:
            _LOGGER.warning(
                "Ignoring decreasing value for %s: new=%s old=%s",
                self.name,
                current,
                previous,
            )
            return previous

        delta = current - previous
        interval = self.coordinator.update_interval.total_seconds()
        elapsed_seconds = interval
        if self._last_valid_total_at is not None:
            elapsed_seconds = max(
                (now - self._last_valid_total_at).total_seconds(), interval
            )
        max_delta_kwh = max(
            MIN_ALLOWED_DELTA_KWH,
            (elapsed_seconds / 3600.0) * MAX_INVERTER_POWER_KW,
        )

        if delta > max_delta_kwh + DELTA_TOLERANCE_KWH:
            _LOGGER.warning(
                "Ignoring implausible jump for %s: delta=%s kWh exceeds max=%s kWh over %s s",
                self.name,
                round(delta, 4),
                round(max_delta_kwh, 4),
                int(elapsed_seconds),
            )
            return previous

        self._last_valid_total = current
        self._last_valid_total_at = now
        return current

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
