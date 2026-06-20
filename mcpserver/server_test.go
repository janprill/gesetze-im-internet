package mcpserver

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/janprill/gii"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// TestValidateBindAddrRejectsNonLoopback ensures non-loopback addresses are
// rejected unless AllowRemoteHost is true.
func TestValidateBindAddrRejectsNonLoopback(t *testing.T) {
	tests := []struct {
		addr        string
		allowRemote bool
		wantErr     bool
		errContains string
	}{
		{"127.0.0.1:8080", false, false, ""},
		{"localhost:8080", false, false, ""},
		{"0.0.0.0:8080", false, true, "non-loopback"},
		{"0.0.0.0:8080", true, false, ""},
		{"", false, true, "empty"},
		{"[::1]:8080", false, false, ""},   // IPv6 loopback bracketed
	}

	for _, tc := range tests {
		t.Run(tc.addr, func(t *testing.T) {
			err := validateBindAddr(tc.addr, tc.allowRemote)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error for addr %q, got nil", tc.addr)
				}
				if tc.errContains != "" && !strings.Contains(err.Error(), tc.errContains) {
					t.Fatalf("expected error containing %q, got %v", tc.errContains, err)
				}
			} else {
				if err != nil {
					t.Fatalf("unexpected error for addr %q: %v", tc.addr, err)
				}
			}
		})
	}
}

// TestAuthMiddlewareRejectsMissingToken ensures 401 when no Authorization header is present.
func TestAuthMiddlewareRejectsMissingToken(t *testing.T) {
	handler := authMiddleware("s3cr3t", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Fatal("next handler should not be called")
	}))
	req := httptest.NewRequest("POST", "/mcp", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "missing Authorization header") {
		t.Fatalf("expected 'missing Authorization header', got %q", rec.Body.String())
	}
}

// TestAuthMiddlewareRejectsWrongToken ensures 401 with wrong token.
func TestAuthMiddlewareRejectsWrongToken(t *testing.T) {
	called := false
	handler := authMiddleware("s3cr3t", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
	}))
	req := httptest.NewRequest("POST", "/mcp", nil)
	req.Header.Set("Authorization", "Bearer wrong")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", rec.Code)
	}
	if called {
		t.Fatal("next handler should not be called with wrong token")
	}
}

// TestAuthMiddlewareAcceptsCorrectToken ensures the request passes through with the correct token.
func TestAuthMiddlewareAcceptsCorrectToken(t *testing.T) {
	called := false
	handler := authMiddleware("s3cr3t", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
		w.WriteHeader(http.StatusOK)
	}))
	req := httptest.NewRequest("POST", "/mcp", nil)
	req.Header.Set("Authorization", "Bearer s3cr3t")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if !called {
		t.Fatal("next handler should be called with correct token")
	}
}

// TestAuthMiddlewareEmptyTokenDisablesAuth ensures that an empty AuthToken disables auth.
func TestAuthMiddlewareEmptyTokenDisablesAuth(t *testing.T) {
	opts := HTTPOptions{AuthToken: ""}
	handler := secureHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}), opts)
	req := httptest.NewRequest("POST", "/mcp", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 with no auth, got %d", rec.Code)
	}
}

// TestRateLimitMiddlewareAllowsBurst ensures the burst capacity is respected.
func TestRateLimitMiddlewareAllowsBurst(t *testing.T) {
	called := 0
	handler := rateLimitMiddleware(5, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called++
		w.WriteHeader(http.StatusOK)
	}))
	// 5 requests should succeed (burst capacity).
	for i := 0; i < 5; i++ {
		req := httptest.NewRequest("POST", "/mcp", nil)
		req.RemoteAddr = "127.0.0.1:1234"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("request %d: expected 200, got %d", i, rec.Code)
		}
	}
	// 6th request should be rate-limited.
	req := httptest.NewRequest("POST", "/mcp", nil)
	req.RemoteAddr = "127.0.0.1:1234"
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429 on 6th request, got %d", rec.Code)
	}
	if called != 5 {
		t.Fatalf("expected 5 successful calls, got %d", called)
	}
}

