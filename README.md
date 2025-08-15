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