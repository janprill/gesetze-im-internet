package gitrepo

import (
	"bytes"
	"context"
	"encoding/xml"
	"fmt"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/janprill/gii/internal/errs"
)

type Options struct {
	RepositoryURL string
	CacheDir      string
	DataBranch    string
	GitBin        string
}

type Store struct {
	options Options
}

type LawMatch struct {
	ID       string
	Title    string
	XMLFiles []string
}

type tocItem struct {
	Title string `xml:"title"`
	Link  string `xml:"link"`
	ID    string
}

func New(options Options) *Store {
	return &Store{options: options}
}

func (s *Store) Update(ctx context.Context) error {
	if _, err := os.Stat(filepath.Join(s.options.CacheDir, ".git")); err != nil {
		if !os.IsNotExist(err) {
			return err
		}
		if err := os.RemoveAll(s.options.CacheDir); err != nil {
			return err
		}
		if err := os.MkdirAll(filepath.Dir(s.options.CacheDir), 0o755); err != nil {
			return err
		}
		if _, err := s.git(ctx, "", "clone", "--branch", s.options.DataBranch, "--single-branch", s.options.RepositoryURL, s.options.CacheDir); err != nil {
			return err
		}
	}
	if _, err := s.git(ctx, s.options.CacheDir, "remote", "set-url", "origin", s.options.RepositoryURL); err != nil {
		return err
	}
	if _, err := s.git(ctx, s.options.CacheDir, "fetch", "--prune", "--tags", "origin", "+refs/heads/"+s.options.DataBranch+":refs/remotes/origin/"+s.options.DataBranch); err != nil {
		return err
	}
	_, err := s.git(ctx, s.options.CacheDir, "checkout", "-B", s.options.DataBranch, "refs/remotes/origin/"+s.options.DataBranch)
	return err
}

func (s *Store) RevisionForDate(ctx context.Context, date time.Time) (string, error) {
	if date.IsZero() {
		date = time.Now()
	}
	cutoff := endOfDayUTC(date).Format(time.RFC3339)
	out, err := s.git(ctx, s.options.CacheDir, "rev-list", "-n", "1", "--before="+cutoff, "refs/remotes/origin/"+s.options.DataBranch)
	if err != nil {
		return "", err
	}
	rev := strings.TrimSpace(out)
	if rev == "" {
		return "", fmt.Errorf("%w: no data commit at or before %s", errs.RevisionNotFound, date.Format("2006-01-02"))
	}
	return rev, nil
}

func (s *Store) FindLaw(ctx context.Context, rev, query string) (LawMatch, error) {
	q := normalize(query)
	if q == "" {
		return LawMatch{}, fmt.Errorf("%w: empty query", errs.LawNotFound)
	}
	items, _ := s.toc(ctx, rev)
	byID := map[string]tocItem{}
	for _, item := range items {
		if item.ID == "" {
			continue
		}
		byID[normalize(item.ID)] = item
	}

	if item, ok := byID[q]; ok {
		return s.matchForID(ctx, rev, item.ID, item.Title)
	}
	for _, item := range items {
		if normalize(item.Title) == q {
			return s.matchForID(ctx, rev, item.ID, item.Title)
		}
	}
	for _, item := range items {
		if strings.Contains(normalize(item.Title), q) {
			return s.matchForID(ctx, rev, item.ID, item.Title)
		}
	}

	if item, ok, err := s.findByJurAbk(ctx, rev, items, query); err != nil {
		return LawMatch{}, err
	} else if ok {
		return s.matchForID(ctx, rev, item.ID, item.Title)
	}

	return LawMatch{}, fmt.Errorf("%w: %q", errs.LawNotFound, query)
}

func (s *Store) matchForID(ctx context.Context, rev, id, title string) (LawMatch, error) {
	files, err := s.xmlFilesForID(ctx, rev, id)
	if err != nil {
		return LawMatch{}, err
	}
	if len(files) == 0 {
		return LawMatch{}, fmt.Errorf("%w: %s has no xml files", errs.LawNotFound, id)
	}
	return LawMatch{ID: id, Title: title, XMLFiles: files}, nil
}

