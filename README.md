# Gesetze im Internet

Es werden die auf https://www.gesetze-im-internet.de veröffentlichten Gesetze, Rechtsverordnungen, etc. täglich archiviert. 
Das Archiv beschränkt sich auf XML-Dateien nebst Anhänge. (Die inhaltsgleichen PDF-, EPUB- und HTML-Dateien werden nicht gesichert.)

Die Daten sind im [Branch 'Data' dieses Repositories](https://github.com/QuantLaw/gesetze-im-internet/tree/data) 
abrufbar.

Unter [Releases](https://github.com/QuantLaw/gesetze-im-internet/releases) 
kann der Stand zu einem Tag ausgewählt, eingesehen und separat heruntergeladen werden.


## Nutzung

Dieses Archiv enthält die jeweils aktuellen Gesetze seit dem 10. Juni 2019 in strukturiertem Format. 
Dieser historische Datensatz eignet sich insbesondere für die maschinelle Weiterverarbeitung 
und kann beispielsweise für quantitative Analysen des Rechts genutzt werden. 
Daher wird auf eine Weiterverarbeitung der archivierten Daten an dieser Stelle verzichtet.

## Go-Library und CLI

Dieses Repository kann zusätzlich als private Go-Library und als CLI genutzt werden. Das Package `github.com/janprill/gii` liest Gesetzesfassungen aus dem Git-`data`-Branch, aktualisiert einen lokalen Cache per `git fetch` und wählt automatisch den neuesten Daten-Commit am oder vor dem gewünschten Stichtag. Wird kein Datum angegeben, wird das heutige Datum verwendet.

### Installation

Für ein privates GitHub-Modul sollte Go so konfiguriert sein, dass der Modulpfad nicht über den öffentlichen Proxy aufgelöst wird:

```sh
go env -w GOPRIVATE=github.com/janprill/*
```

Danach kann das Modul in anderen Projekten eingebunden werden:

```sh
go get github.com/janprill/gii
```

Das CLI wird so installiert:

```sh
go install github.com/janprill/gii/cmd/gii@latest
```

Bei privaten Repositories verwendet `gii` die normale Git-Authentifizierung des Systems, also z. B. SSH-Key, Git Credential Helper oder Token-Konfiguration.

### Quickstart: Library

```go
package main

import (
    "context"
    "errors"
    "fmt"
    "log"
    "time"

    "github.com/janprill/gii"
)

func main() {
    ctx := context.Background()
    client := gii.New(gii.Options{})

    date, err := time.Parse("2006-01-02", "2024-02-15")
    if err != nil {
        log.Fatal(err)
    }

    law, err := client.LawText(ctx, "BGB", date)
    if errors.Is(err, gii.ErrLawNotFound) {
        log.Fatal("Gesetz nicht gefunden")
    }
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("%s (%s)\n", law.Title, law.Revision)
    fmt.Println(law.Text)
}
```

### Public API

```go
client := gii.New(gii.Options{
    RepositoryURL: "git@github.com:janprill/gii.git", // optional; Default: https://github.com/janprill/gii.git
    CacheDir:      "/tmp/gii-cache",                  // optional; Default: OS-User-Cache-Verzeichnis
    DataBranch:    "data",                            // optional; Default: data
})
```

Wichtige Methoden:

- `client.Update(ctx)` klont oder aktualisiert den lokalen Cache.
- `client.LawText(ctx, query, date)` aktualisiert den Cache und gibt den Wortlaut zum Stichtag zurück.
- `client.LawTextToday(ctx, query)` nutzt das heutige Datum.
- `client.LawTextWithoutUpdate(ctx, query, date)` arbeitet offline mit einem bereits vorhandenen Cache.

`query` kann sein:

- die Gesetze-im-Internet-ID, z. B. `bgb`,
- die amtliche Abkürzung aus dem XML, z. B. `BGB`,
- oder der Titel aus `data/toc.xml`, z. B. `Bürgerliches Gesetzbuch`.

Der Rückgabewert `*gii.Law` enthält u. a.:

- `ID`: Gesetze-im-Internet-Verzeichnis-ID,
- `Title`: Titel aus `data/toc.xml`,
- `Date`: angefragter Stichtag,
- `Revision`: ausgewählter Git-Commit,
- `XMLFiles`: gerenderte XML-Dateien,
- `Text`: menschenlesbarer Wortlaut als Plaintext.

Typed Errors:

- `gii.ErrLawNotFound`, wenn kein passendes Gesetz gefunden wurde.
- `gii.ErrRevisionNotFound`, wenn der Datenbranch für den Stichtag noch keinen Commit enthält.

### Offline-/Batch-Nutzung

Wenn mehrere Gesetze aus demselben Datenstand gelesen werden sollen, sollte der Cache einmal aktualisiert und danach offline verwendet werden:

```go
ctx := context.Background()
client := gii.New(gii.Options{})

if err := client.Update(ctx); err != nil {
    log.Fatal(err)
}

for _, abbreviation := range []string{"BGB", "HGB", "StGB"} {
    law, err := client.LawTextWithoutUpdate(ctx, abbreviation, time.Now())
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println(law.Title, len(law.Text))
}
```

### CLI

```sh
# Cache aktualisieren
gii update

# BGB im Wortlaut zum Stichtag ausgeben
gii text BGB --date 2024-02-15

# Ohne --date wird heute verwendet
gii text "Bürgerliches Gesetzbuch"

# Lokalen Cache ohne Fetch verwenden
gii text BGB --date 2024-02-15 --no-update
```

Wichtige Flags:

- `--repo-url`: Git-Repository mit `data`-Branch; Standard ist `https://github.com/janprill/gii.git`.
- `--cache-dir`: lokaler Cache; Standard ist das OS-User-Cache-Verzeichnis.
- `--branch`: Datenbranch; Standard ist `data`.
- `--no-update`: vorhandenen Cache offline verwenden.

### Verhalten und Grenzen

- Der Stichtag bezieht sich auf Archivierungs-Commits im `data`-Branch, nicht zwingend auf das juristische Inkrafttreten einzelner Normänderungen.
- Der Wortlaut wird aus den XML-Dateien als Plaintext gerendert; Layout, PDFs, EPUBs und HTML werden nicht nachgebildet.
- Für reproduzierbare Ergebnisse kann die ausgewählte Git-Revision aus `law.Revision` protokolliert werden.


## Hintergrundinformationen

Das [Log](https://github.com/QuantLaw/gesetze-im-internet/blob/data/data/log.md) 
enthält eine Liste aller archivierten Versionen.
Ebenfalls können die Commit-Messages im Branch 'Data' genutzt werden.

Ab Mai 2020 geschieht die Archivierung grundsätzlich täglich.
Das Archiv reicht bis zum 10. Juni 2019 zurück. 
Für diesen Zeitraum stehen wöchentliche Versionen bereit.
Die Archivierung geschieht transparent mittels Docker. 
Das genutzte Skript ist in diesem Repository im Master-Branch enthalten.

### Archivierungsprozess

Die Archivierung basiert auf dem Inhaltsverzeichnis von Gesetze im Internet, das als XML-Datei bereitgestellt wird. 
(Siehe https://www.gesetze-im-internet.de/hinweise.html für nähere Informationen.)
Es werden alle genannten Gesetze heruntergeladen und entpackt. 
Sofern sich ihr Inhalt geändert hat, wird die neue Version zum Repository hinzugefügt.

In seltenen Fällen ist eine im Inhaltsverzeichnis aufgeführte Datei auf dem Server nicht verfügbar. 
Solche eine Datei wird ausgelassen und unter `data/not_found.txt` im jeweiligen Commit dokumentiert. 
Typischerweise ist die Datei leer, da dieser Fehler bei der betreffenden Archivierung nicht aufgetreten ist.

Finden die Betreiber von gesetze-im-internet.de Fehler in den Daten (beispielsweise einen Tippfehler), 
werden diese auf der Webseite nachträglich korrigiert.
Entsprechend wird bei der nächsten Archivierung die Fehlerkorrektur als neue Gesetzesversion in das Archiv übernommen.
Im Archiv wird der Fehler jedoch nicht in bereits archivierten Versionen nachträglich korrigiert. 
Daher kann von einer neuen Dateiversion nicht zwingend auf eine Änderung der Rechtslage geschlossen werden,
ohne die Änderung inhaltlich zu untersuchen.
Neben einer Fehlerkorrektur wird eine neue Version häufig durch eine Aktualisierung des `builddate` 
(ein Attribut in der XML-Datei) verursacht.
