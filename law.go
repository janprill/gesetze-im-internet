package gii

import "time"

// Law is the rendered wording of one law at a data-branch revision.
type Law struct {
	// Query is the original lookup string supplied by the caller.
	Query string

	// ID is the gesetze-im-internet directory id, e.g. "bgb".
	ID string

	// Title is the title from data/toc.xml when available.
	Title string

	// Date is the requested effective/as-of date.
	Date time.Time

	// Revision is the git commit hash that was selected for Date.
	Revision string

	// XMLFiles are the XML files that were rendered.
	XMLFiles []string

	// Text is a plain-text rendering of the law's XML wording.
	Text string
}
