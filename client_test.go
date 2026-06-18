package gii_test

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/janprill/gii"
	"github.com/janprill/gii/mcpserver"
	mcpsdk "github.com/modelcontextprotocol/go-sdk/mcp"
)

func TestBDD_GesetzestextZuHistorischemDatumAbrufen(t *testing.T) {
	// Given ein data-Branch enthaelt zwei Versionen des BGB.
	source := newDataBranchFixture(t,
		version{date: "2024-01-01", paragraph: "Die Rechtsfähigkeit beginnt alt."},
		version{date: "2024-02-01", paragraph: "Die Rechtsfähigkeit beginnt neu."},
	)
	client := gii.New(gii.Options{RepositoryURL: source, CacheDir: t.TempDir()})

	// When ich den Wortlaut des BGB zum 2024-01-15 abrufe.
	law, err := client.LawText(context.Background(), "BGB", mustDate(t, "2024-01-15"))
	if err != nil {
		t.Fatalf("LawText() error = %v", err)
	}

	// Then erhalte ich die alte Fassung.
	if !strings.Contains(law.Text, "Die Rechtsfähigkeit beginnt alt.") {
		t.Fatalf("expected old wording in:\n%s", law.Text)
	}
	if strings.Contains(law.Text, "Die Rechtsfähigkeit beginnt neu.") {
		t.Fatalf("did not expect new wording in historical text:\n%s", law.Text)
	}
	if law.ID != "bgb" || law.Title != "Bürgerliches Gesetzbuch" {
		t.Fatalf("unexpected law metadata: %#v", law)
	}
}

func TestBDD_OhneDatumWirdHeuteVerwendet(t *testing.T) {
	// Given heute ist der 2024-02-15.
	source := newDataBranchFixture(t,
		version{date: "2024-01-01", paragraph: "Heute noch nicht."},
		version{date: "2024-02-01", paragraph: "Heute gilt diese Fassung."},
	)
	client := gii.New(gii.Options{
		RepositoryURL: source,
		CacheDir:      t.TempDir(),
		Clock:         func() time.Time { return mustDate(t, "2024-02-15") },
	})

	// When ich den Wortlaut des BGB ohne Datum abrufe.
	law, err := client.LawTextToday(context.Background(), "bgb")
	if err != nil {
		t.Fatalf("LawTextToday() error = %v", err)
	}

	// Then erhalte ich die am Stichtag aktuelle Fassung.
	if !strings.Contains(law.Text, "Heute gilt diese Fassung.") {
		t.Fatalf("expected today's wording in:\n%s", law.Text)
	}
}

func TestBDD_UnbekanntesGesetzLiefertTypedError(t *testing.T) {
	source := newDataBranchFixture(t, version{date: "2024-01-01", paragraph: "Text."})
	client := gii.New(gii.Options{RepositoryURL: source, CacheDir: t.TempDir()})

	_, err := client.LawText(context.Background(), "UnbekanntG", mustDate(t, "2024-01-15"))
	if !errors.Is(err, gii.ErrLawNotFound) {
		t.Fatalf("expected ErrLawNotFound, got %v", err)
	}
}

