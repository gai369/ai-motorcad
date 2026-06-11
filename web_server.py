
"""Web server for AI Motor Design Assistant chat interface.

Start with: python web_server.py
Then open: http://localhost:8765
"""

import json
import os
import sys
import io
from http.server import HTTPServer, SimpleHTTPRequestHandler
from contextlib import redirect_stdout

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_motorcad.chat import MotorCADChat


# Global chat instance
_chat = None


def get_chat():
    global _chat
    if _chat is None:
        _chat = MotorCADChat()
        _chat.connector._offline_mode = True
        _chat._mode = "offline"
        _chat.connector.connect()
    return _chat


class ChatHandler(SimpleHTTPRequestHandler):
    """HTTP handler that serves chat.html and processes API requests."""

    def __init__(self, *args, **kwargs):
        # Serve from the web directory
        web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
        super().__init__(*args, directory=web_dir, **kwargs)

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            message = data.get("message", "")

            chat = get_chat()

            # Capture printed output as well as returned value
            f = io.StringIO()
            try:
                with redirect_stdout(f):
                    result = chat._dispatch(message)
            except Exception as e:
                result = f"Error: {e}"

            printed = f.getvalue().strip()
            output = printed + ("\n" + result if result and result != "EXIT" and result != printed else "")

            resp = {
                "response": output.strip() or "(no output)",
                "status": chat._mode,
                "report_file": None,
            }

            # Check if a report was generated
            if output and "Report saved:" in output:
                for line in output.split("\n"):
                    if "Report saved:" in line:
                        resp["report_file"] = line.split("Report saved:")[-1].strip()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging noise."""
        if "200" in str(args[0]) or "304" in str(args[0]):
            return
        print(f"[{self.log_date_time_string()}] {args[0]}")


def main():
    port = 8765
    server = HTTPServer(("127.0.0.1", port), ChatHandler)
    print("=" * 50)
    print("  AI Motor Design Assistant - Web Interface")
    print(f"  Open: http://localhost:{port}")
    print("=" * 50)
    print()
    print("Press Ctrl+C to stop the server.")
    
    # Initialize chat
    chat = get_chat()
    print(f"  Mode: {chat._mode}")
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
