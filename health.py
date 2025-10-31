"""Health check endpoint for monitoring"""
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Handle health check requests"""

    def do_GET(self):
        """Respond to GET requests"""
        if self.path == '/health':
            # Return 200 OK
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            response = {
                'status': 'healthy',
                'service': 'crypto-trading-bot'
            }
            self.wfile.write(json.dumps(response).encode())

        elif self.path == '/':
            # Root path - simple OK
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')

        else:
            # 404 for other paths
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP logs (too verbose)"""
        pass


def start_health_server(port: int = 8080):
    """
    Start health check HTTP server in background thread

    Args:
        port: Port to listen on (default 8080)

    Returns:
        HTTPServer instance
    """
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f'Health check server started on port {port}')
        return server
    except Exception as e:
        logger.error(f'Failed to start health server: {e}')
        return None
