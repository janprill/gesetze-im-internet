package xmltext

import (
	"errors"
	"strings"
	"testing"
)

func TestRenderLawNormSelectsSingleNorm(t *testing.T) {
	text, err := RenderLawNorm("Testgesetz", []Document{{Path: "data/items/test/test.xml", XML: `<norm><metadaten><jurabk>TEST</jurabk><enbez>§ 280</enbez><titel>Schadensersatz wegen Pflichtverletzung</titel></metadaten><textdaten><text><Content><P>Nur Norm 280.</P></Content></text><fussnoten/></textdaten></norm><norm><metadaten><jurabk>TEST</jurabk><enbez>§ 281</enbez><titel>Folgenorm</titel></metadaten><textdaten><text><Content><P>Nicht ausgeben.</P></Content></text><fussnoten/></textdaten></norm>`}}, "280")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text, "§ 280 Schadensersatz wegen Pflichtverletzung") || !strings.Contains(text, "Nur Norm 280.") {
		t.Fatalf("expected § 280 in:\n%s", text)
	}
	if strings.Contains(text, "§ 281") || strings.Contains(text, "Nicht ausgeben.") || strings.Contains(text, "Testgesetz") {
		t.Fatalf("expected only selected norm without full law title, got:\n%s", text)
	}
}

func TestRenderLawNormReturnsTypedError(t *testing.T) {
	_, err := RenderLawNorm("Testgesetz", []Document{{Path: "data/items/test/test.xml", XML: `<norm><metadaten><enbez>§ 1</enbez><titel>Start</titel></metadaten><textdaten><text><Content><P>Text.</P></Content></text></textdaten></norm>`}}, "280")
	if !errors.Is(err, ErrNormNotFound) {
		t.Fatalf("expected ErrNormNotFound, got %v", err)
	}
}

func TestRenderLawRendersHeadingsParagraphsListsAndFootnotes(t *testing.T) {
	text, err := RenderLaw("Testgesetz", []Document{{Path: "data/items/test/test.xml", XML: `<norm><metadaten><jurabk>TEST</jurabk><enbez>§ 1</enbez><titel>Pflichten</titel></metadaten><textdaten><text><Content><P>Absatz eins.</P><P>Liste:<DL><DT>1.</DT><DD><LA>Erstens</LA></DD></DL></P></Content></text><fussnoten><Content><P>Amtlicher Hinweis.</P></Content></fussnoten></textdaten></norm>`}})
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"Testgesetz", "§ 1 Pflichten", "Absatz eins.", "Liste:", "1.", "Erstens", "Fußnoten:", "Amtlicher Hinweis."} {
		if !strings.Contains(text, want) {
			t.Fatalf("expected %q in:\n%s", want, text)
		}
	}
}
