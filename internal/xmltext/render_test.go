package xmltext

import (
	"strings"
	"testing"
)

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
