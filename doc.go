// Package gii provides stichtagsbezogenen Zugriff auf die XML-Daten des
// Gesetze-im-Internet data-Branches, rendert Gesetze als Plaintext und bietet
// lokale Discovery-Methoden für Listen- und Suchabfragen.
//
// Der Client verwaltet einen lokalen Git-Cache oder ein explizites RepositoryDir,
// aktualisiert ihn per fetch und wählt den neuesten data-Branch-Commit am oder
// vor dem gewünschten Datum aus. Standard-Datenquelle ist das öffentliche
// QuantLaw-Archiv; eigene Mirrors können über Options.RepositoryURL genutzt werden.
// Offline-Methoden mit dem Suffix WithoutUpdate lesen ausschließlich aus einem
// bereits vorhandenen Checkout und sind die Grundlage für den MCP-Server.
package gii
