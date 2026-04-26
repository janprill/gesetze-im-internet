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
	cmd := exec.Command(exe, "text", "bgb", "--repo-url", source, "--cache-dir", t.TempDir(), "--today", "2024-01-15")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("gii CLI failed: %v\n%s", err, out)
	}
	if !strings.Contains(string(out), "Heute per CLI.") {
		t.Fatalf("expected today's text, got:\n%s", out)
	}
}

type version struct {
	date      string
	paragraph string
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
	mustWrite(t, filepath.Join(repo, "data", "items", "bgb", "BJNR001950896.xml"), `<norm builddate="20240101000000" doknr="BJNR001950896BJNE000102377"><metadaten><jurabk>BGB</jurabk><enbez>§ 1</enbez><titel format="parat">Beginn der Rechtsfähigkeit</titel></metadaten><textdaten><text format="XML"><Content><P>`+paragraph+`</P></Content></text><fussnoten/></textdaten></norm>
`)
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
