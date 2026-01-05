# BDSG zu GDPR Mapping - Konzept & Anwendung

Dieses Repository enthält ein Toolset, um das Bundesdatenschutzgesetz (BDSG 2018) automatisch zu analysieren und eine semantische Mapping-Datei (`rioKB_Mapping_BDSG.xml`) im LegalRuleML-Format zu erstellen. Ziel ist es, spezifische Rechtsbegriffe der DSGVO im BDSG-Text zu identifizieren und mit Deontischer Logik (Gebot, Verbot, Erlaubnis) zu verknüpfen.

## Voraussetzungen

Stellen Sie sicher, dass Python 3 installiert ist. Installieren Sie die notwendigen Abhängigkeiten:

```bash
pip install lxml beautifulsoup4 spacy spacy-lookups-data
python -m spacy download de_core_news_sm
```

## Dateistruktur

*   `data/items/bdsg_2018/BJNR209710017.xml`: Die Quelle des BDSG-Gesetzestextes (lokal vorhanden).
*   `concept_mapper.py`: Modul zur Erkennung von DSGVO-Entitäten (z.B. "Verantwortlicher", "personenbezogene Daten"). Nutzt Spacy für Lemmatisierung.
*   `deontic_classifier.py`: Modul zur Klassifizierung der deontischen Modalität eines Satzes (Verpflichtung, Verbot, Erlaubnis, Definition).
*   `bdsg_mapping_generator.py`: Das Hauptskript, das den XML-Pipeline-Prozess ausführt.
*   `rioKB_Mapping_BDSG.xml`: Die generierte Ausgabedatei.

## Anwendung

Um das Mapping zu generieren, führen Sie einfach das Hauptskript aus:

```bash
python bdsg_mapping_generator.py
```

### Funktionsweise

1.  **Parsing**: Das Skript liest die BDSG-XML-Datei und iteriert durch alle Paragraphen (`<norm>`).
2.  **Klassifizierung**: Jeder Absatz wird analysiert:
    *   **Deontik**: Enthält der Text Signalwörter wie "muss", "hat zu" (Obligation), "darf nicht" (Prohibition) oder "kann" (Permission)?
    *   **Semantik**: Werden Begriffe wie "Verantwortlicher" oder "Verarbeitung" gefunden? (Basierend auf Art. 4 DSGVO Mapping).
3.  **Generierung**: Es wird eine LegalRuleML-Regel erstellt:
    *   **IF**: Die gefundenen Entitäten (z.B. Es existiert ein Verantwortlicher).
    *   **THEN**: Die deontische Modalität gilt (z.B. Der Verantwortliche ist verpflichtet...).

### Ergebnis

Die Datei `rioKB_Mapping_BDSG.xml` enthält die strukturierten Regeln mit Verweisen auf die entsprechenden Paragraphen des BDSG.

## Anpassung

*   **Wörterbuch**: Ergänzen Sie `concept_mapper.py`, um weitere Begriffe zu erkennen.
*   **Logik**: Verfeinern Sie `deontic_classifier.py`, um komplexere Satzstrukturen besser zu erfassen.
