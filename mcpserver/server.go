// Package mcpserver exposes gii as a Model Context Protocol server.
package mcpserver

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/janprill/gii"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const (
	// Name is the MCP server implementation name.
	Name = "gii"

	// Version is the MCP server implementation version. Releases may override this at build time later.
	Version = "dev"

	defaultDiscoveryLimit = 50
	maxDiscoveryLimit     = 200
)

const serverInstructions = `gii stellt deutsche Gesetze/Rechtsverordnungen aus dem lokalen Gesetze-im-Internet-Datencheckout bereit.

Nutzung für LLMs:
- Für eine einzelne Vorschrift immer norm_text bevorzugen (token-sparsam), z.B. query="BGB", norm="280".
- Für einen vollständigen Gesetzestext law_text verwenden; law_text kann mit norm ebenfalls eine Einzelnorm liefern.
- Wenn die richtige Abkürzung/ID unklar ist, zuerst search_laws verwenden; für Browsing list_laws mit limit/offset nutzen.
- date ist optional und hat immer das Format YYYY-MM-DD. Ohne date wird das vom Server konfigurierte heutige Datum verwendet.
- Read-Tools arbeiten offline und führen kein implizites git fetch aus. Bei local_cache_missing update_cache aufrufen oder den Checkout extern per gii update aktualisieren.
- Ergebnisse enthalten Plaintext sowie strukturierte Metadaten wie id, title, date, revision und xml_files. Die revision für reproduzierbare Antworten zitieren/protokollieren.
- Der Stichtag bezieht sich auf Archivierungs-Commits im data-Branch, nicht zwingend auf das juristische Inkrafttreten einzelner Änderungen.`

// New returns an MCP server exposing gii tools. Read tools use only the local checkout;
// call gii update or the update_cache tool explicitly to refresh data.
func New(client *gii.Client) *mcp.Server {
	if client == nil {
		panic("nil gii client")
	}
	tools := &toolset{client: client}
	server := mcp.NewServer(&mcp.Implementation{Name: Name, Version: Version}, &mcp.ServerOptions{Instructions: serverInstructions})
	mcp.AddTool(server, &mcp.Tool{
		Name:  "law_text",
		Title: "Gesetzestext abrufen",
		Description: "Ruft den Plaintext eines ganzen Gesetzes aus dem lokalen gii-Datencheckout ab; optional mit norm nur eine einzelne Vorschrift. " +
			"Eingaben: query = Gesetze-im-Internet-ID, amtliche Abkürzung oder Titel (z.B. BGB); date optional im Format YYYY-MM-DD; norm optional (z.B. 280 oder § 280). " +
			"Für einzelne Vorschriften nach Möglichkeit norm_text bevorzugen. Führt kein implizites Update/fetch aus.",
		Annotations: readOnlyAnnotations("Gesetzestext abrufen"),
	}, tools.lawText)
	mcp.AddTool(server, &mcp.Tool{
		Name:  "norm_text",
		Title: "Einzelnorm abrufen",
		Description: "Token-sparsamer Abruf genau einer einzelnen Norm eines Gesetzes aus dem lokalen gii-Datencheckout. " +
			"Verwenden, wenn eine Frage nach einem Paragraphen/Artikel gestellt wird, z.B. query=BGB und norm=280 oder § 280. " +
			"date ist optional im Format YYYY-MM-DD. Führt kein implizites Update/fetch aus.",
		Annotations: readOnlyAnnotations("Einzelnorm abrufen"),
	}, tools.normText)
	mcp.AddTool(server, &mcp.Tool{
		Name:  "list_laws",
		Title: "Gesetze listen",
		Description: "Listet verfügbare Gesetze/Rechtsverordnungen aus dem lokalen gii-Datencheckout zum Stichtag. " +
			"Für Browsing/Pagination verwenden; Eingaben: date optional YYYY-MM-DD, limit default 50/max 200, offset nullbasiert. Führt kein implizites Update/fetch aus.",
		Annotations: readOnlyAnnotations("Gesetze listen"),
	}, tools.listLaws)
	mcp.AddTool(server, &mcp.Tool{
		Name:  "search_laws",
		Title: "Gesetze suchen",
		Description: "Sucht Gesetze/Rechtsverordnungen nach ID, Titel oder exakter XML-Abkürzung im lokalen gii-Datencheckout. " +
			"Verwenden, wenn query für law_text/norm_text unklar ist, z.B. Suche nach Bürgerliches Gesetzbuch, BGB oder bgb. " +
			"Eingaben: query, optional date YYYY-MM-DD, limit default 50/max 200, offset. Führt kein implizites Update/fetch aus.",
		Annotations: readOnlyAnnotations("Gesetze suchen"),
	}, tools.searchLaws)
	mcp.AddTool(server, &mcp.Tool{
		Name:  "update_cache",
		Title: "gii-Datencheckout aktualisieren",
		Description: "Aktualisiert den konfigurierten lokalen gii-Datencheckout explizit per git clone/fetch. " +
			"Aufrufen, wenn Read-Tools local_cache_missing melden oder bewusst ein frischer Datenstand benötigt wird. Für regelmäßige Automatisierung wird gii update per Cron empfohlen.",
		Annotations: updateAnnotations("gii-Datencheckout aktualisieren"),
	}, tools.updateCache)
	server.AddPrompt(&mcp.Prompt{
		Name:        "gii_usage",
		Title:       "gii MCP Nutzungshilfe",
		Description: "Kurzanleitung für LLMs zur effizienten Nutzung der gii-MCP-Tools.",
	}, giiUsagePrompt)
	return server
}