func TestBDD_EinzelnormWirdTokenSparsamGerendert(t *testing.T) {
	source := newDataBranchXMLFixture(t, xmlVersion{date: "2024-01-01", xml: `<norm><metadaten><jurabk>BGB</jurabk><enbez>§ 280</enbez><titel>Schadensersatz wegen Pflichtverletzung</titel></metadaten><textdaten><text><Content><P>Nur § 280.</P></Content></text><fussnoten/></textdaten></norm><norm><metadaten><jurabk>BGB</jurabk><enbez>§ 281</enbez><titel>Folgenorm</titel></metadaten><textdaten><text><Content><P>Nicht angeforderte Norm.</P></Content></text><fussnoten/></textdaten></norm>`})
	client := gii.New(gii.Options{RepositoryURL: source, CacheDir: t.TempDir()})

	law, err := client.LawNormText(context.Background(), "BGB", "280", mustDate(t, "2024-01-15"))
	if err != nil {
		t.Fatalf("LawNormText() error = %v", err)
	}
	if law.Norm != "280" || !strings.Contains(law.Text, "§ 280 Schadensersatz wegen Pflichtverletzung") || !strings.Contains(law.Text, "Nur § 280.") {
		t.Fatalf("expected § 280 text, got %#v\n%s", law, law.Text)
	}
	if strings.Contains(law.Text, "§ 281") || strings.Contains(law.Text, "Nicht angeforderte Norm") || strings.Contains(law.Text, "Bürgerliches Gesetzbuch") {
		t.Fatalf("expected token-sparse single norm text, got:\n%s", law.Text)
	}

	_, err = client.LawNormTextWithoutUpdate(context.Background(), "BGB", "999", mustDate(t, "2024-01-15"))
	if !errors.Is(err, gii.ErrNormNotFound) {
		t.Fatalf("expected ErrNormNotFound, got %v", err)
	}
}

func TestBDD_MCPNormTextLiefertNurEinzelnorm(t *testing.T) {
	source := newDataBranchXMLFixture(t, xmlVersion{date: "2024-01-01", xml: `<norm><metadaten><jurabk>BGB</jurabk><enbez>§ 280</enbez><titel>Schadensersatz wegen Pflichtverletzung</titel></metadaten><textdaten><text><Content><P>MCP nur § 280.</P></Content></text><fussnoten/></textdaten></norm><norm><metadaten><jurabk>BGB</jurabk><enbez>§ 281</enbez><titel>Folgenorm</titel></metadaten><textdaten><text><Content><P>MCP nicht § 281.</P></Content></text><fussnoten/></textdaten></norm>`})
	repoDir := filepath.Join(t.TempDir(), ".gii-data")
	client := gii.New(gii.Options{RepositoryURL: source, RepositoryDir: repoDir})
	if err := client.Update(context.Background()); err != nil {
		t.Fatalf("Update() error = %v", err)
	}
	session, cleanup := newMCPSession(t, client)
	defer cleanup()

	result, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{
		Name:      "norm_text",
		Arguments: map[string]any{"query": "BGB", "norm": "280", "date": "2024-01-15"},
	})
	if err != nil {
		t.Fatalf("norm_text CallTool error = %v", err)
	}
	text := toolText(result)
	if result.IsError || !strings.Contains(text, "§ 280 Schadensersatz wegen Pflichtverletzung") || !strings.Contains(text, "MCP nur § 280.") {
		t.Fatalf("expected § 280 result, got %#v text=%q", result, text)
	}
	if strings.Contains(text, "§ 281") || strings.Contains(text, "MCP nicht § 281") {
		t.Fatalf("norm_text should not return following norm, got:\n%s", text)
	}

	viaLawText, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{
		Name:      "law_text",
		Arguments: map[string]any{"query": "BGB", "norm": "§ 280", "date": "2024-01-15"},
	})
	if err != nil {
		t.Fatalf("law_text with norm CallTool error = %v", err)
	}
	if viaLawText.IsError || !strings.Contains(toolText(viaLawText), "MCP nur § 280.") || strings.Contains(toolText(viaLawText), "MCP nicht § 281") {
		t.Fatalf("law_text optional norm should return only § 280, got %#v text=%q", viaLawText, toolText(viaLawText))
	}
}

func TestBDD_CLIAktualisiertCacheUndGibtWortlautAus(t *testing.T) {
	// Given ein leerer lokaler Cache.
	source := newDataBranchFixture(t,
		version{date: "2024-01-01", paragraph: "Alte CLI-Fassung."},
		version{date: "2024-02-01", paragraph: "CLI gibt diese Fassung aus."},
	)
	cache := t.TempDir()
	exe := buildCLI(t)

	// When ich `gii text BGB --date 2024-02-15` ausfuehre.
	cmd := exec.Command(exe, "text", "BGB", "--date", "2024-02-15", "--repo-url", source, "--cache-dir", cache)
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("gii CLI failed: %v\n%s", err, out)
	}

	// Then wird der data-Branch geklont oder aktualisiert und der Wortlaut wird geschrieben.
	if _, err := os.Stat(filepath.Join(cache, "repo", ".git")); err != nil {
		t.Fatalf("expected cloned repo in cache: %v", err)
	}
	stdout := string(out)
	if !strings.Contains(stdout, "CLI gibt diese Fassung aus.") {
		t.Fatalf("expected wording on stdout, got:\n%s", stdout)
	}
}

