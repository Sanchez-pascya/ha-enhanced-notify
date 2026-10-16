# DORALAB Benachrichtigungen (`doralab_notify`)

Zentrale Benachrichtigungsliste für Home Assistant, gedacht für Wand-Tablet (Kiosk), Web und Companion App.

- **Gemeinsamer Lesestatus**: gelesen/ungelesen liegt in Home Assistant, damit ist er auf Kiosk, Web und App identisch und live synchron.
- **Katalog der Meldungstypen** (Pakete, Haustür, Wäsche, Saugroboter, Kalender, Keller-Vorrat, System). Unbekannte Typen legen sich beim ersten Auslösen selbst an.
- **Push pro Typ und Person**: Welche Personen bekommen welchen Typ als Push, und ob immer oder nur, wenn die Person nicht zuhause ist.
- **Push-Aufräumen**: Wird eine Meldung irgendwo gelesen oder gelöscht, verschwindet der Push auf den Handys. Der Button „Gelesen“ in der Push-Meldung markiert sie in der Zentrale als gelesen.
- **HA-Benachrichtigungen übernehmen**: persistente HA-Meldungen (z. B. vom Saugroboter) werden ins Deutsche übersetzt und in die Zentrale übernommen.
- Sensor `Ungelesen` (Zähler für die Glocke), Aufbewahrung per Optionen.

## Installation (HACS)

1. HACS → Integrationen → ⋮ → *Benutzerdefinierte Repositories* → `dominikramachers/ha-enhanced-notify`, Kategorie *Integration*.
2. Installieren, Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → **DORALAB Benachrichtigungen**.

## Meldung senden

```yaml
action: doralab_notify.send
data:
  type: paket_zugestellt          # Typ aus dem Katalog (oder neu: wird automatisch angelegt)
  message: "Hermes: Dein Paket wurde zugestellt"
  title: "Paket zugestellt"       # optional, Standard = Name des Typs
  tag: "paket:H1234567890"        # optional: gleicher Tag aktualisiert statt neu anzulegen
  link: /kiosk-test/pakete        # optional: öffnet beim Tippen auf den Push
  push: true                      # optional: false = nur in die Zentrale
```

Gleicher `tag` mit geändertem Text aktualisiert die vorhandene Meldung (wird wieder ungelesen, rückt nach oben, Push wird ersetzt). Gleicher Tag mit gleichem Titel und Text wird ignoriert, solange sich der Inhalt nicht ändert: Die Integration merkt sich je Tag dauerhaft den zuletzt gemeldeten Inhalt. Eine gelesene oder gelöschte Meldung taucht deshalb nicht wieder auf, auch nicht nach einem Neustart oder wenn eine Automation sie erneut sendet; erst ein geänderter Text meldet wieder (neu, ungelesen, mit Push). Meldungen ohne `tag` und übernommene HA-Meldungen sind davon ausgenommen.

### Nur einmal melden (`once`, `baseline`)

Für Ereignisse, die nicht wiederkehren sollen, z. B. neue Kalendertermine:

```yaml
action: doralab_notify.send
data:
  type: kalender_neuer_termin
  message: "PRIVAT · Do., 29.10. 08:00"
  tag: "kal:calendar.xyz:UID-123"
  once: true        # dieser Tag wird nur ein einziges Mal gemeldet, auch nach dem Löschen
  baseline: true    # optional, nur mit once: Tag nur vormerken, keine Meldung und kein Push (stiller Erstlauf)
```

Die gesehenen Tags werden dauerhaft gespeichert (bis 5000, die ältesten fallen heraus).

## Weitere Aktionen

| Aktion | Zweck |
|---|---|
| `doralab_notify.mark_read` | `ids`, `all`, `read` |
| `doralab_notify.delete` | `ids`, `tags` (löscht alle Meldungen mit diesem Tag), `all`, `only_read` |
| `doralab_notify.set_type` | `type`, `recipients` (Personen), `push_when` (`always`/`away`), `reset` |

Beim Senden löst die Integration das Ereignis `doralab_notify_created` aus (für eigene Automationen).

## Push-Empfänger

Die Handys einer Person werden über deren Geräte-Tracker (Companion App) gefunden, der Dienst heißt `notify.mobile_app_<gerätename>`. Geräte, die nie Push bekommen sollen (z. B. ein iPad), lassen sich in den Integrationsoptionen ausschließen.

Standard je Typ steht im Katalog (`catalog.py`): `default_push: all` = alle Personen, `none` = niemand. Automatisch angelegte Typen pushen anfangs nicht.

## Übersetzung der HA-Meldungen

Regeln in `translate.py`. Was nicht erkannt wird, landet unverändert als Typ `ha_system`. Die Original-Texte stehen in `data.original_title` / `data.original_message` der Meldung, damit sich Regeln anhand echter Meldungen nachschärfen lassen.

## Websocket-API (für Karten)

`doralab_notify/subscribe` (liefert Stand und jede Änderung), `mark_read`, `delete`, `set_type` (nur Admin).

## Entwicklung

```
python -m venv venv && venv/bin/pip install pytest-homeassistant-custom-component
venv/bin/pytest
```

## Oberfläche (Glocke, Liste, Admin-Karte)

Die Dateien liegen unter `frontend/doralab-notify.js` und werden als Dashboard-Ressource (Typ *Modul*) eingebunden.
Sie liefern:

- Glocke mit Zähler im Kiosk-Header (`doralab-kt-page`) und im Handy-Header (`doralab-home-header`), die sich dort automatisch einhängt
- Meldungsliste als Popup (Filter Alle / Ungelesen / Kategorie, löschen, „Alle gelesen“, „Gelesene löschen“)
- Die Standard-Glocke der HA-Seitenleiste (Web und App) öffnet diese Liste und zeigt den Zähler der Integration statt der leeren HA-Schublade
- Karte `custom:doralab-notify-admin`: Push-Empfänger und Modus je Meldungstyp, Testmeldung, Zurücksetzen auf Standard

Alles läuft über die Websocket-Befehle der Integration, der Lesestatus ist damit auf allen Geräten identisch.