func giiUsagePrompt(context.Context, *mcp.GetPromptRequest) (*mcp.GetPromptResult, error) {
	return &mcp.GetPromptResult{
		Description: "Kurzanleitung für die gii-MCP-Tools",
		Messages: []*mcp.PromptMessage{{
			Role:    "user",
			Content: &mcp.TextContent{Text: serverInstructions},
		}},
	}, nil
}

// ServeStdio serves one MCP session over stdin/stdout.
func ServeStdio(ctx context.Context, server *mcp.Server) error {
	return server.Run(ctx, &mcp.StdioTransport{})
}

// ServeStreamableHTTP serves MCP over Streamable HTTP at addr.
func ServeStreamableHTTP(ctx context.Context, server *mcp.Server, addr string) error {
	if strings.TrimSpace(addr) == "" {
		return fmt.Errorf("addr must not be empty")
	}
	handler := mcp.NewStreamableHTTPHandler(func(*http.Request) *mcp.Server { return server }, &mcp.StreamableHTTPOptions{Stateless: true})
	return serveHTTP(ctx, addr, handler)
}

// ServeSSE serves MCP over the legacy HTTP/SSE transport at addr.
func ServeSSE(ctx context.Context, server *mcp.Server, addr string) error {
	if strings.TrimSpace(addr) == "" {
		return fmt.Errorf("addr must not be empty")
	}
	handler := mcp.NewSSEHandler(func(*http.Request) *mcp.Server { return server }, nil)
	return serveHTTP(ctx, addr, handler)
}

type toolset struct {
	client *gii.Client
}

type lawTextInput struct {
	Query string `json:"query" jsonschema:"Gesetz-ID, amtliche Abkürzung oder Titel, z.B. BGB"`
	Norm  string `json:"norm,omitempty" jsonschema:"Optionale Einzelnorm, z.B. 280 oder § 280. Ohne norm wird der ganze Gesetzestext geliefert."`
	Date  string `json:"date,omitempty" jsonschema:"Optionaler Stichtag im Format YYYY-MM-DD; default ist heute gemäß Server-Konfiguration"`
}

type normTextInput struct {
	Query string `json:"query" jsonschema:"Gesetz-ID, amtliche Abkürzung oder Titel, z.B. BGB"`
	Norm  string `json:"norm" jsonschema:"Einzelnorm, z.B. 280 oder § 280"`
	Date  string `json:"date,omitempty" jsonschema:"Optionaler Stichtag im Format YYYY-MM-DD; default ist heute gemäß Server-Konfiguration"`
}

type lawTextOutput struct {
	Query    string   `json:"query"`
	ID       string   `json:"id"`
	Title    string   `json:"title"`
	Norm     string   `json:"norm,omitempty"`
	Date     string   `json:"date"`
	Revision string   `json:"revision"`
	XMLFiles []string `json:"xml_files"`
	Text     string   `json:"text"`
}

type discoveryInput struct {
	Date   string `json:"date,omitempty" jsonschema:"Optionaler Stichtag im Format YYYY-MM-DD; default ist heute gemäß Server-Konfiguration"`
	Limit  int    `json:"limit,omitempty" jsonschema:"Maximale Anzahl Treffer; default 50, Maximum 200"`
	Offset int    `json:"offset,omitempty" jsonschema:"Nullbasierter Offset für Pagination"`
}

