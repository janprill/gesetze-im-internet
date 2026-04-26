package xmltext

import (
	"encoding/xml"
	"fmt"
	"io"
	"sort"
	"strings"
)

type Document struct {
	Path string
	XML  string
}

type norm struct {
	Metadata struct {
		JurAbk string `xml:"jurabk"`
		EnBez  string `xml:"enbez"`
		Title  inner  `xml:"titel"`
		Unit   struct {
			Bez   string `xml:"gliederungsbez"`
			Title string `xml:"gliederungstitel"`
		} `xml:"gliederungseinheit"`
	} `xml:"metadaten"`
	TextData struct {
		Text struct {
			Content inner `xml:"Content"`
		} `xml:"text"`
		Footnotes struct {
			Content inner `xml:"Content"`
		} `xml:"fussnoten"`
	} `xml:"textdaten"`
}

type inner struct {
	XML string `xml:",innerxml"`
}

func RenderLaw(title string, documents []Document) (string, error) {
	sort.SliceStable(documents, func(i, j int) bool { return documents[i].Path < documents[j].Path })
	var b strings.Builder
	if strings.TrimSpace(title) != "" {
		b.WriteString(strings.TrimSpace(title))
		b.WriteString("\n\n")
	}
	for _, document := range documents {
		parts, err := renderDocument(document.XML)
		if err != nil {
			return "", fmt.Errorf("render %s: %w", document.Path, err)
		}
		for _, part := range parts {
			if part == "" {
				continue
			}
			if b.Len() > 0 && !strings.HasSuffix(b.String(), "\n\n") {
				b.WriteString("\n\n")
			}
			b.WriteString(part)
		}
	}
	return strings.TrimSpace(b.String()) + "\n", nil
}

func renderDocument(contents string) ([]string, error) {
	decoder := xml.NewDecoder(strings.NewReader(contents))
	decoder.Strict = false
	decoder.Entity = xml.HTMLEntity
	var rendered []string
	for {
		token, err := decoder.Token()
		if err == io.EOF {
			return rendered, nil
		}
		if err != nil {
			return nil, err
		}
		start, ok := token.(xml.StartElement)
		if !ok || start.Name.Local != "norm" {
			continue
		}
		var n norm
		if err := decoder.DecodeElement(&n, &start); err != nil {
			return nil, err
		}
		text := renderNorm(n)
		if text != "" {
			rendered = append(rendered, text)
		}
	}
}

func renderNorm(n norm) string {
	var lines []string
	heading := strings.TrimSpace(strings.Join(nonEmpty(
		n.Metadata.Unit.Bez,
		n.Metadata.Unit.Title,
	), " "))
	if heading == "" {
		heading = strings.TrimSpace(strings.Join(nonEmpty(
			n.Metadata.EnBez,
			fragmentText(n.Metadata.Title.XML),
		), " "))
	}
	if heading != "" {
		lines = append(lines, heading)
	}
	body := fragmentText(n.TextData.Text.Content.XML)
	if body != "" {
		lines = append(lines, splitParagraphs(body)...)
	}
	footnotes := fragmentText(n.TextData.Footnotes.Content.XML)
	if footnotes != "" {
		lines = append(lines, "Fußnoten:")
		lines = append(lines, splitParagraphs(footnotes)...)
	}
	return strings.Join(lines, "\n")
}

func fragmentText(fragment string) string {
	fragment = strings.TrimSpace(fragment)
	if fragment == "" {
		return ""
	}
	decoder := xml.NewDecoder(strings.NewReader("<root>" + fragment + "</root>"))
	decoder.Strict = false
	decoder.Entity = xml.HTMLEntity
	var b strings.Builder
	newlinePending := false
	spacePending := false
	for {
		token, err := decoder.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			return strings.TrimSpace(stripTagsFallback(fragment))
		}
		switch t := token.(type) {
		case xml.StartElement:
			switch t.Name.Local {
			case "P", "BR", "DL", "DT", "DD", "Footnote":
				newlinePending = b.Len() > 0
			case "LA", "I", "B", "SUP", "SUB":
				spacePending = b.Len() > 0
			}
		case xml.EndElement:
			switch t.Name.Local {
			case "P", "DT", "DD", "Footnote":
				newlinePending = b.Len() > 0
			}
		case xml.CharData:
			words := strings.Fields(string(t))
			if len(words) == 0 {
				continue
			}
			if newlinePending {
				appendNewline(&b)
				newlinePending = false
				spacePending = false
			} else if spacePending && b.Len() > 0 && !strings.HasSuffix(b.String(), "\n") {
				b.WriteByte(' ')
				spacePending = false
			}
			for i, word := range words {
				if i > 0 || needsSpace(b.String()) {
					b.WriteByte(' ')
				}
				b.WriteString(word)
			}
		}
	}
	return strings.TrimSpace(compactBlankLines(b.String()))
}

func splitParagraphs(value string) []string {
	var out []string
	for _, part := range strings.Split(compactBlankLines(value), "\n") {
		part = strings.TrimSpace(part)
		if part != "" && part != "-" {
			out = append(out, part)
		}
	}
	return out
}

func nonEmpty(values ...string) []string {
	out := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value != "" {
			out = append(out, value)
		}
	}
	return out
}

func appendNewline(b *strings.Builder) {
	current := b.String()
	if strings.HasSuffix(current, "\n") {
		return
	}
	b.WriteByte('\n')
}

func needsSpace(current string) bool {
	if current == "" || strings.HasSuffix(current, "\n") || strings.HasSuffix(current, " ") {
		return false
	}
	return true
}

func compactBlankLines(value string) string {
	lines := strings.Split(value, "\n")
	out := make([]string, 0, len(lines))
	lastBlank := false
	for _, line := range lines {
		line = strings.Join(strings.Fields(line), " ")
		blank := line == ""
		if blank && lastBlank {
			continue
		}
		out = append(out, line)
		lastBlank = blank
	}
	return strings.TrimSpace(strings.Join(out, "\n"))
}

func stripTagsFallback(fragment string) string {
	var b strings.Builder
	inside := false
	for _, r := range fragment {
		switch r {
		case '<':
			inside = true
			b.WriteByte(' ')
		case '>':
			inside = false
			b.WriteByte(' ')
		default:
			if !inside {
				b.WriteRune(r)
			}
		}
	}
	return strings.Join(strings.Fields(b.String()), " ")
}
