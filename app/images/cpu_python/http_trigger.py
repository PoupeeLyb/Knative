from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import subprocess
import datetime
import urllib.parse
import os

PORT = int(os.environ.get("PORT", "8080"))
LOG_FILE = "/app/cpu_python.log"

# 默认参数
DEFAULT_ARG1 = "10"
DEFAULT_ARG2 = "10"


def log(msg):
    print(msg, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        # 请求 ID
        req_id = params.get("id", ["unknown"])[0]

        # 参数，支持 HTTP 覆盖默认值
        arg1 = params.get("arg1", [DEFAULT_ARG1])[0]
        arg2 = params.get("arg2", [DEFAULT_ARG2])[0]

        # 记录开始时间
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log(f"[MAIN][INFO] Program start [{req_id}] time: {start_time}")
        log(f"[MAIN][INFO] Args [{req_id}] arg1: {arg1}, arg2: {arg2}")

        # 执行主程序
        process = subprocess.Popen(
            ["python3", "/app/1.cpu_linear_equations.py", arg1, arg2],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        if process.stdout is not None:
            for line in process.stdout:
                log(line.rstrip("\n"))

        return_code = process.wait()

        # 记录结束时间
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log(f"[MAIN][INFO] Program end [{req_id}] time: {end_time}")

        # HTTP 返回
        if return_code == 0:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Program exited with code {return_code}".encode())

    def log_message(self, format, *args):
        # 屏蔽默认 HTTP 访问日志
        return


log(f"[WRAPPER] Starting HTTP trigger server on port {PORT}")
server = ThreadingHTTPServer(("", PORT), Handler)
server.serve_forever()
