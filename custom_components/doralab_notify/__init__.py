"""DORALAB Benachrichtigungszentrale.

Zentrale Meldungsliste mit Lesestatus, Push-Steuerung pro Meldungstyp und
Person sowie Übernahme/Übersetzung der HA-eigenen Benachrichtigungen.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DISMISS_IMPORTED,
    CONF_IMPORT_PERSISTENT,
    DOMAIN,
    MOBILE_APP_ACTION_EVENT,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    PUSH_MODES,
)
from .manager import NotificationManager
from .websocket_api import async_register_websocket_api

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SEND_SCHEMA = vol.Schema(
    {
        vol.Required("type"): cv.string,
        vol.Required("message"): cv.string,
        vol.Optional("title"): cv.string,
        vol.Optional("tag"): cv.string,
        vol.Optional("link"): cv.string,
        vol.Optional("icon"): cv.string,
        vol.Optional("push", default=True): cv.boolean,
        vol.Optional("priority"): vol.In((PRIORITY_NORMAL, PRIORITY_HIGH)),
        vol.Optional("category"): cv.string,
        vol.Optional("type_name"): cv.string,
        vol.Optional("data"): dict,
    }
)
MARK_READ_SCHEMA = vol.Schema(
    {
        vol.Optional("ids"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("all", default=False): cv.boolean,
        vol.Optional("read", default=True): cv.boolean,
    }
)
DELETE_SCHEMA = vol.Schema(
    {
        vol.Optional("ids"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("all", default=False): cv.boolean,
        vol.Optional("only_read", default=False): cv.boolean,
    }
)
SET_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): cv.string,
        vol.Optional("recipients"): vol.Any(None, vol.All(cv.ensure_list, [cv.entity_id])),
        vol.Optional("push_when"): vol.In(PUSH_MODES),
        vol.Optional("reset", default=False): cv.boolean,
    }
)


def _manager(hass: HomeAssistant) -> NotificationManager:
    manager: NotificationManager | None = hass.data.get(DOMAIN)
    if manager is None:
        raise ServiceValidationError("Die Benachrichtigungszentrale ist nicht eingerichtet")
    return manager


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Websocket-API und Services registrieren."""
    async_register_websocket_api(hass)

    async def handle_send(call: ServiceCall) -> ServiceResponse:
        d = call.data
        return await _manager(hass).async_send(
            d["type"],
            d["message"],
            title=d.get("title"),
            tag=d.get("tag"),
            link=d.get("link"),
            icon=d.get("icon"),
            push=d["push"],
            priority=d.get("priority"),
            category=d.get("category"),
            type_name=d.get("type_name"),
            data=d.get("data"),
        )

    async def handle_mark_read(call: ServiceCall) -> None:
        d = call.data
        await _manager(hass).async_mark_read(d.get("ids"), mark_all=d["all"], read=d["read"])

    async def handle_delete(call: ServiceCall) -> None:
        d = call.data
        await _manager(hass).async_delete(
            d.get("ids"), delete_all=d["all"], only_read=d["only_read"]
        )

    async def handle_set_type(call: ServiceCall) -> None:
        d = call.data
        kwargs: dict[str, Any] = {"reset": d["reset"]}
        if "recipients" in d:
            kwargs["recipients"] = d["recipients"]
        if "push_when" in d:
            kwargs["push_when"] = d["push_when"]
        _manager(hass).async_set_type(d["type"], **kwargs)

    hass.services.async_register(
        DOMAIN, "send", handle_send, schema=SEND_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(DOMAIN, "mark_read", handle_mark_read, schema=MARK_READ_SCHEMA)
    hass.services.async_register(DOMAIN, "delete", handle_delete, schema=DELETE_SCHEMA)
    hass.services.async_register(DOMAIN, "set_type", handle_set_type, schema=SET_TYPE_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = NotificationManager(hass, entry)
    await manager.async_load()
    hass.data[DOMAIN] = manager

    # Button „Gelesen“ in der Push-Meldung
    @callback
    def _on_push_action(event: Any) -> None:
        hass.async_create_task(manager.async_handle_push_action(event.data.get("action")))

    entry.async_on_unload(hass.bus.async_listen(MOBILE_APP_ACTION_EVENT, _on_push_action))

    # Persistente HA-Meldungen übernehmen und übersetzen
    if entry.options.get(CONF_IMPORT_PERSISTENT, True):
        from homeassistant.components import persistent_notification as pn

        dismiss = entry.options.get(CONF_DISMISS_IMPORTED, True)

        async def _import(notification_id: str, notification: dict[str, Any]) -> None:
            await manager.async_import_persistent(
                notification_id, notification.get("title"), notification.get("message")
            )
            if dismiss:
                pn.async_dismiss(hass, notification_id)

        @callback
        def _on_persistent(update_type: Any, notifications: dict[str, Any]) -> None:
            if update_type not in (
                pn.UpdateType.ADDED,
                pn.UpdateType.UPDATED,
                pn.UpdateType.CURRENT,
            ):
                return
            for notification_id, notification in notifications.items():
                hass.async_create_task(_import(notification_id, notification))

        entry.async_on_unload(pn.async_register_callback(hass, _on_persistent))

        # Bereits vorhandene Meldungen beim Start übernehmen. Dafür gibt es keine
        # öffentliche Schnittstelle, daher abgesichert.
        try:
            existing = dict(pn._async_get_or_create_notifications(hass))  # noqa: SLF001
        except Exception:  # noqa: BLE001
            existing = {}
        for notification_id, notification in existing.items():
            hass.async_create_task(_import(notification_id, notification))

    # Aufräumen: einmal täglich nachts und beim Start
    @callback
    def _daily_cleanup(_now: Any) -> None:
        hass.async_create_task(manager.async_cleanup())

    entry.async_on_unload(async_track_time_change(hass, _daily_cleanup, hour=3, minute=30, second=0))
    await manager.async_cleanup()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        manager: NotificationManager = hass.data.pop(DOMAIN)
        await manager.async_flush()
    return unloaded
