from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import subprocess
import datetime
import urllib.parse
import sys

PORT = 8080


# ==============================
# 高稳定性日志函数（科研级）
# ==============================

def log(msg):
    print(msg, flush=True)


# ==============================
# HTTP Handler
# ==============================

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        # Request ID（论文实验核心）
        req_id = params.get("id", ["unknown"])[0]

        # --------------------------
        # Program start log
        # --------------------------

        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        log(f"[MAIN][INFO] Program start [{req_id}] time: {start_time}")

        # --------------------------
        # 执行主程序（最稳定写法）
        # --------------------------

        subprocess.Popen(
            ["/app/ovx1_app_cn", "/data/video.mp4"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            bufsize=1,
            text=True
        ).wait()

        # --------------------------
        # Program end log
        # --------------------------

        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        log(f"[MAIN][INFO] Program end [{req_id}] time: {end_time}")

        # --------------------------
        # HTTP response
        # --------------------------

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


# ==============================
# Server Start
# ==============================

print("[WRAPPER] Starting HTTP trigger server...", flush=True)

server = ThreadingHTTPServer(("", PORT), Handler)
server.serve_forever()
