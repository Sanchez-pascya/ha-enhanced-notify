"""Die Beispiele unter examples/ müssen gültige Automationen sein und funktionieren."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import async_mock_service
import yaml

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_integration import _setup

EXAMPLES = sorted((Path(__file__).parents[1] / "examples" / "automations").glob("*.yaml"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
async def test_example_automation_is_valid(hass: HomeAssistant, path: Path):
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("automation"), f"{path.name}: Automation wurde nicht geladen"


def test_dashboard_examples_parse():
    for path in (Path(__file__).parents[1] / "examples" / "dashboard").glob("*.yaml"):
        assert yaml.safe_load(path.read_text(encoding="utf-8")), path.name


async def test_calendar_example_reports_each_event_once(hass: HomeAssistant):
    _, manager = await _setup(hass)
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {"kalender_neue_termine_initialisiert": {}}})
    events = {
        "calendar.privat": {
            "events": [
                {"summary": "Zahnarzt", "start": "2026-10-29T08:00:00+01:00", "end": "2026-10-29T09:00:00+01:00"},
            ]
        }
    }
    async_mock_service(hass, "calendar", "get_events", response=events, supports_response="only")
    config = yaml.safe_load((Path(__file__).parents[1] / "examples" / "automations" / "kalender_neuer_termin.yaml").read_text(encoding="utf-8"))
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()

    async def run():
        await hass.services.async_call("automation", "trigger", {"entity_id": "automation.meldung_neuer_kalendertermin"}, blocking=True)
        await hass.async_block_till_done()

    await run()  # Erstlauf: still
    assert manager.items == []
    assert hass.states.get("input_boolean.kalender_neue_termine_initialisiert").state == "on"
    events["calendar.privat"]["events"].append({"summary": "Konzert", "start": "2026-11-02T20:00:00+01:00", "end": "2026-11-02T22:00:00+01:00"})
    await run()
    assert [i["title"] for i in manager.items] == ["Neuer Termin: Konzert"]
    await manager.async_delete(delete_all=True)
    await run()  # gelöscht, kommt nicht wieder
    assert manager.items == []
