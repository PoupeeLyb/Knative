import Monsoon.HVPM as HVPM
import Monsoon.sampleEngine as sampleEngine
from Monsoon.sampleEngine import triggers
from datetime import datetime, timedelta
import threading
import os
import csv
import re

# =========================
# 输出路径放在 Linux 家目录
# =========================
raw_csv_path = "/home/poupee/power_log.csv"
absolute_csv_path = "/home/poupee/power_log_absolute.csv"
os.makedirs(os.path.dirname(raw_csv_path), exist_ok=True)

# =========================
# 初始化设备
# =========================
Mon = HVPM.Monsoon()
Mon.setup_usb()

# 避免残留采样状态
try:
    Mon.stopSampling()
except Exception:
    pass

# HVPM 支持 5V
Mon.setVout(5)

# =========================
# 创建采样引擎
# =========================
engine = sampleEngine.SampleEngine(Mon)
engine.enableCSVOutput(raw_csv_path)
engine.ConsoleOutput(False)

# 记录真实开始时间（绝对时间）
start_time = datetime.now()


def extract_float(value):
    """
    兼容：
    np.float64(0.123)
    0.123
    """
    s = str(value).strip()
    m = re.match(r"np\.float64\((.*)\)", s)
    if m:
        s = m.group(1)
    return float(s)


def convert_to_absolute_csv(input_csv, output_csv, start_dt):
    """
    把 Monsoon 原始 CSV 的相对时间转换为绝对时间
    """
    with open(input_csv, "r", newline="", encoding="utf-8") as f_in, \
         open(output_csv, "w", newline="", encoding="utf-8") as f_out:

        reader = csv.reader(f_in)
        writer = csv.writer(f_out)

        header = next(reader, None)
        if not header:
            print("CSV 文件为空，未生成绝对时间文件。")
            return

        # 新表头
        writer.writerow([
            "Absolute Time",
            "Main(mA)",
            "Main Voltage(V)"
        ])

        for row in reader:
            if not row or len(row) < 3:
                continue

            try:
                # 虽然表头写 Time(ms)，但实际数据看起来是秒
                elapsed_seconds = extract_float(row[0])
                current_ma = extract_float(row[1])
                voltage_v = extract_float(row[2])

                abs_time = start_dt + timedelta(seconds=elapsed_seconds)

                writer.writerow([
                    abs_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    f"{current_ma:.6f}",
                    f"{voltage_v:.6f}"
                ])
            except Exception as e:
                print("跳过异常行:", row, "error:", e)


def sampling_worker():
    try:
        # 无限采样；granularity=500 -> 5000Hz / 500 = 约10Hz，即约0.1秒一个点
        engine.startSampling(samples=triggers.SAMPLECOUNT_INFINITE, granularity=500)
    except Exception as e:
        print("Sampling error:", e)


# =========================
# 启动采样线程
# =========================
print("Start time:", start_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
print("Raw CSV path:", raw_csv_path)
print("Absolute CSV path:", absolute_csv_path)
print("输入 x 后按回车停止采样...")

t = threading.Thread(target=sampling_worker, daemon=True)
t.start()

# =========================
# 主线程等待输入 x
# =========================
while True:
    try:
        cmd = input().strip().lower()
        if cmd == "x":
            break
        else:
            print("请输入 x 后按回车退出。")
    except KeyboardInterrupt:
        print("\n检测到 Ctrl+C，也将停止采样。")
        break
    except EOFError:
        print("\n检测到输入结束，也将停止采样。")
        break

# =========================
# 停止采样
# =========================
print("Stopping sampling...")
try:
    Mon.stopSampling()
except Exception as e:
    print("stopSampling error:", e)

t.join(timeout=5)
print("Sampling stopped.")

# =========================
# 转换为绝对时间 CSV
# =========================
try:
    convert_to_absolute_csv(raw_csv_path, absolute_csv_path, start_time)
    print("Absolute time CSV generated:", absolute_csv_path)
except Exception as e:
    print("生成绝对时间 CSV 失败：", e)
