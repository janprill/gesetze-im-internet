package errs

import "errors"

var (
	LawNotFound       = errors.New("law not found")
	NormNotFound      = errors.New("norm not found")
	RevisionNotFound  = errors.New("revision not found")
	LocalCacheMissing = errors.New("local cache missing")
)