func (s *Store) ShowFile(ctx context.Context, rev, path string) (string, error) {
	return s.git(ctx, s.options.CacheDir, "show", rev+":"+path)
}

func (s *Store) toc(ctx context.Context, rev string) ([]tocItem, error) {
	contents, err := s.ShowFile(ctx, rev, "data/toc.xml")
	if err != nil {
		return nil, err
	}
	var parsed struct {
		Items []tocItem `xml:"item"`
	}
	decoder := xml.NewDecoder(strings.NewReader(contents))
	decoder.Strict = false
	if err := decoder.Decode(&parsed); err != nil {
		return nil, err
	}
	for i := range parsed.Items {
		parsed.Items[i].ID = idFromLink(parsed.Items[i].Link)
	}
	return parsed.Items, nil
}

func (s *Store) xmlFilesForID(ctx context.Context, rev, id string) ([]string, error) {
	prefix := "data/items/" + id
	out, err := s.git(ctx, s.options.CacheDir, "ls-tree", "-r", "--name-only", rev, "--", prefix)
	if err != nil {
		return nil, err
	}
	var files []string
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasSuffix(strings.ToLower(line), ".xml") {
			files = append(files, line)
		}
	}
	sort.Strings(files)
	return files, nil
}

func (s *Store) findByJurAbk(ctx context.Context, rev string, items []tocItem, query string) (tocItem, bool, error) {
	needle := "<jurabk>" + query + "</jurabk>"
	out, err := s.git(ctx, s.options.CacheDir, "grep", "-F", "-l", needle, rev, "--", "data/items")
	if err != nil {
		if exit, ok := err.(*GitError); ok && exit.ExitCode == 1 {
			return tocItem{}, false, nil
		}
		return tocItem{}, false, err
	}
	first := ""
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasSuffix(strings.ToLower(line), ".xml") {
			first = line
			break
		}
	}
	if first == "" {
		return tocItem{}, false, nil
	}
	id := itemIDFromPath(first)
	for _, item := range items {
		if item.ID == id {
			return item, true, nil
		}
	}
	return tocItem{ID: id, Title: id}, true, nil
}

func (s *Store) git(ctx context.Context, dir string, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, s.options.GitBin, args...)
	if dir != "" {
		cmd.Dir = dir
	}
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	if err != nil {
		exitCode := -1
		if exit, ok := err.(*exec.ExitError); ok {
			exitCode = exit.ExitCode()
		}
		return stdout.String(), &GitError{Args: append([]string(nil), args...), Dir: dir, ExitCode: exitCode, Stderr: stderr.String(), Err: err}
	}
	return stdout.String(), nil
}

type GitError struct {
	Args     []string
	Dir      string
	ExitCode int
	Stderr   string
	Err      error
}

func (e *GitError) Error() string {
	msg := strings.TrimSpace(e.Stderr)
	if msg == "" {
		msg = e.Err.Error()
	}
	return fmt.Sprintf("git %s failed: %s", strings.Join(e.Args, " "), msg)
}

func (e *GitError) Unwrap() error { return e.Err }

func endOfDayUTC(date time.Time) time.Time {
	y, m, d := date.Date()
	return time.Date(y, m, d, 23, 59, 59, int(time.Second-time.Nanosecond), time.UTC)
}

func normalize(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	value = strings.ReplaceAll(value, " ", "")
	value = strings.ReplaceAll(value, "-", "")
	value = strings.ReplaceAll(value, "_", "")
	return value
}

func idFromLink(link string) string {
	parsed, err := url.Parse(strings.TrimSpace(link))
	var path string
	if err == nil {
		path = parsed.Path
	} else {
		path = link
	}
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) >= 2 && parts[len(parts)-1] == "xml.zip" {
		return parts[len(parts)-2]
	}
	return ""
}

func itemIDFromPath(path string) string {
	parts := strings.Split(filepath.ToSlash(path), "/")
	for i := 0; i+1 < len(parts); i++ {
		if parts[i] == "items" {
			return parts[i+1]
		}
	}
	return ""
}
