package gii

import (
	"context"
	"time"

	"github.com/janprill/gii/internal/xmltext"
)

type Snapshot struct {
	Revision    string    `json:"revision"`
	CommittedAt time.Time `json:"committed_at"`
	Tags        []string  `json:"tags"`
}

type StructuredNorm struct {
	JurAbk    string `json:"jurabk"`
	EnBez     string `json:"enbez"`
	Title     string `json:"title"`
	XMLPath   string `json:"xml_path"`
	BuildDate string `json:"builddate"`
	Text      string `json:"text"`
}

type StructuredLaw struct {
	Query    string           `json:"query"`
	ID       string           `json:"id"`
	Title    string           `json:"title"`
	Date     time.Time        `json:"date"`
	Revision string           `json:"revision"`
	Norms    []StructuredNorm `json:"norms"`
}

func (c *Client) ListSnapshotsWithoutUpdate(ctx context.Context) ([]Snapshot, error) {
	revisions, err := c.store.Revisions(ctx)
	if err != nil {
		return nil, err
	}
	result := make([]Snapshot, len(revisions))
	for i, revision := range revisions {
		result[i] = Snapshot{Revision: revision.Hash, CommittedAt: revision.CommittedAt, Tags: append([]string(nil), revision.Tags...)}
	}
	return result, nil
}

func (c *Client) StructuredLawWithoutUpdate(ctx context.Context, query string, date time.Time) (*StructuredLaw, error) {
	if date.IsZero() {
		date = c.today()
	}
	revision, err := c.store.RevisionForDate(ctx, date)
	if err != nil {
		return nil, err
	}
	match, err := c.store.FindLaw(ctx, revision, query)
	if err != nil {
		return nil, err
	}
	documents := make([]xmltext.Document, 0, len(match.XMLFiles))
	for _, path := range match.XMLFiles {
		content, err := c.store.ShowFile(ctx, revision, path)
		if err != nil {
			return nil, err
		}
		documents = append(documents, xmltext.Document{Path: path, XML: content})
	}
	extracted, err := xmltext.ExtractStructuredNorms(documents)
	if err != nil {
		return nil, err
	}
	result := &StructuredLaw{Query: query, ID: match.ID, Title: match.Title, Date: date, Revision: revision, Norms: make([]StructuredNorm, len(extracted))}
	for i, norm := range extracted {
		result.Norms[i] = StructuredNorm{JurAbk: norm.JurAbk, EnBez: norm.EnBez, Title: norm.Title, XMLPath: norm.XMLPath, BuildDate: norm.BuildDate, Text: norm.Text}
	}
	return result, nil
}
