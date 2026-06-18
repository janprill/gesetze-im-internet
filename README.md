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

Dieses Repository kann zusätzlich als private Go-Library und als CLI genutzt werden. Wichtig ist die Trennung von **Code-Modul** und **Datenquelle**:

- Das Go-Modul liegt unter `github.com/janprill/gii` und enthält Library + CLI.
- Die Gesetzesdaten werden standardmäßig direkt aus dem öffentlichen Archiv `https://github.com/QuantLaw/gesetze-im-internet.git`, Branch `data`, gelesen.
- Ein eigener Daten-Mirror ist optional. Er ist nur nötig, wenn ihr den Datenstand intern pinnen, cachen oder unabhängig vom Upstream bereitstellen wollt.

Damit muss der `data`-Branch nicht zwingend in das private Go-Modul-Repository gespiegelt werden. Andere Projekte können die Library einbinden und ohne weitere Konfiguration loslegen. Intern klont/fetcht `gii` ein lokales Git-Repo und wählt automatisch den neuesten Daten-Commit am oder vor dem gewünschten Stichtag. Wird kein Datum angegeben, wird das heutige Datum verwendet.

### Installation

Für ein privates GitHub-Modul sollte Go so konfiguriert sein, dass der Modulpfad nicht über den öffentlichen Proxy aufgelöst wird:

```sh
go env -w GOPRIVATE=github.com/janprill/*
```

Danach kann das Modul in anderen Go-Projekten eingebunden werden:

```sh
go get github.com/janprill/gii
```

Das CLI wird so installiert:

```sh
go install github.com/janprill/gii/cmd/gii@latest
```

Bei privaten Code- oder Daten-Repositories verwendet `gii` die normale Git-Authentifizierung des Systems, also z. B. SSH-Key, Git Credential Helper oder Token-Konfiguration.

### Empfohlenes Setup

#### Einfachster Fall: Go-Projekt

Keine Daten-Konfiguration nötig. Beim ersten Zugriff klont die Library das öffentliche Datenarchiv in den OS-User-Cache:

```go
client := gii.New(gii.Options{})
law, err := client.LawText(ctx, "BGB", date)
```

#### Projekt-lokales Datenrepo für Go- oder Nicht-Go-Projekte

Wenn der Daten-Checkout sichtbar im Projekt liegen soll, kann das CLI ihn explizit anlegen/aktualisieren:

```sh
gii init --repo-dir ./.gii-data
# oder äquivalent:
gii update --repo-dir ./.gii-data
```

Danach kann der Checkout offline genutzt werden:

```sh
gii text BGB --date 2024-02-15 --repo-dir ./.gii-data --no-update
```

In Go kann derselbe Checkout genutzt werden:

```go
client := gii.New(gii.Options{RepositoryDir: ".gii-data"})
law, err := client.LawTextWithoutUpdate(ctx, "BGB", date)
```

#### Eigener Daten-Mirror

Für interne Mirrors oder einen privaten Fork des Datenbranches:

```sh
gii init --repo-dir ./.gii-data --data-repo git@github.com:deine-org/gesetze-data.git
```

```go
client := gii.New(gii.Options{
    RepositoryURL: "git@github.com:deine-org/gesetze-data.git",
    RepositoryDir: ".gii-data",
})
```

`--repo-url` bleibt als kompatibler Alias für `--data-repo` erhalten, neue Aufrufe sollten aber `--data-repo` verwenden.

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
    RepositoryURL: "https://github.com/QuantLaw/gesetze-im-internet.git", // optional; Default-Datenquelle
    CacheDir:      "/tmp/gii-cache",                                      // optional; Clone liegt unter <CacheDir>/repo
    RepositoryDir: ".gii-data",                                           // optional; direkter Clone-Pfad statt CacheDir
    DataBranch:    "data",                                                // optional; Default: data
})
```

Wichtige Methoden:

- `client.Update(ctx)` klont oder aktualisiert den lokalen Daten-Checkout.
- `client.LawText(ctx, query, date)` aktualisiert den Checkout und gibt den vollständigen Wortlaut zum Stichtag zurück.
- `client.LawNormText(ctx, query, norm, date)` aktualisiert den Checkout und gibt nur eine einzelne Norm zurück, z. B. `query="BGB"`, `norm="280"`.
- `client.LawTextToday(ctx, query)` nutzt das heutige Datum.
- `client.LawTextWithoutUpdate(ctx, query, date)` arbeitet offline mit einem bereits vorhandenen Checkout.
- `client.LawNormTextWithoutUpdate(ctx, query, norm, date)` arbeitet offline und gibt token-sparsam nur eine einzelne Norm zurück.
- `client.ListLawsWithoutUpdate(ctx, date, limit, offset)` listet Gesetze/Rechtsverordnungen offline aus `data/toc.xml`.
- `client.SearchLawsWithoutUpdate(ctx, query, date, limit, offset)` sucht offline nach ID, Titel oder exakter XML-Abkürzung.

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
- `gii.ErrNormNotFound`, wenn das Gesetz gefunden wurde, aber die angefragte Einzelnorm nicht existiert.
- `gii.ErrRevisionNotFound`, wenn der Datenbranch für den Stichtag noch keinen Commit enthält.
- `gii.ErrLocalCacheMissing`, wenn ein Offline-Aufruf ohne vorhandenen lokalen Checkout ausgeführt wird.

### Offline-/Batch-Nutzung

Wenn mehrere Gesetze aus demselben Datenstand gelesen werden sollen, sollte der Checkout einmal aktualisiert und danach offline verwendet werden:

```go
ctx := context.Background()
client := gii.New(gii.Options{RepositoryDir: ".gii-data"})

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
# Projekt-lokales Datenrepo initialisieren oder aktualisieren
gii init --repo-dir ./.gii-data

