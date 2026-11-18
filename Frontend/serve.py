#!/usr/bin/env python3
"""Simple development server for StockShield 2.0 Frontend."""

import http.server
import socketserver
import webbrowser
import os
import sys

DEFAULT_PORT = 3000
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))

class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def log_message(self, format, *args):
        pass  # Suppress verbose access logs

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

os.chdir(FRONTEND_DIR)

port = DEFAULT_PORT
httpd = None

for p in [DEFAULT_PORT, 3001, 3002, 8080]:
    try:
        httpd = ReusableTCPServer(("", p), CORSHTTPRequestHandler)
        port = p
        break
    except OSError:
        continue

if not httpd:
    print(f"Error: Could not bind to port {DEFAULT_PORT} or fallbacks. Is another server running?")
    sys.exit(1)

print("=" * 50)
print("  StockShield 2.0 - Frontend Dev Server")
print("=" * 50)
print(f"  Frontend: http://localhost:{port}")
print(f"  Backend:  http://localhost:8000")
print("=" * 50)
print(f"Serving at http://localhost:{port}")
print("Press Ctrl+C to stop.\n")

try:
    webbrowser.open(f"http://localhost:{port}")
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServer stopped.")
    httpd.server_close()
