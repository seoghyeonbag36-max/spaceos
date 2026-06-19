"""로컬 개발용 간단 HTTP 서버 — Python 표준 라이브러리만 사용."""
import http.server
import os
import webbrowser
from pathlib import Path

PORT = 3000
DIR  = Path(__file__).parent  # spaceos/html/

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIR), **kwargs)
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

if __name__ == "__main__":
    os.chdir(DIR)
    with http.server.HTTPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"\n  SpaceOS 지도 서버 시작")
        print(f"  URL : {url}")
        print(f"  종료: Ctrl+C\n")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  서버 종료")