# OS-User-Cache aktualisieren
gii update

# BGB im Wortlaut zum Stichtag ausgeben
gii text BGB --date 2024-02-15

# Ohne --date wird heute verwendet
gii text "Bürgerliches Gesetzbuch"

# Lokales Projekt-Datenrepo ohne Fetch verwenden
gii text BGB --date 2024-02-15 --repo-dir ./.gii-data --no-update
```

### MCP-Server

`gii` kann als Model-Context-Protocol-Server gestartet werden. MCP-Read-Tools arbeiten bewusst **offline** und führen kein implizites `git fetch` aus. Aktualisiert den Datencheckout daher vorher explizit:

```sh
gii update --repo-dir ./.gii-data
```

Für lokale MCP-Clients ist `stdio` der Default:

```sh
gii mcp --repo-dir ./.gii-data
```

Beispiel-Konfiguration für einen MCP-Client:

```json
{
  "mcpServers": {
    "gii": {
      "command": "gii",
      "args": ["mcp", "--repo-dir", "/absolute/path/to/.gii-data"]
    }
  }
}
```

Für serviceartige Nutzung steht Streamable HTTP bereit (`--transport http`):

```sh
gii mcp --transport http --addr 127.0.0.1:8080 --repo-dir ./.gii-data
```

Für ältere MCP-Clients kann der SSE-Transport verwendet werden:

```sh
gii mcp --transport sse --addr 127.0.0.1:8080 --repo-dir ./.gii-data
```

Verfügbare MCP-Tools:

- `law_text`: Plaintext eines ganzen Gesetzes zum Stichtag; Eingaben: `query`, optional `date` (`YYYY-MM-DD`). Optional kann `norm` gesetzt werden, dann wird nur diese Einzelnorm geliefert. Ausgabe: Plaintext plus strukturierte JSON-Metadaten (`id`, `title`, `norm`, `date`, `revision`, `xml_files`, `text`).
- `norm_text`: token-sparsamer Abruf einer einzelnen Norm; Eingaben: `query`, `norm` (z. B. `280` oder `§ 280`), optional `date`.
- `list_laws`: paginierte Discovery aus dem lokalen Checkout; Eingaben: optional `date`, `limit`, `offset`.
- `search_laws`: Suche nach ID, Titel oder exakter XML-Abkürzung; Eingaben: `query`, optional `date`, `limit`, `offset`.
- `update_cache`: explizites Update des lokalen Checkouts. Für regelmäßige Aktualisierung ist ein Cronjob meist besser:

```cron
# täglich um 04:30 Uhr den lokalen gii-Datencheckout aktualisieren
30 4 * * * /usr/local/bin/gii update --repo-dir /srv/gii/.gii-data >>/var/log/gii-update.log 2>&1
```

Wichtige Flags:

- `--data-repo`: Git-Repository mit `data`-Branch; Standard ist `https://github.com/QuantLaw/gesetze-im-internet.git`.
- `--repo-url`: kompatibler Alias für `--data-repo`.
- `--cache-dir`: lokaler Cache; Clone liegt unter `<cache-dir>/repo`; Standard ist das OS-User-Cache-Verzeichnis.
- `--repo-dir`: expliziter Pfad zu einem lokalen Datenrepo, z. B. `./.gii-data`.
- `--branch`: Datenbranch; Standard ist `data`.
- `--transport`: MCP-Transport für `gii mcp`: `stdio` (Default), `http` (Streamable HTTP) oder `sse`.
- `--addr`: Listen-Adresse für `gii mcp --transport http|sse`; Standard ist `127.0.0.1:8080`.
- `--no-update`: vorhandenen Checkout offline verwenden.

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
