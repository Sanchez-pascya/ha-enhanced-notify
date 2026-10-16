"""Übersetzung übernommener HA-Meldungen ins Deutsche.

Persistente HA-Benachrichtigungen (z. B. vom Saugroboter) kommen meist auf
Englisch. ``translate_persistent`` ordnet sie einem Typ zu und formuliert sie
auf Deutsch um. Was nicht erkannt wird, landet unverändert als
``ha_system``. Die Regeln lassen sich unten einfach erweitern.
"""

from __future__ import annotations

import re
from typing import Any

_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKUP = re.compile(r"[*_`#>]+")

# Verbrauchsmaterial (Dreame): englischer Begriff -> deutscher Name
_CONSUMABLES: list[tuple[str, str]] = [
    (r"main\s*brush", "Hauptbürste"),
    (r"side\s*brush", "Seitenbürste"),
    (r"mop\s*pad|mop\s*cloth|mop", "Wischpad"),
    (r"filter", "Filter"),
    (r"sensor", "Sensoren"),
    (r"silver\s*ion", "Silberionen-Modul"),
    (r"detergent", "Reinigungsmittel"),
    (r"dust\s*bag", "Staubbeutel"),
    (r"dust\s*collection|dust\s*bin", "Staubbehälter"),
]


def clean(text: str | None) -> str:
    """Markdown-Links und -Auszeichnungen entfernen."""
    if not text:
        return ""
    text = _LINK.sub(r"\1", text)
    text = _MARKUP.sub("", text)
    return re.sub(r"\s+\n", "\n", text).strip()


def _consumable_name(text: str) -> str | None:
    lowered = text.lower()
    for pattern, name in _CONSUMABLES:
        if re.search(pattern, lowered):
            return name
    return None


def translate_persistent(
    notification_id: str, title: str | None, message: str | None
) -> dict[str, Any]:
    """Liefert ``{"type", "title", "message"}`` für eine HA-Meldung."""
    raw_title = clean(title)
    raw_message = clean(message)
    haystack = f"{notification_id} {raw_title} {raw_message}".lower()

    # --- Saugroboter ------------------------------------------------------
    if re.search(r"cleanup completed|cleaning completed|cleaning (job )?(is )?(finished|completed)", haystack):
        return {
            "type": "saugroboter_fertig",
            "title": "Reinigung abgeschlossen",
            "message": "Der Saugroboter hat die Reinigung abgeschlossen.",
        }
    if re.search(r"low water|water tank.*(empty|low)|water level", haystack):
        return {
            "type": "saugroboter_wartung",
            "title": "Wassertank fast leer",
            "message": "Der Saugroboter braucht frisches Wasser im Tank.",
        }
    if re.search(r"drain", haystack):
        return {
            "type": "saugroboter_wartung",
            "title": "Abwasser entleeren",
            "message": "Das Abwasser muss manuell entleert werden.",
        }
    if re.search(r"consumable|depleted|worn out|replace|life", haystack):
        name = _consumable_name(haystack)
        if name:
            depleted = bool(re.search(r"depleted|worn out|ended|expired", haystack))
            return {
                "type": "saugroboter_wartung",
                "title": f"{name} wechseln" if depleted else f"{name} bald verschlissen",
                "message": (
                    f"{name} ist verbraucht und sollte ersetzt werden."
                    if depleted
                    else f"Die Lebensdauer von {name} geht zur Neige."
                ),
            }

    # --- Home Assistant ---------------------------------------------------
    if re.search(r"new devices? discovered|discovered", haystack):
        return {
            "type": "ha_system",
            "title": "Neue Geräte entdeckt",
            "message": "Home Assistant hat neue Geräte gefunden. Hinzufügen unter Einstellungen → Geräte & Dienste.",
        }
    if re.search(r"re-?authenticat|reauth", haystack):
        return {
            "type": "ha_system",
            "title": "Erneute Anmeldung nötig",
            "message": "Eine Integration braucht eine erneute Anmeldung. Öffne Einstellungen → Geräte & Dienste.",
        }
    if re.search(r"invalid config|configuration (is )?invalid|check_config", haystack):
        return {
            "type": "ha_system",
            "title": "Konfigurationsfehler",
            "message": raw_message or "In der Home-Assistant-Konfiguration wurde ein Fehler gefunden.",
        }

    return {
        "type": "ha_system",
        "title": raw_title or "Home Assistant",
        "message": raw_message or raw_title or "Neue Meldung von Home Assistant.",
    }
