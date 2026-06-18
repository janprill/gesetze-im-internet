package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"strings"

	"github.com/janprill/gii"
	"github.com/janprill/gii/mcpserver"
)

func runMCP(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("gii mcp", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	common := addCommonFlags(fs)
	transportValue := fs.String("transport", "stdio", "MCP transport: stdio, http (streamable HTTP), or sse")
	addr := fs.String("addr", "127.0.0.1:8080", "Listen address for --transport http or sse")
	todayValue := fs.String("today", "", "Test-/Automationshilfe: heutiges Datum im Format YYYY-MM-DD")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if fs.NArg() != 0 {
		return fmt.Errorf("usage: gii mcp [--transport stdio|http|sse] [--addr 127.0.0.1:8080] [flags]")
	}
	clock, err := clockFromToday(*todayValue)
	if err != nil {
		return err
	}
	client := gii.New(common.options(clock))
	server := mcpserver.New(client)

	switch strings.ToLower(strings.TrimSpace(*transportValue)) {
	case "", "stdio":
		return mcpserver.ServeStdio(ctx, server)
	case "http", "streamable", "streamable-http":
		return mcpserver.ServeStreamableHTTP(ctx, server, *addr)
	case "sse":
		return mcpserver.ServeSSE(ctx, server, *addr)
	default:
		return fmt.Errorf("unsupported MCP transport %q (want stdio, http, or sse)", *transportValue)
	}
}
