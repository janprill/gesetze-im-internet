package gii

import "github.com/janprill/gii/internal/errs"

var (
	// ErrLawNotFound is returned when no law can be resolved for a query at the selected revision.
	ErrLawNotFound = errs.LawNotFound

	// ErrNormNotFound is returned when no norm locator can be resolved inside a law.
	ErrNormNotFound = errs.NormNotFound

	// ErrRevisionNotFound is returned when the data branch has no commit at or before the selected date.
	ErrRevisionNotFound = errs.RevisionNotFound
)
