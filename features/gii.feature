Feature: Gesetze im Internet als Go Library und CLI nutzen
  Andere Projekte sollen Gesetzestexte aus dem data-Branch stichtagsbezogen abrufen koennen.

  Scenario: Gesetzestext zu einem historischen Datum abrufen
    Given ein data-Branch enthaelt zwei Versionen des BGB
    When ich den Wortlaut des BGB zum 2024-01-15 abrufe
    Then erhalte ich die alte Fassung

  Scenario: Ohne Datum wird heute verwendet
    Given heute ist der 2024-02-15
    When ich den Wortlaut des BGB ohne Datum abrufe
    Then erhalte ich die am Stichtag aktuelle Fassung

  Scenario: CLI aktualisiert den Cache und gibt den Wortlaut aus
    Given ein leerer lokaler Cache
    When ich `gii text BGB --date 2024-02-15` ausfuehre
    Then wird der data-Branch geklont oder aktualisiert
    And der Wortlaut wird auf stdout geschrieben

  Scenario: CLI bootstrapped ein projekt-lokales Datenrepo
    Given ein Projekt will den Datencheckout unter .gii-data halten
    When ich `gii update --repo-dir .gii-data` ausfuehre
    Then wird dort ein Git-Repo mit data-Branch geklont oder aktualisiert
    And spaetere Aufrufe koennen `--repo-dir .gii-data --no-update` nutzen

  Scenario: MCP-Server liefert Gesetzestext und Discovery offline
    Given ein zuvor mit `gii update --repo-dir .gii-data` aktualisierter Datencheckout
    When ich `gii mcp --repo-dir .gii-data` starte
    Then kann ein MCP-Client `law_text` fuer BGB zum Stichtag aufrufen
    And `norm_text` liefert token-sparsam nur eine einzelne Norm wie § 280 BGB
    And `list_laws` und `search_laws` finden das BGB in den lokalen Metadaten

  Scenario: MCP-Read-Tools aktualisieren nicht implizit
    Given noch kein lokaler Datencheckout existiert
    When ein MCP-Client `law_text` oder `list_laws` aufruft
    Then wird ein lokaler-cache-fehlt-Fehler gemeldet
    And erst `gii update` per Cron oder das Tool `update_cache` aktualisiert den Checkout
