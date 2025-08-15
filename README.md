# Kaco-Blueplanet
A homeassistant custom integration for Kaco Blueplanet Inverter. It works by fetching a local api from the Kaco WLAN Module ```http://{ip}:8484/getdevdata.cgi?device=2&sn={serial}```

For setup the ip Adress and the serial number of the inverter is needed.

This is the really first release and should be considered as early alpha but it seem to work pretty well for me.

Tested only with a Kaco Blueplanet 10.0 NX3 M2 with an Eastron SDM 630. Should work for other inverters of the same line as well.

I think the API is dependent on the Modbus addresses. I use the default addresses, so it may not work if you have changed them.

## Installation

### HACS
The easiest way to add the component to your Home Assistant installation is
using [HACS](https://hacs.xyz). Add this GitHub repository as a [custom
repository](https://hacs.xyz/docs/faq/custom_repositories), then follow the
instructions under [Configuration](#configuration) below.

### Manual

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `kaco_blueplanet`.
4. Download _all_ the files from the `custom_components/kaco_blueplanet/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Follow the instructions under [Configuration](#configuration) below.

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/kaco_blueplanet/__init__.py
custom_components/kaco_blueplanet/config_flow.py
custom_components/kaco_blueplanet/const.py
custom_components/kaco_blueplanet/manifest.json
custom_components/kaco_blueplanet/sensor.py
.. etc
```

## Sensors

### Inverter Sensors

| Name                | Description                                               |
|---------------------|----------------------------------------------------------|
| Power AC            | Current AC power of the inverter                         |
| Day Energy          | Energy yield of the current day                          |
| Total Energy        | Total energy yield since commissioning                    |
| WR Hours            | Operating hours of the inverter                          |
| Voltage S1          | Voltage at PV string 1                                   |
| Voltage S2          | Voltage at PV string 2                                   |
| Current S1          | Current at PV string 1                                   |
| Current S2          | Current at PV string 2                                   |
| AC Voltage L1       | AC voltage phase L1                                      |
| AC Voltage L2       | AC voltage phase L2                                      |
| AC Voltage L3       | AC voltage phase L3                                      |
| AC Current L1       | AC current phase L1                                      |
| AC Current L2       | AC current phase L2                                      |
| AC Current L3       | AC current phase L3                                      |
| WR Temp             | Inverter temperature                                     |
| Power Factor        | Power factor                                             |
| WR Error            | Inverter error status                                    |
| String 1 Power      | Calculated power PV string 1                             |
| String 2 Power      | Calculated power PV string 2                             |

### Meter Sensors

| Name                    | Description                                         |
|-------------------------|-----------------------------------------------------|
| Meter Power AC          | Current AC power at the meter                       |
| Meter Energy In Today   | Energy fed in today (unknown)                                |
| Meter Energy Out Today  | Energy drawn today  (unknown)                                |
| Meter Energy In         | Total energy fed in     (unknown)                            |
| Meter Energy Out        | Total energy drawn      (unknown)                            |
| Meter Mode              | Meter operating mode (unknown)                                |
| Meter Enabled           | Status whether the meter is enabled                 |