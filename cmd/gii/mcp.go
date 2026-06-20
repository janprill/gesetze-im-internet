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
	addr := fs.String("addr", "127.0.0.1:8080", "Listen address for --transport http or sse (loopback only by default)")
	todayValue := fs.String("today", "", "Test-/Automationshilfe: heutiges Datum im Format YYYY-MM-DD")
	authToken := fs.String("auth-token", "", "Bearer token required for HTTP/SSE transports (empty = no auth)")
	allowRemote := fs.Bool("allow-remote", false, "Allow binding to non-loopback addresses (use with caution)")
	rateLimit := fs.Int("rate-limit", 120, "Max requests per minute per client IP for HTTP/SSE (0 = unlimited)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if fs.NArg() != 0 {
		return fmt.Errorf("usage: gii mcp [--transport stdio|http|sse] [--addr 127.0.0.1:8080] [--auth-token TOKEN] [--allow-remote] [--rate-limit N] [flags]")
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
		return mcpserver.ServeStreamableHTTP(ctx, server, *addr, mcpserver.HTTPOptions{
			AuthToken:       *authToken,
			AllowRemoteHost:  *allowRemote,
			RateLimitPerMin: *rateLimit,
		})
	case "sse":
		return mcpserver.ServeSSE(ctx, server, *addr, mcpserver.HTTPOptions{
			AuthToken:       *authToken,
			AllowRemoteHost:  *allowRemote,
			RateLimitPerMin: *rateLimit,
		})
	default:
		return fmt.Errorf("unsupported MCP transport %q (want stdio, http, or sse)", *transportValue)
	}
}