type searchInput struct {
	Query  string `json:"query" jsonschema:"Suchbegriff für Gesetz-ID, Titel oder exakte XML-Abkürzung, z.B. BGB"`
	Date   string `json:"date,omitempty" jsonschema:"Optionaler Stichtag im Format YYYY-MM-DD; default ist heute gemäß Server-Konfiguration"`
	Limit  int    `json:"limit,omitempty" jsonschema:"Maximale Anzahl Treffer; default 50, Maximum 200"`
	Offset int    `json:"offset,omitempty" jsonschema:"Nullbasierter Offset für Pagination"`
}

type discoveryOutput struct {
	Query    string          `json:"query,omitempty"`
	Date     string          `json:"date"`
	Revision string          `json:"revision"`
	Total    int             `json:"total"`
	Limit    int             `json:"limit"`
	Offset   int             `json:"offset"`
	Laws     []lawInfoOutput `json:"laws"`
}

type lawInfoOutput struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	Link  string `json:"link,omitempty"`
}

type updateCacheInput struct{}

type updateCacheOutput struct {
	Updated bool   `json:"updated"`
	Message string `json:"message"`
}

func (t *toolset) lawText(ctx context.Context, _ *mcp.CallToolRequest, input lawTextInput) (*mcp.CallToolResult, lawTextOutput, error) {
	return t.lookupText(ctx, input.Query, input.Norm, input.Date, false)
}

func (t *toolset) normText(ctx context.Context, _ *mcp.CallToolRequest, input normTextInput) (*mcp.CallToolResult, lawTextOutput, error) {
	return t.lookupText(ctx, input.Query, input.Norm, input.Date, true)
}

func (t *toolset) lookupText(ctx context.Context, query, norm, dateValue string, requireNorm bool) (*mcp.CallToolResult, lawTextOutput, error) {
	if strings.TrimSpace(query) == "" {
		return nil, lawTextOutput{}, toolError("invalid_query", "query must not be empty", nil)
	}
	if requireNorm && strings.TrimSpace(norm) == "" {
		return nil, lawTextOutput{}, toolError("invalid_norm", "norm must not be empty", nil)
	}
	date, err := parseToolDate(dateValue)
	if err != nil {
		return nil, lawTextOutput{}, err
	}
	var law *gii.Law
	if strings.TrimSpace(norm) == "" {
		law, err = t.client.LawTextWithoutUpdate(ctx, query, date)
	} else {
		law, err = t.client.LawNormTextWithoutUpdate(ctx, query, norm, date)
	}
	if err != nil {
		return nil, lawTextOutput{}, mapReadError(err)
	}
	output := lawTextOutput{
		Query:    law.Query,
		ID:       law.ID,
		Title:    law.Title,
		Norm:     law.Norm,
		Date:     law.Date.Format("2006-01-02"),
		Revision: law.Revision,
		XMLFiles: append([]string(nil), law.XMLFiles...),
		Text:     law.Text,
	}
	return &mcp.CallToolResult{Content: []mcp.Content{&mcp.TextContent{Text: law.Text}}}, output, nil
}

func (t *toolset) listLaws(ctx context.Context, _ *mcp.CallToolRequest, input discoveryInput) (*mcp.CallToolResult, discoveryOutput, error) {
	date, err := parseToolDate(input.Date)
	if err != nil {
		return nil, discoveryOutput{}, err
	}
	limit, offset, err := normalizePagination(input.Limit, input.Offset)
	if err != nil {
		return nil, discoveryOutput{}, err
	}
	result, err := t.client.ListLawsWithoutUpdate(ctx, date, limit, offset)
	if err != nil {
		return nil, discoveryOutput{}, mapReadError(err)
	}
	return nil, discoveryOutputFromResult(result), nil
}

func (t *toolset) searchLaws(ctx context.Context, _ *mcp.CallToolRequest, input searchInput) (*mcp.CallToolResult, discoveryOutput, error) {
	if strings.TrimSpace(input.Query) == "" {
		return nil, discoveryOutput{}, toolError("invalid_query", "query must not be empty", nil)
	}
	date, err := parseToolDate(input.Date)
	if err != nil {
		return nil, discoveryOutput{}, err
	}
	limit, offset, err := normalizePagination(input.Limit, input.Offset)
	if err != nil {
		return nil, discoveryOutput{}, err
	}
	result, err := t.client.SearchLawsWithoutUpdate(ctx, input.Query, date, limit, offset)
	if err != nil {
		return nil, discoveryOutput{}, mapReadError(err)
	}
	return nil, discoveryOutputFromResult(result), nil
}