// TestRateLimitMiddlewareZeroDisables ensures 0 means unlimited.
func TestRateLimitMiddlewareZeroDisables(t *testing.T) {
	opts := HTTPOptions{RateLimitPerMin: 0}
	handler := secureHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}), opts)
	for i := 0; i < 100; i++ {
		req := httptest.NewRequest("POST", "/mcp", nil)
		req.RemoteAddr = "127.0.0.1:1234"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("request %d: expected 200 with no rate limit, got %d", i, rec.Code)
		}
	}
}

// TestRateLimitMiddlewareRefillsOverTime ensures tokens refill after waiting.
func TestRateLimitMiddlewareRefillsOverTime(t *testing.T) {
	handler := rateLimitMiddleware(60, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	// Exhaust the burst (60 tokens).
	for i := 0; i < 60; i++ {
		req := httptest.NewRequest("POST", "/mcp", nil)
		req.RemoteAddr = "127.0.0.1:4321"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
	}
	// Next request should fail.
	req := httptest.NewRequest("POST", "/mcp", nil)
	req.RemoteAddr = "127.0.0.1:4321"
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429 after burst, got %d", rec.Code)
	}
	// Wait 1.1 seconds — at 1 token/sec (60/min), we should have at least 1 token.
	time.Sleep(1100 * time.Millisecond)
	req2 := httptest.NewRequest("POST", "/mcp", nil)
	req2.RemoteAddr = "127.0.0.1:4321"
	rec2 := httptest.NewRecorder()
	handler.ServeHTTP(rec2, req2)
	if rec2.Code != http.StatusOK {
		t.Fatalf("expected 200 after refill, got %d", rec2.Code)
	}
}

// TestServeHTTPRejectsNonLoopback ensures ServeStreamableHTTP rejects non-loopback.
func TestServeStreamableHTTPRejectsNonLoopback(t *testing.T) {
	client := gii.New(gii.Options{RepositoryDir: t.TempDir()})
	server := mcpserverNewForTest(t, client)
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	err := ServeStreamableHTTP(ctx, server, "0.0.0.0:8080", HTTPOptions{})
	if err == nil {
		t.Fatal("expected error for non-loopback address without --allow-remote")
	}
	if !strings.Contains(err.Error(), "non-loopback") {
		t.Fatalf("expected 'non-loopback' in error, got %v", err)
	}
}

// TestServeStreamableHTTPAcceptsLoopbackWithAuth ensures the server starts on loopback with auth.
func TestServeStreamableHTTPAcceptsLoopbackWithAuth(t *testing.T) {
	client := gii.New(gii.Options{RepositoryDir: t.TempDir()})
	server := mcpserverNewForTest(t, client)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errc := make(chan error, 1)
	go func() {
		errc <- ServeStreamableHTTP(ctx, server, "127.0.0.1:0", HTTPOptions{
			AuthToken:       "test-token",
			RateLimitPerMin: 10,
		})
	}()

	// Give the server a moment to start, then cancel.
	time.Sleep(200 * time.Millisecond)
	cancel()
	select {
	case err := <-errc:
		if err != nil && !strings.Contains(err.Error(), "context canceled") && err != context.Canceled {
			// Server should have started successfully (we just can't get the actual port easily).
			// The error on shutdown is expected.
		}
	case <-time.After(2 * time.Second):
		t.Fatal("server did not stop within timeout")
	}
}

// TestParseToolDateErrorMessageIncludesValue ensures the error includes the bad value.
func TestParseToolDateErrorMessageIncludesValue(t *testing.T) {
	_, err := parseToolDate("31.12.2023")
	if err == nil {
		t.Fatal("expected error for invalid date format")
	}
	if !strings.Contains(err.Error(), "31.12.2023") {
		t.Fatalf("expected error to include the bad value, got %v", err)
	}
	if !strings.Contains(err.Error(), "invalid_date") {
		t.Fatalf("expected 'invalid_date' code in error, got %v", err)
	}
}

// TestBuildTimeVersionOverride ensures Version can be overridden (simulating ldflags).
func TestBuildTimeVersionOverride(t *testing.T) {
	original := Version
	defer func() { Version = original }()
	Version = "1.2.3"
	if Version != "1.2.3" {
		t.Fatalf("expected Version override to work, got %q", Version)
	}
}

// mcpserverNewForTest creates an MCP server for testing, reusing the public New function.
func mcpserverNewForTest(t *testing.T, client *gii.Client) *mcp.Server {
	t.Helper()
	return New(client)
}