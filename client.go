package gii

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/janprill/gii/internal/errs"
	"github.com/janprill/gii/internal/gitrepo"
	"github.com/janprill/gii/internal/xmltext"
)

const (
	// DefaultRepositoryURL is the public archive repository that contains the data branch.
	// The Go module itself can live in a private repository; callers only need to override
	// this when they want to use their own data mirror.
	DefaultRepositoryURL = "https://github.com/QuantLaw/gesetze-im-internet.git"
	DefaultDataBranch    = "data"
)

// Options configures a Client.
type Options struct {
	// RepositoryURL is cloned/fetched to access the data branch.
	// Defaults to DefaultRepositoryURL.
	RepositoryURL string

	// CacheDir stores the managed local git clone below <CacheDir>/repo.
	// Defaults to the user cache directory. Ignored when RepositoryDir is set.
	CacheDir string

	// RepositoryDir is an explicit path to the local git clone. When set, gii clones/fetches
	// directly into this directory instead of using <CacheDir>/repo. This is useful for
	// project-local bootstraps such as ./.gii-data that other tools can also inspect.
	RepositoryDir string

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
	repositoryDir := options.RepositoryDir
	if repositoryDir == "" {
		repositoryDir = filepath.Join(options.CacheDir, "repo")
	}
	return &Client{
		options: options,
		store: gitrepo.New(gitrepo.Options{
			RepositoryURL: options.RepositoryURL,
			CacheDir:      repositoryDir,
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
	return c.lawText(ctx, query, "", date, true)
}

// LawNormText updates the local cache and returns one individual norm of query as of date.
// A zero date means today according to the configured Clock.
func (c *Client) LawNormText(ctx context.Context, query, norm string, date time.Time) (*Law, error) {
	return c.lawText(ctx, query, norm, date, true)
}

// LawTextWithoutUpdate returns the wording from the local cache without fetching first.
// It is useful for offline use after Update was called explicitly.
func (c *Client) LawTextWithoutUpdate(ctx context.Context, query string, date time.Time) (*Law, error) {
	return c.lawText(ctx, query, "", date, false)
}

// LawNormTextWithoutUpdate returns one individual norm from the local cache without fetching first.
// It is useful for token-sparse MCP and offline use after Update was called explicitly.
func (c *Client) LawNormTextWithoutUpdate(ctx context.Context, query, norm string, date time.Time) (*Law, error) {
	return c.lawText(ctx, query, norm, date, false)
}

// LawTextToday updates the local cache and returns the wording of query as of today.
func (c *Client) LawTextToday(ctx context.Context, query string) (*Law, error) {
	return c.LawText(ctx, query, c.today())
}

func (c *Client) lawText(ctx context.Context, query, norm string, date time.Time, update bool) (*Law, error) {
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
	var text string
	if strings.TrimSpace(norm) == "" {
		text, err = xmltext.RenderLaw(match.Title, rendered)
	} else {
		text, err = xmltext.RenderLawNorm(match.Title, rendered, norm)
	}
	if err != nil {
		if errors.Is(err, xmltext.ErrNormNotFound) {
			return nil, fmt.Errorf("%w: %s %s", errs.NormNotFound, query, norm)
		}
		return nil, err
	}
	return &Law{
		Query:    query,
		ID:       match.ID,
		Title:    match.Title,
		Norm:     strings.TrimSpace(norm),
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
