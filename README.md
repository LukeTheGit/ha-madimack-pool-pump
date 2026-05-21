# Madimack Pool Pump Integration for Home Assistant

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

This integration enables monitoring (and, eventually, control) of **Madimack Inverflow Plus** variable-speed pool pumps in Home Assistant, connecting directly to the iGarden cloud API.

Madimack pumps are rebadged Fairland units sharing the same iGarden cloud platform, so this fork of [`siedi/ha-fairland`](https://github.com/siedi/ha-fairland) reuses the upstream auth/coordinator scaffolding and replaces the heat-pump entity model with pump-appropriate data points.

## Compatibility

> **Important:** This integration only works with pumps paired through the **iGarden app** (Fairland's cloud platform). It is **not compatible** with the SmartPool app, which is Tuya-based and uses a completely different API.
>
> If your pump is paired with the SmartPool app, look into Tuya-based integrations instead (e.g. [LocalTuya](https://github.com/rospogriern/localtuya) or the built-in Tuya integration).

Tested against: Madimack Inverflow Plus 1.5hp (productCode `cj0p0sf6ax7sseec`, `categoryCode "waterPump"`).

## Status

This is an **in-progress rebuild** of the upstream heat-pump integration for pumps. Current state:

| Capability                                 | Status |
|-------------------------------------------|--------|
| iGarden cloud auth + courtyard selection   | ✅ Works (reused from upstream). |
| Read-only sensors (power W, running %, energy kWh, backwash countdown) | ✅ Phase C — wired. |
| Power on/off switch (dpId 105)             | ⏳ Phase E — pending write-payload capture. |
| Speed % setpoint (dpId 111, 30–100 %)      | ⏳ Phase F — pending write-payload capture. |
| Manual Inverter vs Backwash mode select    | ⏳ Phase G — pending write-payload capture. |
| Schedules / timers                          | ❌ Out of scope for v0.3. |

See `DEVELOPMENT_PLAN.md`, `TEST_PLAN.md`, and `DATAPOINT_MAP.md` for the full plan and discovered data points.

## Installation

### HACS (recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed.
2. HACS → Integrations → ⋮ → Custom repositories.
3. Add this repository URL with category "Integration".
4. Install "Madimack Pool Pump (iGarden)".
5. Restart Home Assistant.

### Manual

1. Copy `custom_components/madimack_pump/` into your Home Assistant `custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Settings → Devices & Services → Add Integration.
2. Search for "Madimack".
3. Enter your iGarden account credentials and country code (default `AU`).
4. Pick the courtyard the pump is registered in.

## Supported entities (current)

The pump appears as a single device with these entities:

| Entity                    | dpId | Type   | Notes |
|---------------------------|------|--------|-------|
| `sensor.…_current_power`  | 5    | W      | Live electrical draw. |
| `sensor.…_speed_setpoint` | 111  | %      | Speed % the pump is currently set to (30–100). Will become a writable `number` in Phase F. |
| `sensor.…_backwash_countdown` | 108 | min | Diagnostic; 0 outside backwash mode. |
| `sensor.…_energy_consumption` | 109 | kWh | Cumulative; raw value scaled by 1/100. |

Write entities (switch, speed, mode) will appear in subsequent releases once write payloads are confirmed.

## Energy dashboard

Once `sensor.<device>_energy_consumption` is exposed, you can add it directly to the **Energy** dashboard under *Individual devices* — it is reported as cumulative kWh (`state_class: total_increasing`), so no integration sensor is needed.

## Troubleshooting

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.madimack_pump: debug
```

## Development

Forked from `siedi/ha-fairland` (which is based on the HA integration_blueprint).

## License

MIT — see `LICENSE`.
