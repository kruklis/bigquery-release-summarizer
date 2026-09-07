#!/usr/bin/env python3
"""
Zero-dependency HTTP Server and REST API for BigQuery Release Notes.
Serves web UI assets and provides endpoints for notes querying and AI summarization.
"""

import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

from fetcher import ReleaseNotesFetcher
from summarizer import ReleaseNotesSummarizer

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
PORT = 8080


class ReleaseNotesHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for static files and REST API."""

    fetcher = ReleaseNotesFetcher()
    summarizer = ReleaseNotesSummarizer()

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def do_OPTIONS(self):
        """CORS preflight support."""
        self._set_headers(200, "text/plain")
        self.wfile.write(b"OK")

    def _read_json_body(self) -> Dict[str, Any]:
        """Reads and parses JSON body from POST requests."""
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        post_data = self.rfile.read(content_len)
        try:
            return json.loads(post_data.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        """Handles static file requests and GET endpoints."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # API: /api/notes
        if path == "/api/notes":
            days_str = query.get("days", [None])[0]
            days = int(days_str) if days_str and days_str.isdigit() else None
            category = query.get("category", [None])[0]
            stage = query.get("stage", [None])[0]
            search = query.get("search", [None])[0]
            force_refresh = query.get("refresh", ["false"])[0].lower() == "true"

            items = self.fetcher.get_flat_items(
                force_refresh=force_refresh,
                days=days,
                category=category,
                stage=stage,
                search=search
            )
            self._set_headers(200, "application/json")
            response_payload = {
                "items": items,
                "count": len(items),
                "query": {
                    "days": days,
                    "category": category,
                    "stage": stage,
                    "search": search
                }
            }
            self.wfile.write(json.dumps(response_payload, ensure_ascii=False).encode("utf-8"))
            return

        # API: /api/stats
        if path == "/api/stats":
            stats = self.fetcher.get_stats()
            self._set_headers(200, "application/json")
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))
            return

        # API: /api/health
        if path == "/api/health":
            self._set_headers(200, "application/json")
            self.wfile.write(b'{"status":"ok"}')
            return

        # Serve static assets from web/
        clean_path = path.lstrip("/")
        if not clean_path:
            clean_path = "index.html"

        file_path = os.path.join(WEB_DIR, clean_path)

        # Prevent directory traversal
        if not os.path.abspath(file_path).startswith(WEB_DIR) or not os.path.exists(file_path):
            self._set_headers(404, "text/plain")
            self.wfile.write(b"404 Not Found")
            return

        content_types = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon"
        }
        ext = os.path.splitext(file_path)[1].lower()
        content_type = content_types.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self._set_headers(200, content_type)
            self.wfile.write(content)
        except Exception as e:
            self._set_headers(500, "text/plain")
            self.wfile.write(f"500 Internal Server Error: {e}".encode("utf-8"))

    def do_POST(self):
        """Handles POST endpoints."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # API: /api/refresh
        if path == "/api/refresh":
            try:
                entries = self.fetcher.fetch_live()
                stats = self.fetcher.get_stats()
                self._set_headers(200, "application/json")
                self.wfile.write(json.dumps({
                    "success": True,
                    "total_entries": len(entries),
                    "stats": stats
                }).encode("utf-8"))
            except Exception as e:
                self._set_headers(500, "application/json")
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        # API: /api/summarize
        if path == "/api/summarize":
            data = self._read_json_body()
            days = data.get("days")
            if days is not None:
                try:
                    days = int(days)
                except ValueError:
                    days = None

            category = data.get("category")
            stage = data.get("stage")
            search = data.get("search")
            mode = data.get("mode", "executive")
            custom_question = data.get("custom_question")
            force_offline = bool(data.get("offline", False))

            # Fetch matching items
            items = self.fetcher.get_flat_items(
                force_refresh=False,
                days=days,
                category=category,
                stage=stage,
                search=search
            )

            timeframe_desc = f"Last {days} days" if days else "All available release notes"
            if category and category.lower() != "all":
                timeframe_desc += f" | Category: {category}"
            if stage and stage.lower() != "all":
                timeframe_desc += f" | Stage: {stage}"

            result = self.summarizer.summarize(
                items=items,
                mode=mode,
                custom_question=custom_question,
                force_offline=force_offline,
                timeframe_desc=timeframe_desc
            )

            result["item_count"] = len(items)
            result["timeframe_desc"] = timeframe_desc

            self._set_headers(200, "application/json")
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
            return

        self._set_headers(404, "application/json")
        self.wfile.write(b'{"error": "Endpoint not found"}')

    def log_message(self, format, *args):
        """Clean log output."""
        print(f"[HTTP] {self.address_string()} - {format % args}")


def run_server(port: int = PORT, host: str = "0.0.0.0"):
    """Starts the BigQuery release notes web server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, ReleaseNotesHandler)
    print(f"\n=======================================================")
    print(f"🚀 BigQuery Release Notes Dashboard running!")
    print(f"👉 Local Web UI: http://localhost:{port}")
    print(f"👉 API Endpoints: http://localhost:{port}/api/notes")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else PORT
    run_server(port=port)
