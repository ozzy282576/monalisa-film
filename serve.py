import http.server, socketserver, os, sys
os.chdir('/home/user/monalisa-film')
PORT = 8000
class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", PORT), CORSHandler) as httpd:
    print(f"Serving at 0.0.0.0:{PORT}")
    sys.stdout.flush()
    httpd.serve_forever()
