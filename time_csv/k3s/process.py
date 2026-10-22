import re
import pandas as pd

# ==========================
# 输入输出文件
# ==========================
input_file = "../k8s/128/cold_start_all.csv"
output_file = "../k8s/128/processed_cold_start_all.csv"

# ==========================
# 读取CSV
# ==========================
df = pd.read_csv(input_file)

# ==========================
# 提取 program_main_start/end
# ==========================
def extract_main_time(text):
    if pd.isna(text):
        return pd.NaT

    m = re.search(
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)',
        str(text)
    )

    if m:
        return pd.to_datetime(m.group(1))

    return pd.NaT

df["program_main_start"] = df["program_main_start"].apply(extract_main_time)
df["program_main_end"] = df["program_main_end"].apply(extract_main_time)

# =====================================================
# 判断program_main是不是UTC
#
# 你的数据规律：
# curl只有时间，而program如果小时相差>=8，说明它还是UTC
# =====================================================
for i in df.index:

    curl_hour = int(str(df.at[i, "curl_time"]).split(":")[0])

    t = df.at[i, "program_main_start"]

    if pd.isna(t):
        continue

    hour_diff = (t.hour - curl_hour) % 24

    # 例如：
    # curl=00 program=16 -> 16
    # curl=01 program=17 -> 16
    # curl=23 program=15 -> 16
    if hour_diff >= 8:
        df.at[i, "program_main_start"] += pd.Timedelta(hours=8)
        df.at[i, "program_main_end"] += pd.Timedelta(hours=8)

# =====================================================
# 解析logic时间
# =====================================================
def parse_logic(text):
    if pd.isna(text):
        return pd.NaT

    text = str(text).strip()

    if text.endswith("Z"):
        return (
            pd.to_datetime(text, utc=True)
              .tz_convert("Asia/Shanghai")
              .tz_localize(None)
        )

    return pd.to_datetime(text)

df["program_logic_start"] = df["program_logic_start"].apply(parse_logic)
df["program_logic_end"] = df["program_logic_end"].apply(parse_logic)

# =====================================================
# 给curl补日期（一定放最后）
# =====================================================
df["curl_time"] = pd.to_datetime(
    df["program_main_start"].dt.strftime("%Y-%m-%d")
    + " "
    + df["curl_time"].astype(str)
)

# =====================================================
# 计算耗时
# =====================================================
df["knative_cold_start_time"] = (
    df["program_main_start"] - df["curl_time"]
).dt.total_seconds()

df["program_execution_time"] = (
    df["program_main_end"] - df["program_main_start"]
).dt.total_seconds()

df["program_logic_time"] = (
    df["program_logic_end"] - df["program_logic_start"]
).dt.total_seconds()

# =====================================================
# 保存
# =====================================================
result = df[
    [
        "knative_cold_start_time",
        "program_execution_time",
        "program_logic_time"
    ]
]

result.to_csv(output_file, index=False)

print(result)
print("\n输出文件：", output_file)