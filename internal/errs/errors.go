package errs

import "errors"

var (
	LawNotFound      = errors.New("law not found")
	RevisionNotFound = errors.New("revision not found")
)
