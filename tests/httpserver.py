# HTTP test server that will accept POST requests and print the body.

import http.server
import logging
import logging.config

import yaml


class LoggingHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        body = self.rfile.read(content_length)
        self.send_response(200)
        self.end_headers()
        logger.info(f"body:\n{body.decode('utf-8')}")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        logger.info(
            f"address: {self.client_address[0]}:{self.client_address[1]} method: {self.command} path: {self.path}"
        )


def main():
    with open("logging.yaml") as f:
        config = yaml.safe_load(f)
        logging.config.dictConfig(config)

    global logger
    logger = logging.getLogger("httpserver")

    server_address = ("127.0.0.1", 8000)
    logger.info(f"Starting server on {server_address[0]}:{server_address[1]}")
    httpd = http.server.HTTPServer(server_address, LoggingHandler)
    httpd.request_queue_size = 10
    httpd.serve_forever()


if __name__ == "__main__":
    main()
