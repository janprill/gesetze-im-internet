// Package gii provides stichtagsbezogenen Zugriff auf die XML-Daten des
// Gesetze-im-Internet data-Branches und rendert Gesetze als Plaintext.
//
// Der Client verwaltet einen lokalen Git-Cache, aktualisiert ihn per fetch und
// wählt den neuesten data-Branch-Commit am oder vor dem gewünschten Datum aus.
package gii
