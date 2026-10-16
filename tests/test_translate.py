"""Tests der Übersetzung von HA-Meldungen."""

import pytest

from custom_components.doralab_notify.translate import clean, translate_persistent


@pytest.mark.parametrize(
    ("nid", "title", "message", "type_", "title_de"),
    [
        ("dreame_1", "Dreame Vacuum", "Cleaning completed", "saugroboter_fertig", "Reinigung abgeschlossen"),
        ("dreame_2", "Dreame Vacuum", "Main brush is depleted. Please replace it.", "saugroboter_wartung", "Hauptbürste wechseln"),
        ("dreame_3", "Dreame Vacuum", "Side brush life is low, replace soon", "saugroboter_wartung", "Seitenbürste bald verschlissen"),
        ("dreame_4", "Dreame Vacuum", "Low water warning", "saugroboter_wartung", "Wassertank fast leer"),
        ("dreame_5", "Dreame Vacuum", "Manual drainage required", "saugroboter_wartung", "Abwasser entleeren"),
        ("config_entry_discovery", "New devices discovered", "Some stuff", "ha_system", "Neue Geräte entdeckt"),
        ("x", "Something else", "A [link](https://example.com) here", "ha_system", "Something else"),
    ],
)
def test_translate(nid, title, message, type_, title_de):
    result = translate_persistent(nid, title, message)
    assert result["type"] == type_
    assert result["title"] == title_de


def test_unknown_keeps_text_and_strips_markup():
    result = translate_persistent("x", None, "**Hallo** [Welt](http://a.b)")
    assert result["title"] == "Home Assistant"
    assert result["message"] == "Hallo Welt"


def test_clean_empty():
    assert clean(None) == ""