func TestBDD_CLIKurzformOhneDatumNutztHeute(t *testing.T) {
	source := newDataBranchFixture(t, version{date: "2024-01-01", paragraph: "Heute per CLI."})
	exe := buildCLI(t)
	cmd := exec.Command(exe, "text", "bgb", "--data-repo", source, "--cache-dir", t.TempDir(), "--today", "2024-01-15")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("gii CLI failed: %v\n%s", err, out)
	}
	if !strings.Contains(string(out), "Heute per CLI.") {
		t.Fatalf("expected today's text, got:\n%s", out)
	}
}

func TestBDD_CLIKlonteExplizitesDatenrepoFuerProjekt(t *testing.T) {
	// Given ein Projekt moechte ein sichtbares lokales Datenrepo statt eines versteckten OS-Caches.
	source := newDataBranchFixture(t, version{date: "2024-01-01", paragraph: "Projekt-Repo-Fassung."})
	repoDir := filepath.Join(t.TempDir(), ".gii-data")
	exe := buildCLI(t)

	// When das CLI mit --repo-dir aktualisiert wird.
	cmd := exec.Command(exe, "update", "--data-repo", source, "--repo-dir", repoDir)
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("gii update failed: %v\n%s", err, out)
	}

	// Then liegt dort ein direkt nutzbares Git-Repo mit data-Branch.
	if _, err := os.Stat(filepath.Join(repoDir, ".git")); err != nil {
		t.Fatalf("expected cloned data repo at --repo-dir: %v", err)
	}
	cmd = exec.Command(exe, "text", "BGB", "--repo-dir", repoDir, "--no-update", "--date", "2024-01-15")
	out, err = cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("gii text --repo-dir --no-update failed: %v\n%s", err, out)
	}
	if !strings.Contains(string(out), "Projekt-Repo-Fassung.") {
		t.Fatalf("expected text from project repo, got:\n%s", out)
	}
}

func TestBDD_DiscoveryFindetBGBLokalOhneUpdate(t *testing.T) {
	source := newDataBranchFixture(t, version{date: "2024-01-01", paragraph: "Discovery-Fassung."})
	repoDir := filepath.Join(t.TempDir(), ".gii-data")
	updater := gii.New(gii.Options{RepositoryURL: source, RepositoryDir: repoDir})
	if err := updater.Update(context.Background()); err != nil {
		t.Fatalf("Update() error = %v", err)
	}

	// A different, invalid RepositoryURL proves that discovery reads only the local checkout.
	client := gii.New(gii.Options{RepositoryURL: "file:///does-not-exist", RepositoryDir: repoDir})
	listed, err := client.ListLawsWithoutUpdate(context.Background(), mustDate(t, "2024-01-15"), 10, 0)
	if err != nil {
		t.Fatalf("ListLawsWithoutUpdate() error = %v", err)
	}
	if listed.Total != 1 || len(listed.Laws) != 1 || listed.Laws[0].ID != "bgb" {
		t.Fatalf("expected listed BGB, got %#v", listed)
	}

	found, err := client.SearchLawsWithoutUpdate(context.Background(), "BGB", mustDate(t, "2024-01-15"), 10, 0)
	if err != nil {
		t.Fatalf("SearchLawsWithoutUpdate() error = %v", err)
	}
	if found.Total != 1 || len(found.Laws) != 1 || found.Laws[0].Title != "Bürgerliches Gesetzbuch" {
		t.Fatalf("expected search to find BGB, got %#v", found)
	}
}

