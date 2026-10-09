package gii_test

import (
	"context"
	"path/filepath"
	"strings"
	"testing"

	"github.com/janprill/gii"
)

func TestBDD_StructuredLawAndSnapshotsUseOfflineCache(t *testing.T) {
	source := newDataBranchXMLFixture(t, xmlVersion{date: "2024-01-01", xml: `<norm builddate="20240101000000"><metadaten><jurabk>BGB</jurabk><enbez>§ 280</enbez><titel>Schadensersatz</titel></metadaten><textdaten><text><Content><P>Strukturierter Text.</P></Content></text><fussnoten/></textdaten></norm>`})
	repositoryDir := filepath.Join(t.TempDir(), ".gii-data")
	updater := gii.New(gii.Options{RepositoryURL: source, RepositoryDir: repositoryDir})
	if err := updater.Update(context.Background()); err != nil {
		t.Fatal(err)
	}
	client := gii.New(gii.Options{RepositoryURL: "file:///must-not-fetch", RepositoryDir: repositoryDir})

	law, err := client.StructuredLawWithoutUpdate(context.Background(), "BGB", mustDate(t, "2024-01-15"))
	if err != nil {
		t.Fatal(err)
	}
	if law.ID != "bgb" || len(law.Norms) != 1 || law.Norms[0].EnBez != "§ 280" || law.Norms[0].BuildDate != "20240101000000" || !strings.Contains(law.Norms[0].Text, "Strukturierter Text.") {
		t.Fatalf("structured law=%+v", law)
	}
	snapshots, err := client.ListSnapshotsWithoutUpdate(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	for _, snapshot := range snapshots {
		if snapshot.Revision == law.Revision && !snapshot.CommittedAt.IsZero() {
			return
		}
	}
	t.Fatalf("revision %s absent from snapshots=%+v", law.Revision, snapshots)
}
