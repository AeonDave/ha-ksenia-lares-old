# Ksenia Lares pre-v4 Home Assistant integration

Custom integration for **Ksenia Lares < v4** panels (this house: `lares 128IP`) that expose an old HTTP XML web server, not a documented API.

## What it does

- **Lights** (`light.*`) — every named digital output, including shutter pulse channels.
- **Covers** (`cover.*`) — paired `TAPP SU` / `TAPP GIU` outputs as shutters (open / close / stop). Position is unknown; the panel does not report travel.
- Alarm zones / partitions are **not** implemented (not installed on this system).

Existing `light.tapp_su_*` / `light.tapp_giu_*` entities are kept so automations do not break. Prefer the new `cover.*` entities in the UI.

## Requirements

- Home Assistant 2026.9+
- Panel reachable over HTTP with Basic Auth
- XML paths like `/xml/outputs/outputsDescription128IP.xml` and `/xml/outputs/outputsStatus128IP.xml`

## Install / update (this home server)

The live custom component is a git clone:

```bash
git -C /home/aeon/docker/homeassistant/data/ha-ksenia-lares-old pull
sudo docker restart homeassistant
```

## Development

```bash
python -m pytest tests -v
```

Tests parse in-memory XML fixtures and never contact the panel.