func TestBDD_MCPToolsLiefernHistorischenTextUndDiscovery(t *testing.T) {
	source := newDataBranchFixture(t,
		version{date: "2024-01-01", paragraph: "Alter MCP-Text."},
		version{date: "2024-02-01", paragraph: "Neuer MCP-Text."},
	)
	repoDir := filepath.Join(t.TempDir(), ".gii-data")
	client := gii.New(gii.Options{RepositoryURL: source, RepositoryDir: repoDir})
	if err := client.Update(context.Background()); err != nil {
		t.Fatalf("Update() error = %v", err)
	}
	session, cleanup := newMCPSession(t, client)
	defer cleanup()

	textResult, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{
		Name:      "law_text",
		Arguments: map[string]any{"query": "BGB", "date": "2024-01-15"},
	})
	if err != nil {
		t.Fatalf("law_text CallTool error = %v", err)
	}
	if textResult.IsError || !strings.Contains(toolText(textResult), "Alter MCP-Text.") || strings.Contains(toolText(textResult), "Neuer MCP-Text.") {
		t.Fatalf("unexpected law_text result: %#v text=%q", textResult, toolText(textResult))
	}

	listResult, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{
		Name:      "list_laws",
		Arguments: map[string]any{"date": "2024-01-15", "limit": 5},
	})
	if err != nil {
		t.Fatalf("list_laws CallTool error = %v", err)
	}
	if listResult.IsError || !strings.Contains(toolText(listResult), "Bürgerliches Gesetzbuch") {
		t.Fatalf("unexpected list_laws result: %#v text=%q", listResult, toolText(listResult))
	}

	searchResult, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{
		Name:      "search_laws",
		Arguments: map[string]any{"query": "BGB", "date": "2024-01-15"},
	})
	if err != nil {
		t.Fatalf("search_laws CallTool error = %v", err)
	}
	if searchResult.IsError || !strings.Contains(toolText(searchResult), `"id":"bgb"`) {
		t.Fatalf("unexpected search_laws result: %#v text=%q", searchResult, toolText(searchResult))
	}
}

func TestBDD_MCPReadToolsBrauchenExplizitesUpdate(t *testing.T) {
	source := newDataBranchFixture(t, version{date: "2024-01-01", paragraph: "Nach explizitem Update."})
	repoDir := filepath.Join(t.TempDir(), ".gii-data")
	client := gii.New(gii.Options{RepositoryURL: source, RepositoryDir: repoDir})
	session, cleanup := newMCPSession(t, client)
	defer cleanup()

	missing, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{
		Name:      "law_text",
		Arguments: map[string]any{"query": "BGB", "date": "2024-01-15"},
	})
	if err != nil {
		t.Fatalf("law_text without cache CallTool error = %v", err)
	}
	if !missing.IsError || !strings.Contains(toolText(missing), "local_cache_missing") {
		t.Fatalf("expected local_cache_missing tool error, got %#v text=%q", missing, toolText(missing))
	}
	if _, err := os.Stat(filepath.Join(repoDir, ".git")); !os.IsNotExist(err) {
		t.Fatalf("read tool should not create/update repo; stat err = %v", err)
	}

	updated, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{Name: "update_cache", Arguments: map[string]any{}})
	if err != nil {
		t.Fatalf("update_cache CallTool error = %v", err)
	}
	if updated.IsError || !strings.Contains(toolText(updated), "updated") {
		t.Fatalf("unexpected update_cache result: %#v text=%q", updated, toolText(updated))
	}

	ok, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{
		Name:      "law_text",
		Arguments: map[string]any{"query": "BGB", "date": "2024-01-15"},
	})
	if err != nil {
		t.Fatalf("law_text after update CallTool error = %v", err)
	}
	if ok.IsError || !strings.Contains(toolText(ok), "Nach explizitem Update.") {
		t.Fatalf("expected law_text after update, got %#v text=%q", ok, toolText(ok))
	}
}