func (t *toolset) updateCache(ctx context.Context, _ *mcp.CallToolRequest, _ updateCacheInput) (*mcp.CallToolResult, updateCacheOutput, error) {
	if err := t.client.Update(ctx); err != nil {
		return nil, updateCacheOutput{}, toolError("update_failed", "failed to update local gii cache", err)
	}
	return nil, updateCacheOutput{Updated: true, Message: "local gii cache updated"}, nil
}

func parseToolDate(value string) (time.Time, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		return time.Time{}, nil
	}
	date, err := time.Parse("2006-01-02", value)
	if err != nil {
		return time.Time{}, toolError("invalid_date", "date must use YYYY-MM-DD", err)
	}
	return date, nil
}

func normalizePagination(limit, offset int) (int, int, error) {
	if limit < 0 {
		return 0, 0, toolError("invalid_limit", "limit must be >= 0", nil)
	}
	if offset < 0 {
		return 0, 0, toolError("invalid_offset", "offset must be >= 0", nil)
	}
	if limit == 0 {
		limit = defaultDiscoveryLimit
	}
	if limit > maxDiscoveryLimit {
		return 0, 0, toolError("invalid_limit", fmt.Sprintf("limit must be <= %d", maxDiscoveryLimit), nil)
	}
	return limit, offset, nil
}

func discoveryOutputFromResult(result *gii.LawDiscoveryResult) discoveryOutput {
	laws := make([]lawInfoOutput, len(result.Laws))
	for i, law := range result.Laws {
		laws[i] = lawInfoOutput{ID: law.ID, Title: law.Title, Link: law.Link}
	}
	return discoveryOutput{
		Query:    result.Query,
		Date:     result.Date.Format("2006-01-02"),
		Revision: result.Revision,
		Total:    result.Total,
		Limit:    result.Limit,
		Offset:   result.Offset,
		Laws:     laws,
	}
}

type codedError struct {
	code    string
	message string
	err     error
}

func toolError(code, message string, err error) error {
	return codedError{code: code, message: message, err: err}
}

func (e codedError) Error() string {
	if e.err == nil {
		return e.code + ": " + e.message
	}
	return e.code + ": " + e.message + ": " + e.err.Error()
}

func (e codedError) Unwrap() error { return e.err }

func mapReadError(err error) error {
	switch {
	case errors.Is(err, gii.ErrLocalCacheMissing):
		return toolError("local_cache_missing", "local gii data checkout is missing; run `gii update --repo-dir ...` or call update_cache first", err)
	case errors.Is(err, gii.ErrRevisionNotFound):
		return toolError("revision_not_found", "no local data revision exists at or before the requested date", err)
	case errors.Is(err, gii.ErrNormNotFound):
		return toolError("norm_not_found", "individual norm could not be resolved for the requested law", err)
	case errors.Is(err, gii.ErrLawNotFound):
		return toolError("law_not_found", "law could not be resolved for the requested query", err)
	default:
		return toolError("read_failed", "failed to read local gii data checkout", err)
	}
}

func readOnlyAnnotations(title string) *mcp.ToolAnnotations {
	closedWorld := false
	return &mcp.ToolAnnotations{
		Title:         title,
		ReadOnlyHint:  true,
		OpenWorldHint: &closedWorld,
	}
}

func updateAnnotations(title string) *mcp.ToolAnnotations {
	notDestructive := false
	openWorld := true
	return &mcp.ToolAnnotations{
		Title:           title,
		ReadOnlyHint:    false,
		DestructiveHint: &notDestructive,
		IdempotentHint:  true,
		OpenWorldHint:   &openWorld,
	}
}

func serveHTTP(ctx context.Context, addr string, handler http.Handler) error {
	srv := &http.Server{Addr: addr, Handler: handler}
	errc := make(chan error, 1)
	go func() {
		err := srv.ListenAndServe()
		if errors.Is(err, http.ErrServerClosed) {
			err = nil
		}
		errc <- err
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := srv.Shutdown(shutdownCtx); err != nil {
			return err
		}
		return ctx.Err()
	case err := <-errc:
		return err
	}
}
