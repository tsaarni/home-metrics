# Metrics scraper for home automation

⚠️ Note: This project is meant for personal use, and is not guaranteed to work for anyone else.

## Description

This project scrapes data from various sources and stores it in [VictoriaMetrics](https://victoriametrics.com/) time series database.
The data is then used to generate graphs.

Supported sources:

- [Shelly 3EM](https://kb.shelly.cloud/knowledge-base/shelly-3em) and [Shelly Plus 1PM](https://kb.shelly.cloud/knowledge-base/shelly-plus-1pm) for energy consumption data.
- [go-e Gemini Charger](https://go-e.com/en/products/go-e-charger-gemini) for car charging data.
- [Skoda Connect](https://www.skoda-connect.com/) for car odometer, battery charge percentage and esimated range data.
- [spot-hinta.fi](https://spot-hinta.fi/) for electricity price.
- Zigbee and Z-Wave sensors via MQTT broker for temperature and humidity data, among others, using [Z-Wave JS UI](https://github.com/zwave-js/zwave-js-ui) and [Zigbee2MQTT](https://github.com/Koenkk/zigbee2mqtt).
- [Melcloud](https://www.melcloud.com/) for heat pump data.

## Development

Install dependencies with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Execute the application:

```bash
python3 app/main.py --config config.yaml
```

Run the test web server to see the metrics being pushed to it in Prometheus exposition format:

```bash
python3 tests/httpserver.py
```

Build the container image:

```bash
docker build -t quay.io/tsaarni/home-metrics:latest .
```

The documentation for used APIs is available at following links:

- [Shelly 1st gen REST API](https://shelly-api-docs.shelly.cloud/gen1/#shelly-family-overview) for Shelly 3EM [status](https://shelly-api-docs.shelly.cloud/gen1/#shelly-3em-status).
- [Shelly 2nd gen JSON RPC API](https://shelly-api-docs.shelly.cloud/gen2/) for Shelly Plus 1PM [status](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch#status).
- [go-e charger REST API](https://github.com/goecharger/go-eCharger-API-v2/blob/main/introduction-en.md)
- [skodaconnect](https://github.com/skodaconnect/skodaconnect) project has reverse engineered the Skoda Connect API and created a Python library for it.
- [spot-hinta.fi REST API](https://spot-hinta.fi/) for electricity price.
- VictoriaMetrics [API for importing](https://docs.victoriametrics.com/url-examples.html#apiv1importprometheus) time series data in Prometheus exposition format.
- Specification of [Prometheus datatypes](https://github.com/prometheus/docs/blob/main/content/docs/concepts/metric_types.md) and [Prometheus exposition format](https://github.com/prometheus/docs/blob/main/content/docs/instrumenting/exposition_formats.md).
- [Z-Wave JS UI MQTT](https://zwave-js.github.io/zwave-js-ui/#/guide/mqtt) and Z-Wave [command classes](https://z-wave.me/manual/z-way/Command_Class_Reference.html#).
