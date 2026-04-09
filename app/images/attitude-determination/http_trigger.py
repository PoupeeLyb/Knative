from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import subprocess
import datetime
import urllib.parse
import os

PORT = int(os.environ.get("PORT", "8080"))
LOG_FILE = "/app/attitude.log"


def log(msg):
    print(msg, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        # 请求 ID，用于实验日志关联
        req_id = params.get("id", ["unknown"])[0]

        # 记录开始时间
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log(f"[MAIN][INFO] Program start [{req_id}] time: {start_time}")

        # 执行 Node.js 主程序
        process = subprocess.Popen(
            ["node", "/app/index.js"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # 实时转发程序输出
        if process.stdout is not None:
            for line in process.stdout:
                log(line.rstrip("\n"))

        return_code = process.wait()

        # 记录结束时间
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log(f"[MAIN][INFO] Program end [{req_id}] time: {end_time}")

        # 返回 HTTP 响应
        if return_code == 0:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Program exited with code {return_code}".encode())

    def log_message(self, format, *args):
        # 屏蔽默认访问日志，避免污染实验输出
        return


log(f"[WRAPPER] Starting HTTP trigger server on port {PORT}")
server = ThreadingHTTPServer(("", PORT), Handler)
server.serve_forever()