func TestBDD_MCPMeldetUngueltigesDatumUndUnbekanntesGesetzTypisiert(t *testing.T) {
	source := newDataBranchFixture(t, version{date: "2024-01-01", paragraph: "Text."})
	repoDir := filepath.Join(t.TempDir(), ".gii-data")
	client := gii.New(gii.Options{RepositoryURL: source, RepositoryDir: repoDir})
	if err := client.Update(context.Background()); err != nil {
		t.Fatalf("Update() error = %v", err)
	}
	session, cleanup := newMCPSession(t, client)
	defer cleanup()

	invalidDate, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{
		Name:      "law_text",
		Arguments: map[string]any{"query": "BGB", "date": "15.01.2024"},
	})
	if err != nil {
		t.Fatalf("invalid date CallTool error = %v", err)
	}
	if !invalidDate.IsError || !strings.Contains(toolText(invalidDate), "invalid_date") {
		t.Fatalf("expected invalid_date tool error, got %#v text=%q", invalidDate, toolText(invalidDate))
	}

	unknown, err := session.CallTool(context.Background(), &mcpsdk.CallToolParams{
		Name:      "law_text",
		Arguments: map[string]any{"query": "UnbekanntG", "date": "2024-01-15"},
	})
	if err != nil {
		t.Fatalf("unknown law CallTool error = %v", err)
	}
	if !unknown.IsError || !strings.Contains(toolText(unknown), "law_not_found") {
		t.Fatalf("expected law_not_found tool error, got %#v text=%q", unknown, toolText(unknown))
	}
}

func TestBDD_CLIUsageZeigtMCP(t *testing.T) {
	exe := buildCLI(t)
	cmd := exec.Command(exe, "help")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("gii help failed: %v\n%s", err, out)
	}
	if !strings.Contains(string(out), "gii mcp") {
		t.Fatalf("expected mcp in usage, got:\n%s", out)
	}
}

func TestDefaultDataRepositoryIsPublicArchiveNotCodeModule(t *testing.T) {
	if gii.DefaultRepositoryURL != "https://github.com/QuantLaw/gesetze-im-internet.git" {
		t.Fatalf("unexpected default data repository: %s", gii.DefaultRepositoryURL)
	}
}

type version struct {
	date      string
	paragraph string
}

type xmlVersion struct {
	date string
	xml  string
}

func newDataBranchFixture(t *testing.T, versions ...version) string {
	t.Helper()
	repo := filepath.Join(t.TempDir(), "source")
	runGit(t, "", nil, "init", "--initial-branch=data", repo)
	for _, v := range versions {
		writeFixtureData(t, repo, v.paragraph)
		runGitWithDate(t, repo, v.date, "add", "data", "README.md")
		runGitWithDate(t, repo, v.date, "commit", "-m", "scrape "+v.date)
		runGitWithDate(t, repo, v.date, "tag", v.date)
	}
	return repo
}

func newDataBranchXMLFixture(t *testing.T, versions ...xmlVersion) string {
	t.Helper()
	repo := filepath.Join(t.TempDir(), "source")
	runGit(t, "", nil, "init", "--initial-branch=data", repo)
	for _, v := range versions {
		writeFixtureXMLData(t, repo, v.xml)
		runGitWithDate(t, repo, v.date, "add", "data", "README.md")
		runGitWithDate(t, repo, v.date, "commit", "-m", "scrape "+v.date)
		runGitWithDate(t, repo, v.date, "tag", v.date)
	}
	return repo
}

func writeFixtureData(t *testing.T, repo, paragraph string) {
	t.Helper()
	mustWrite(t, filepath.Join(repo, "README.md"), "fixture\n")
	mustWrite(t, filepath.Join(repo, "data", "toc.xml"), `<?xml version="1.0" encoding="UTF-8" ?>
<items>
  <item>
    <title>Bürgerliches Gesetzbuch</title>
    <link>http://www.gesetze-im-internet.de/bgb/xml.zip</link>
  </item>
</items>
`)
	writeFixtureXMLData(t, repo, `<norm builddate="20240101000000" doknr="BJNR001950896BJNE000102377"><metadaten><jurabk>BGB</jurabk><enbez>§ 1</enbez><titel format="parat">Beginn der Rechtsfähigkeit</titel></metadaten><textdaten><text format="XML"><Content><P>`+paragraph+`</P></Content></text><fussnoten/></textdaten></norm>`)
}

