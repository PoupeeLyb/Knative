from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import subprocess
import datetime
import urllib.parse
import os

PORT = int(os.environ.get("PORT", "8080"))
LOG_FILE = "/app/object_detect.log"

DEFAULT_MODEL_PATH = "/app/model/yolov8n.torchscript"
DEFAULT_IMAGE_PATH = "/app/model/input.jpg"


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

        # 支持 HTTP 参数覆盖默认路径
        model_path = params.get("model", [DEFAULT_MODEL_PATH])[0] or DEFAULT_MODEL_PATH
        image_path = params.get("image", [DEFAULT_IMAGE_PATH])[0] or DEFAULT_IMAGE_PATH

        # 开始时间
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log(f"[MAIN][INFO] Program start [{req_id}] time: {start_time}")
        log(f"[MAIN][INFO] Args [{req_id}] model: {model_path}, image: {image_path}")

        process = subprocess.Popen(
            ["python3", "/app/6.object_detect.py", model_path, image_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        if process.stdout is not None:
            for line in process.stdout:
                log(line.rstrip("\n"))

        return_code = process.wait()

        # 结束时间
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log(f"[MAIN][INFO] Program end [{req_id}] time: {end_time}")

        if return_code == 0:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Program exited with code {return_code}".encode())

    def log_message(self, format, *args):
        return


log(f"[WRAPPER] Starting HTTP trigger server on port {PORT}")
server = ThreadingHTTPServer(("", PORT), Handler)
server.serve_forever()
