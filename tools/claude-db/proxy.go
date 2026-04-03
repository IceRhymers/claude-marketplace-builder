package main

import (
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
)

// ProxyConfig holds the configuration for the proxy server.
type ProxyConfig struct {
	InferenceUpstream string
	OTELUpstream      string
	UCTable           string
	TokenProvider     *TokenProvider
	Verbose           bool
}

// recoveryHandler wraps h with panic recovery, returning 502 on panic.
func recoveryHandler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("claude-db: proxy panic recovered: %v", err)
				http.Error(w, "Internal proxy error", http.StatusBadGateway)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// NewProxyServer returns an http.Handler that routes requests to the
// inference upstream (default) and the OTEL upstream (/otel/).
func NewProxyServer(config *ProxyConfig) http.Handler {
	mux := http.NewServeMux()

	inferenceUpstream, err := url.Parse(config.InferenceUpstream)
	if err != nil {
		log.Fatalf("claude-db: invalid InferenceUpstream %q: %v", config.InferenceUpstream, err)
	}

	otelUpstream, err := url.Parse(config.OTELUpstream)
	if err != nil {
		log.Fatalf("claude-db: invalid OTELUpstream %q: %v", config.OTELUpstream, err)
	}

	// Inference proxy — default route
	inferenceProxy := &httputil.ReverseProxy{
		Director: func(req *http.Request) {
			token, err := config.TokenProvider.Token(req.Context())
			if err != nil {
				// Log the error but let the upstream return an auth failure rather
				// than crashing; the empty bearer will be rejected by the upstream.
				log.Printf("claude-db: token fetch error: %v", err)
			}
			req.Header.Set("Authorization", "Bearer "+token)
			req.Header.Set("x-databricks-use-coding-agent-mode", "true")

			req.URL.Scheme = inferenceUpstream.Scheme
			req.URL.Host = inferenceUpstream.Host
			// Prepend the upstream base path to the incoming request path.
			basePath := strings.TrimRight(inferenceUpstream.Path, "/")
			req.URL.Path = basePath + req.URL.Path
			req.URL.RawPath = ""

			if config.Verbose {
				log.Printf("claude-db: inference → %s %s%s", req.Method, req.URL.Host, req.URL.Path)
			}
		},
		FlushInterval: -1,
	}

	// OTEL proxy — /otel/ route
	otelProxy := &httputil.ReverseProxy{
		Director: func(req *http.Request) {
			token, err := config.TokenProvider.Token(req.Context())
			if err != nil {
				log.Printf("claude-db: token fetch error (otel): %v", err)
			}
			req.Header.Set("Authorization", "Bearer "+token)
			req.Header.Set("X-Databricks-UC-Table-Name", config.UCTable)

			// Strip the /otel prefix and prepend the upstream base path.
			stripped := strings.TrimPrefix(req.URL.Path, "/otel")
			basePath := strings.TrimRight(otelUpstream.Path, "/")
			req.URL.Scheme = otelUpstream.Scheme
			req.URL.Host = otelUpstream.Host
			req.URL.Path = basePath + stripped
			req.URL.RawPath = ""

			if config.Verbose {
				log.Printf("claude-db: otel → %s %s%s", req.Method, req.URL.Host, req.URL.Path)
			}
		},
		FlushInterval: -1,
	}

	mux.Handle("/otel/", recoveryHandler(otelProxy))
	mux.Handle("/", recoveryHandler(inferenceProxy))

	return mux
}

// StartProxy binds to 127.0.0.1:0, starts serving, and returns the listener.
// Callers read l.Addr() to discover the assigned port.
func StartProxy(handler http.Handler) (net.Listener, error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, err
	}
	go func() {
		if err := http.Serve(l, handler); err != nil {
			// http.Serve returns when the listener is closed; that is expected
			// during shutdown and not worth logging as an error.
			log.Printf("claude-db: proxy stopped: %v", err)
		}
	}()
	return l, nil
}
