package gii

import (
	"context"
	"os"
	"path/filepath"
	"time"

	"github.com/janprill/gii/internal/gitrepo"
	"github.com/janprill/gii/internal/xmltext"
)

const (
	// DefaultRepositoryURL is the repository that is expected to contain the data branch.
	// Private installations can authenticate through the normal git credential/SSH setup or override this option.
	DefaultRepositoryURL = "https://github.com/janprill/gii.git"
	DefaultDataBranch    = "data"
)

// Options configures a Client.
type Options struct {
	// RepositoryURL is cloned/fetched to access the data branch.
	// Defaults to DefaultRepositoryURL.
	RepositoryURL string

	// CacheDir stores the local git clone. Defaults to the user cache directory.
	CacheDir string

	// DataBranch is the git branch containing data/items and data/toc.xml. Defaults to "data".
	DataBranch string

	// GitBin is the git executable. Defaults to "git".
	GitBin string

	// Clock supplies today's date for LawTextToday. Defaults to time.Now.
	Clock func() time.Time
}

// Client provides stichtagsbezogenen Zugriff auf Gesetze-im-Internet data-branch contents.
type Client struct {
	options Options
	store   *gitrepo.Store
}

// New creates a Client. It does not touch the network until Update or a lookup is called.
func New(options Options) *Client {
	options = normalizeOptions(options)
	return &Client{
		options: options,
		store: gitrepo.New(gitrepo.Options{
			RepositoryURL: options.RepositoryURL,
			CacheDir:      filepath.Join(options.CacheDir, "repo"),
			DataBranch:    options.DataBranch,
			GitBin:        options.GitBin,
		}),
	}
}

// Update clones or fetches the configured repository's data branch and tags.
func (c *Client) Update(ctx context.Context) error {
	return c.store.Update(ctx)
}

// LawText updates the local cache and returns the wording of query as of date.
// A zero date means today according to the configured Clock.
func (c *Client) LawText(ctx context.Context, query string, date time.Time) (*Law, error) {
	return c.lawText(ctx, query, date, true)
}

// LawTextWithoutUpdate returns the wording from the local cache without fetching first.
// It is useful for offline use after Update was called explicitly.
func (c *Client) LawTextWithoutUpdate(ctx context.Context, query string, date time.Time) (*Law, error) {
	return c.lawText(ctx, query, date, false)
}

// LawTextToday updates the local cache and returns the wording of query as of today.
func (c *Client) LawTextToday(ctx context.Context, query string) (*Law, error) {
	return c.LawText(ctx, query, c.today())
}

func (c *Client) lawText(ctx context.Context, query string, date time.Time, update bool) (*Law, error) {
	if date.IsZero() {
		date = c.today()
	}
	if update {
		if err := c.Update(ctx); err != nil {
			return nil, err
		}
	}
	rev, err := c.store.RevisionForDate(ctx, date)
	if err != nil {
		return nil, err
	}
	match, err := c.store.FindLaw(ctx, rev, query)
	if err != nil {
		return nil, err
	}
	var rendered []xmltext.Document
	for _, file := range match.XMLFiles {
		contents, err := c.store.ShowFile(ctx, rev, file)
		if err != nil {
			return nil, err
		}
		rendered = append(rendered, xmltext.Document{Path: file, XML: contents})
	}
	text, err := xmltext.RenderLaw(match.Title, rendered)
	if err != nil {
		return nil, err
	}
	return &Law{
		Query:    query,
		ID:       match.ID,
		Title:    match.Title,
		Date:     date,
		Revision: rev,
		XMLFiles: append([]string(nil), match.XMLFiles...),
		Text:     text,
	}, nil
}

func (c *Client) today() time.Time {
	return c.options.Clock()
}

func normalizeOptions(options Options) Options {
	if options.RepositoryURL == "" {
		options.RepositoryURL = DefaultRepositoryURL
	}
	if options.DataBranch == "" {
		options.DataBranch = DefaultDataBranch
	}
	if options.GitBin == "" {
		options.GitBin = "git"
	}
	if options.Clock == nil {
		options.Clock = time.Now
	}
	if options.CacheDir == "" {
		options.CacheDir = defaultCacheDir()
	}
	return options
}

func defaultCacheDir() string {
	base, err := os.UserCacheDir()
	if err != nil || base == "" {
		base = os.TempDir()
	}
	return filepath.Join(base, "gii")
}
