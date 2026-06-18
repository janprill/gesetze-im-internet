package gii

import (
	"context"
	"fmt"
	"time"

	"github.com/janprill/gii/internal/gitrepo"
)

// LawInfo is compact metadata for one law or ordinance from data/toc.xml.
type LawInfo struct {
	// ID is the gesetze-im-internet directory id, e.g. "bgb".
	ID string `json:"id"`

	// Title is the title from data/toc.xml when available.
	Title string `json:"title"`

	// Link is the XML ZIP link from data/toc.xml.
	Link string `json:"link,omitempty"`
}

// LawDiscoveryResult contains paginated discovery results from a selected data-branch revision.
type LawDiscoveryResult struct {
	// Query is set for search results and empty for list results.
	Query string `json:"query,omitempty"`

	// Date is the requested effective/as-of date.
	Date time.Time `json:"date"`

	// Revision is the git commit hash that was selected for Date.
	Revision string `json:"revision"`

	// Total is the number of matches before limit/offset pagination.
	Total int `json:"total"`

	// Limit is the requested maximum number of entries. Zero means no limit.
	Limit int `json:"limit"`

	// Offset is the requested zero-based start offset.
	Offset int `json:"offset"`

	// Laws are the paginated law metadata entries.
	Laws []LawInfo `json:"laws"`
}

// ListLawsWithoutUpdate returns local law metadata from the configured data checkout without fetching first.
// A zero date means today according to the configured Clock. A limit of zero means no limit.
func (c *Client) ListLawsWithoutUpdate(ctx context.Context, date time.Time, limit, offset int) (*LawDiscoveryResult, error) {
	if date.IsZero() {
		date = c.today()
	}
	rev, err := c.store.RevisionForDate(ctx, date)
	if err != nil {
		return nil, err
	}
	laws, err := c.store.ListLaws(ctx, rev)
	if err != nil {
		return nil, err
	}
	page, total, err := paginateLawInfos(convertLawInfos(laws), limit, offset)
	if err != nil {
		return nil, err
	}
	return &LawDiscoveryResult{Date: date, Revision: rev, Total: total, Limit: limit, Offset: offset, Laws: page}, nil
}

// SearchLawsWithoutUpdate searches local law metadata from the configured data checkout without fetching first.
// It matches ID, title, and exact XML jurabk abbreviations. A zero date means today according to the configured Clock.
// A limit of zero means no limit.
func (c *Client) SearchLawsWithoutUpdate(ctx context.Context, query string, date time.Time, limit, offset int) (*LawDiscoveryResult, error) {
	if date.IsZero() {
		date = c.today()
	}
	rev, err := c.store.RevisionForDate(ctx, date)
	if err != nil {
		return nil, err
	}
	laws, err := c.store.SearchLaws(ctx, rev, query)
	if err != nil {
		return nil, err
	}
	page, total, err := paginateLawInfos(convertLawInfos(laws), limit, offset)
	if err != nil {
		return nil, err
	}
	return &LawDiscoveryResult{Query: query, Date: date, Revision: rev, Total: total, Limit: limit, Offset: offset, Laws: page}, nil
}

func convertLawInfos(in []gitrepo.LawInfo) []LawInfo {
	out := make([]LawInfo, len(in))
	for i, law := range in {
		out[i] = LawInfo{ID: law.ID, Title: law.Title, Link: law.Link}
	}
	return out
}

func paginateLawInfos(laws []LawInfo, limit, offset int) ([]LawInfo, int, error) {
	if limit < 0 {
		return nil, 0, fmt.Errorf("limit must be >= 0")
	}
	if offset < 0 {
		return nil, 0, fmt.Errorf("offset must be >= 0")
	}
	total := len(laws)
	if offset >= total {
		return []LawInfo{}, total, nil
	}
	end := total
	if limit > 0 && offset+limit < end {
		end = offset + limit
	}
	return append([]LawInfo(nil), laws[offset:end]...), total, nil
}
