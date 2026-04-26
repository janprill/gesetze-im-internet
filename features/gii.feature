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