func writeFixtureXMLData(t *testing.T, repo, xml string) {
	t.Helper()
	mustWrite(t, filepath.Join(repo, "README.md"), "fixture\n")
	mustWrite(t, filepath.Join(repo, "data", "toc.xml"), `<?xml version="1.0" encoding="UTF-8" ?>
<items>
  <item>
    <title>Bürgerliches Gesetzbuch</title>
    <link>http://www.gesetze-im-internet.de/bgb/xml.zip</link>
  </item>
</items>
`)
	mustWrite(t, filepath.Join(repo, "data", "items", "bgb", "BJNR001950896.xml"), xml+"\n")
}

func newMCPSession(t *testing.T, client *gii.Client) (*mcpsdk.ClientSession, func()) {
	t.Helper()
	serverTransport, clientTransport := mcpsdk.NewInMemoryTransports()
	ctx, cancel := context.WithCancel(context.Background())
	server := mcpserver.New(client)
	errc := make(chan error, 1)
	go func() {
		errc <- server.Run(ctx, serverTransport)
	}()
	mcpClient := mcpsdk.NewClient(&mcpsdk.Implementation{Name: "gii-test", Version: "v0.0.0"}, nil)
	session, err := mcpClient.Connect(ctx, clientTransport, nil)
	if err != nil {
		cancel()
		t.Fatalf("MCP client connect failed: %v", err)
	}
	cleanup := func() {
		_ = session.Close()
		cancel()
		select {
		case err := <-errc:
			if err != nil && !errors.Is(err, context.Canceled) {
				t.Logf("MCP server stopped with error: %v", err)
			}
		case <-time.After(2 * time.Second):
			t.Log("MCP server did not stop within timeout")
		}
	}
	return session, cleanup
}

func toolText(result *mcpsdk.CallToolResult) string {
	if result == nil {
		return ""
	}
	var b strings.Builder
	for _, content := range result.Content {
		if text, ok := content.(*mcpsdk.TextContent); ok {
			b.WriteString(text.Text)
		}
	}
	return b.String()
}

func buildCLI(t *testing.T) string {
	t.Helper()
	exe := filepath.Join(t.TempDir(), "gii")
	if runtime.GOOS == "windows" {
		exe += ".exe"
	}
	cmd := exec.Command("go", "build", "-o", exe, "./cmd/gii")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go build ./cmd/gii failed: %v\n%s", err, out)
	}
	return exe
}

func mustDate(t *testing.T, value string) time.Time {
	t.Helper()
	d, err := time.Parse("2006-01-02", value)
	if err != nil {
		t.Fatalf("parse date: %v", err)
	}
	return d
}

func mustWrite(t *testing.T, path, contents string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(contents), 0o644); err != nil {
		t.Fatal(err)
	}
}

func runGitWithDate(t *testing.T, dir, day string, args ...string) {
	t.Helper()
	stamp := day + "T12:00:00Z"
	env := []string{
		"GIT_AUTHOR_NAME=Fixture",
		"GIT_AUTHOR_EMAIL=fixture@example.invalid",
		"GIT_COMMITTER_NAME=Fixture",
		"GIT_COMMITTER_EMAIL=fixture@example.invalid",
		"GIT_AUTHOR_DATE=" + stamp,
		"GIT_COMMITTER_DATE=" + stamp,
	}
	runGit(t, dir, env, args...)
}

func runGit(t *testing.T, dir string, env []string, args ...string) {
	t.Helper()
	cmd := exec.Command("git", args...)
	if dir != "" {
		cmd.Dir = dir
	}
	cmd.Env = append(os.Environ(), env...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("git %s failed: %v\n%s", strings.Join(args, " "), err, out)
	}
}
