// Package gii provides stichtagsbezogenen Zugriff auf die XML-Daten des
// Gesetze-im-Internet data-Branches und rendert Gesetze als Plaintext.
//
// Der Client verwaltet einen lokalen Git-Cache oder ein explizites RepositoryDir,
// aktualisiert ihn per fetch und wählt den neuesten data-Branch-Commit am oder
// vor dem gewünschten Datum aus. Standard-Datenquelle ist das öffentliche
// QuantLaw-Archiv; eigene Mirrors können über Options.RepositoryURL genutzt werden.
package gii
