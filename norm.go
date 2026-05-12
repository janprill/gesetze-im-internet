package gii

import (
	"context"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/janprill/gii/internal/errs"
	"github.com/janprill/gii/internal/xmltext"
)

var normRefPattern = regexp.MustCompile(`^§+\s*([0-9]+[a-zA-Z]?)\s+(.+)$`)

type ResolvedNorm struct {
	Query     string `json:"query"`
	Date      string `json:"date"`
	Revision  string `json:"revision"`
	LawID     string `json:"lawId"`
	LawTitle  string `json:"lawTitle"`
	JurAbk    string `json:"jurabk"`
	Locator   string `json:"locator"`
	XMLPath   string `json:"xmlPath"`
	Text      string `json:"text"`
	DokNR     string `json:"doknr,omitempty"`
	BuildDate string `json:"builddate,omitempty"`
}

type parsedNormRef struct {
	EnBez    string
	LawQuery string
}

func (c *Client) ResolveNorm(ctx context.Context, query string, date time.Time) (*ResolvedNorm, error) {
	return c.resolveNorm(ctx, query, date, true)
}

func (c *Client) ResolveNormWithoutUpdate(ctx context.Context, query string, date time.Time) (*ResolvedNorm, error) {
	return c.resolveNorm(ctx, query, date, false)
}

func (c *Client) resolveNorm(ctx context.Context, query string, date time.Time, update bool) (*ResolvedNorm, error) {
	parsed, err := parseNormRef(query)
	if err != nil {
		return nil, err
	}
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
	match, err := c.store.FindLaw(ctx, rev, parsed.LawQuery)
	if err != nil {
		return nil, err
	}
	for _, file := range match.XMLFiles {
		contents, err := c.store.ShowFile(ctx, rev, file)
		if err != nil {
			return nil, err
		}
		fragment, err := xmltext.RenderNormByEnBez(xmltext.Document{Path: file, XML: contents}, parsed.EnBez)
		if err != nil {
			return nil, err
		}
		if fragment == nil {
			continue
		}
		jurabk := fragment.JurAbk
		if jurabk == "" {
			jurabk = strings.TrimSpace(parsed.LawQuery)
		}
		return &ResolvedNorm{
			Query:     query,
			Date:      date.Format("2006-01-02"),
			Revision:  rev,
			LawID:     match.ID,
			LawTitle:  match.Title,
			JurAbk:    jurabk,
			Locator:   parsed.EnBez + " " + jurabk,
			XMLPath:   file,
			Text:      fragment.Text,
			DokNR:     fragment.DokNR,
			BuildDate: fragment.BuildDate,
		}, nil
	}
	return nil, fmt.Errorf("%w: %s in %s", errs.NormNotFound, parsed.EnBez, parsed.LawQuery)
}

func parseNormRef(query string) (parsedNormRef, error) {
	trimmed := strings.Join(strings.Fields(query), " ")
	match := normRefPattern.FindStringSubmatch(trimmed)
	if match == nil {
		return parsedNormRef{}, fmt.Errorf("%w: invalid norm reference %q", errs.NormNotFound, query)
	}
	enbez := "§ " + match[1]
	lawQuery := strings.TrimSpace(match[2])
	return parsedNormRef{
		EnBez:    enbez,
		LawQuery: lawQuery,
	}, nil
}
