
"""
计算 Knative 各函数每次运行的平均功率和能耗。

输入文件：
    cold_start_all.csv
    hot_start_all.csv
    power_log_absolute_*.csv

计算区间：
    curl_time -> program_main_end

功率：
    P(W) = Main(mA) * Main Voltage(V) / 1000

能耗：
    E(J) = 对功率曲线按时间做梯形积分

支持：
    1. UTC 与北京时间相差 8 小时
    2. 跨午夜运行
    3. 自动匹配功率日志日期
    4. 输出每次运行及每个函数的统计结果
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# 0. 配置区：以后只需要修改这里
# =========================================================

TIMEZONE = "Asia/Shanghai"

# Python 脚本所在目录
SCRIPT_DIR = Path(__file__).resolve().parent

# 实验数据目录（相对于 Python 脚本所在目录）
WORK_DIR = SCRIPT_DIR / "k3s" / "2048"

# 冷启动、热启动文件
COLD_FILE = "cold_start_all.csv"
HOT_FILE = "hot_start_all.csv"

# 功率日志匹配规则
POWER_PATTERN = "power_log_absolute_*.csv"

# 输出文件
DETAIL_FILE = "power_by_run.csv"
SUMMARY_FILE = "power_by_function.csv"

# 是否启用自动时间校正
AUTO_ALIGN_TIME = True

# 单次任务最长执行时间（秒）
# 防止匹配到相隔数小时的错误时间
MAX_INTERVAL_SECONDS = 600

# 允许的 UTC / 北京时间偏移
TIMEZONE_OFFSETS = (-8, 0, 8)

# 允许的日期偏移
DAY_OFFSETS = (-2, -1, 0, 1, 2)


# =========================================================
# 1. 时间解析
# =========================================================

def parse_logic_time(value):
    """
    解析时间戳。

    带 Z 的时间视为 UTC，转换为北京时间。
    不带时区的时间暂时保持原样。
    """

    if pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    if not text:
        return pd.NaT

    try:
        timestamp = pd.to_datetime(
            text,
            errors="coerce"
        )
    except (TypeError, ValueError):
        return pd.NaT

    if pd.isna(timestamp):
        return pd.NaT

    if getattr(timestamp, "tzinfo", None) is not None:
        return (
            timestamp
            .tz_convert(TIMEZONE)
            .tz_localize(None)
        )

    return timestamp


def extract_main_time(value):
    """
    提取程序结束时间。

    例如：
    [MAIN][INFO] Program end [xxx]
    time: 2026-10-20 16:24:00.625
    """

    if pd.isna(value):
        return pd.NaT

    text = str(value)

    match = re.search(
        r"time:\s*"
        r"(\d{4}-\d{2}-\d{2}"
        r"[ T]"
        r"\d{2}:\d{2}:\d{2}"
        r"(?:\.\d+)?"
        r"(?:Z|[+-]\d{2}:?\d{2})?)",
        text
    )

    if not match:
        return pd.NaT

    return parse_logic_time(match.group(1))


def parse_curl_time(value, date):
    """
    将 curl_time 的 HH:MM:SS.mmm
    放到指定日期。
    """

    if pd.isna(value) or pd.isna(date):
        return pd.NaT

    text = str(value).strip()

    if not text:
        return pd.NaT

    return pd.to_datetime(
        f"{date.strftime('%Y-%m-%d')} {text}",
        errors="coerce"
    )


# =========================================================
# 2. 自动时间对齐
# =========================================================

def align_run_interval(
    curl_value,
    main_end_value,
    power_start,
    power_end
):
    """
    自动匹配一次函数运行的开始和结束时间。

    处理：
        - UTC / 北京时间相差 8 小时
        - 实验跨越午夜
        - 日志日期不一致
        - 时间区间超出功率日志范围

    返回：
        start
        end
        align_status
        offset_hours
        offset_days
    """

    raw_end = extract_main_time(main_end_value)

    invalid = (
        pd.NaT,
        pd.NaT,
        "time_parse_failed",
        np.nan,
        np.nan
    )

    if pd.isna(curl_value) or pd.isna(raw_end):
        return invalid

    if not AUTO_ALIGN_TIME:
        start = parse_curl_time(
            curl_value,
            power_start
        )
        return (
            start,
            raw_end,
            "alignment_disabled",
            0,
            0
        )

    # -----------------------------------------------------
    # 2.1 根据功率日志生成开始时间候选
    # -----------------------------------------------------

    start_candidates = []

    dates = pd.date_range(
        power_start.normalize(),
        power_end.normalize(),
        freq="D"
    )

    for day in dates:

        start = parse_curl_time(
            curl_value,
            day
        )

        if pd.isna(start):
            continue

        if power_start <= start <= power_end:
            start_candidates.append(start)

    if not start_candidates:
        return (
            pd.NaT,
            pd.NaT,
            "start_outside_power_log",
            np.nan,
            np.nan
        )

    # -----------------------------------------------------
    # 2.2 生成结束时间候选
    # -----------------------------------------------------

    matches = []

    for start in start_candidates:

        for day_offset in DAY_OFFSETS:

            for hour_offset in TIMEZONE_OFFSETS:

                end = (
                    raw_end
                    + pd.Timedelta(days=day_offset)
                    + pd.Timedelta(hours=hour_offset)
                )

                duration = (
                    end - start
                ).total_seconds()

                if duration <= 0:
                    continue

                if duration > MAX_INTERVAL_SECONDS:
                    continue

                if end > power_end or end < power_start:
                    continue

                # 记录候选方案
                matches.append({
                    "start": start,
                    "end": end,
                    "duration": duration,
                    "hour_offset": hour_offset,
                    "day_offset": day_offset,
                })

    if not matches:
        return (
            pd.NaT,
            pd.NaT,
            "no_valid_time_match",
            np.nan,
            np.nan
        )

    # -----------------------------------------------------
    # 2.3 选择匹配结果
    # -----------------------------------------------------

    # 优先保留原始时间，其次选择较少的时间校正。
    # 若校正程度相同，选择持续时间较短的候选。
    #
    # 此规则并不能证明候选一定是真实运行时间，
    # 因此结果中会保留校正信息供核对。

    matches.sort(
        key=lambda item: (
            abs(item["day_offset"]) * 24
            + abs(item["hour_offset"]),
            item["duration"]
        )
    )

    best = matches[0]

    # 不同偏移可能得到相同的结束时间，
    # 因此检查是否存在不同的有效运行区间。
    distinct_intervals = {
        (item["start"], item["end"])
        for item in matches
    }

    if len(distinct_intervals) > 1:
        status = "calculated_check_alignment"
    elif (
        best["hour_offset"] != 0
        or best["day_offset"] != 0
    ):
        status = "time_corrected"
    else:
        status = "original_time"

    return (
        best["start"],
        best["end"],
        status,
        best["hour_offset"],
        best["day_offset"]
    )


# =========================================================
# 3. 读取冷启动、热启动记录
# =========================================================

def parse_run_file(
    path,
    run_type,
    power_start,
    power_end
):

    frame = pd.read_csv(path)

    required = {
        "service_name",
        "iteration",
        "request_id",
        "curl_time",
        "program_main_end",
    }

    missing = sorted(
        required.difference(frame.columns)
    )

    if missing:
        raise ValueError(
            f"{path} 缺少字段: {', '.join(missing)}"
        )

    # 保留原始时间便于核对
    frame["original_curl_time"] = frame["curl_time"]
    frame["original_main_end"] = frame["program_main_end"]

    results = []

    for row in frame.itertuples():

        result = align_run_interval(
            row.curl_time,
            row.program_main_end,
            power_start,
            power_end
        )

        results.append(result)

    frame["interval_start_dt"] = [
        item[0] for item in results
    ]

    frame["interval_end_dt"] = [
        item[1] for item in results
    ]

    frame["align_status"] = [
        item[2] for item in results
    ]

    frame["offset_hours"] = [
        item[3] for item in results
    ]

    frame["offset_days"] = [
        item[4] for item in results
    ]

    frame["run_type"] = run_type

    return frame


# =========================================================
# 4. 读取功率日志
# =========================================================

def load_power_log(path):

    power = pd.read_csv(path)

    required = {
        "Absolute Time",
        "Main(mA)",
        "Main Voltage(V)"
    }

    missing = sorted(
        required.difference(power.columns)
    )

    if missing:
        raise ValueError(
            f"{path} 缺少字段: {', '.join(missing)}"
        )

    power["timestamp"] = pd.to_datetime(
        power["Absolute Time"],
        errors="coerce"
    )

    power["current_ma"] = pd.to_numeric(
        power["Main(mA)"],
        errors="coerce"
    )

    power["voltage_v"] = pd.to_numeric(
        power["Main Voltage(V)"],
        errors="coerce"
    )

    # P(W) = I(mA) * V(V) / 1000
    power["power_w"] = (
        power["current_ma"]
        * power["voltage_v"]
        / 1000.0
    )

    power = (
        power
        .dropna(subset=["timestamp", "power_w"])
        .sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"])
        .reset_index(drop=True)
    )

    if power.empty:
        raise ValueError(
            f"功率日志没有有效数据: {path}"
        )

    return power


# =========================================================
# 5. 计算单次运行平均功率和能耗
# =========================================================

def interval_stats(
    power_seconds,
    power_values,
    log_start,
    log_end,
    start,
    end
):
    """
    计算运行区间：
        curl_time -> program_main_end

    使用线性插值补齐区间边界，
    然后通过梯形积分计算能耗。
    """

    empty = {
        "sample_count": 0,
        "duration_s": np.nan,
        "average_power_w": np.nan,
        "energy_j": np.nan,
        "power_status": "invalid_interval",
    }

    if pd.isna(start) or pd.isna(end):
        return empty.copy()

    if end <= start:
        return empty.copy()

    if start < log_start or end > log_end:
        result = empty.copy()
        result["power_status"] = "outside_power_log"
        return result

    epoch = pd.Timestamp("1970-01-01")

    start_s = (
        start - epoch
    ).total_seconds()

    end_s = (
        end - epoch
    ).total_seconds()

    # 使用 searchsorted 定位功率样本，
    # 避免每次遍历整个功率日志。

    left = np.searchsorted(
        power_seconds,
        start_s,
        side="left"
    )

    right = np.searchsorted(
        power_seconds,
        end_s,
        side="right"
    )

    middle_left = np.searchsorted(
        power_seconds,
        start_s,
        side="right"
    )

    middle_right = np.searchsorted(
        power_seconds,
        end_s,
        side="left"
    )

    middle_x = power_seconds[
        middle_left:middle_right
    ]

    middle_y = power_values[
        middle_left:middle_right
    ]

    # 对区间两个边界进行插值
    boundary_x = np.array(
        [start_s, end_s],
        dtype=float
    )

    boundary_y = np.interp(
        boundary_x,
        power_seconds,
        power_values
    )

    all_x = np.concatenate((
        [start_s],
        middle_x,
        [end_s]
    ))

    all_y = np.concatenate((
        [boundary_y[0]],
        middle_y,
        [boundary_y[1]]
    ))

    # 梯形积分
    if hasattr(np, "trapezoid"):
        energy = float(
            np.trapezoid(all_y, all_x)
        )
    else:
        energy = float(
            np.trapz(all_y, all_x)
        )

    duration = float(
        (end - start).total_seconds()
    )

    average_power = energy / duration

    return {
        "sample_count": int(right - left),
        "duration_s": duration,
        "average_power_w": average_power,
        "energy_j": energy,
        "power_status": "calculated",
    }


# =========================================================
# 6. 自动寻找功率文件
# =========================================================

def find_power_log(
    directory,
    explicit_path=None
):

    if explicit_path:

        path = Path(explicit_path)

        if not path.is_absolute():
            path = directory / path

        if not path.exists():
            raise FileNotFoundError(path)

        return path

    candidates = list(
        directory.glob(POWER_PATTERN)
    )

    if not candidates:
        raise FileNotFoundError(
            f"{directory} 中找不到 {POWER_PATTERN}"
        )

    # 选择文件名排序最后的文件
    candidates = sorted(candidates)

    if len(candidates) > 1:
        print(
            "检测到多个功率日志，"
            f"使用文件: {candidates[-1]}"
        )

    return candidates[-1]


# =========================================================
# 7. 主函数
# =========================================================

def main():

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--directory",
        type=Path,
        default=WORK_DIR,
        help="实验数据目录"
    )

    parser.add_argument(
        "--power-log",
        type=Path,
        default=None,
        help="指定功率日志文件"
    )

    args = parser.parse_args()

    directory = args.directory.resolve()

    if not directory.is_dir():
        raise NotADirectoryError(
            f"实验目录不存在: {directory}"
        )

    print("=" * 65)
    print("Knative 功率与能耗计算")
    print("=" * 65)

    print(f"实验目录: {directory}")

    # -----------------------------------------------------
    # 7.1 读取功率日志
    # -----------------------------------------------------

    power_path = find_power_log(
        directory,
        args.power_log
    )

    power = load_power_log(power_path)

    log_start = power["timestamp"].iloc[0]
    log_end = power["timestamp"].iloc[-1]

    print(f"功率日志: {power_path}")
    print(f"功率日志开始: {log_start}")
    print(f"功率日志结束: {log_end}")
    print(f"功率样本数量: {len(power)}")

    epoch = pd.Timestamp("1970-01-01")

    power_seconds = (
        power["timestamp"] - epoch
    ).dt.total_seconds().to_numpy(dtype=float)

    power_values = power[
        "power_w"
    ].to_numpy(dtype=float)

    # -----------------------------------------------------
    # 7.2 读取运行记录
    # -----------------------------------------------------

    frames = []

    input_files = {
        "cold": COLD_FILE,
        "hot": HOT_FILE,
    }

    for run_type, filename in input_files.items():

        run_path = directory / filename

        if not run_path.exists():
            raise FileNotFoundError(
                f"找不到运行记录: {run_path}"
            )

        frame = parse_run_file(
            run_path,
            run_type,
            log_start,
            log_end
        )

        frames.append(frame)

        print(
            f"{run_type} 记录: "
            f"{run_path} ({len(frame)} rows)"
        )

    runs = pd.concat(
        frames,
        ignore_index=True
    )

    # -----------------------------------------------------
    # 7.3 逐次计算
    # -----------------------------------------------------

    stats = []

    for row in runs.itertuples():

        result = interval_stats(
            power_seconds,
            power_values,
            log_start,
            log_end,
            row.interval_start_dt,
            row.interval_end_dt
        )

        stats.append(result)

    runs = pd.concat(
        [
            runs.reset_index(drop=True),
            pd.DataFrame(stats)
        ],
        axis=1
    )

    # -----------------------------------------------------
    # 7.4 格式化时间
    # -----------------------------------------------------

    runs["interval_start"] = (
        runs["interval_start_dt"]
        .dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        .str[:-3]
    )

    runs["interval_end"] = (
        runs["interval_end_dt"]
        .dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        .str[:-3]
    )

    # -----------------------------------------------------
    # 7.5 保存单次运行结果
    # -----------------------------------------------------

    detail_columns = [
        "run_type",
        "service_name",
        "iteration",
        "request_id",
        "original_curl_time",
        "original_main_end",
        "interval_start",
        "interval_end",
        "offset_hours",
        "offset_days",
        "align_status",
        "sample_count",
        "duration_s",
        "average_power_w",
        "energy_j",
        "power_status",
    ]

    detail_path = directory / DETAIL_FILE

    runs[detail_columns].to_csv(
        detail_path,
        index=False,
        float_format="%.6f",
        encoding="utf-8-sig"
    )

    # -----------------------------------------------------
    # 7.6 按函数汇总
    # -----------------------------------------------------

    summary = (
        runs.groupby(
            ["run_type", "service_name"],
            as_index=False
        )
        .agg(
            total_runs=(
                "request_id",
                "count"
            ),
            valid_runs=(
                "average_power_w",
                "count"
            ),
            average_power_w=(
                "average_power_w",
                "mean"
            ),
            power_std_w=(
                "average_power_w",
                "std"
            ),
            average_duration_s=(
                "duration_s",
                "mean"
            ),
            average_energy_j=(
                "energy_j",
                "mean"
            ),
        )
    )

    # 时间存在多种可能匹配时，标记需要人工核对
    runs["needs_alignment_check"] = (
        runs["align_status"]
        == "calculated_check_alignment"
    )

    check_counts = (
        runs.groupby(
            ["run_type", "service_name"]
        )["needs_alignment_check"]
        .sum()
        .reset_index(name="alignment_check_runs")
    )

    summary = summary.merge(
        check_counts,
        on=["run_type", "service_name"],
        how="left"
    )

    summary_path = directory / SUMMARY_FILE

    summary.to_csv(
        summary_path,
        index=False,
        float_format="%.6f",
        encoding="utf-8-sig"
    )

    # -----------------------------------------------------
    # 7.7 打印统计信息
    # -----------------------------------------------------

    valid = int(
        runs["average_power_w"].notna().sum()
    )

    invalid = len(runs) - valid

    corrected = int(
        (
            (runs["offset_hours"].fillna(0) != 0)
            |
            (runs["offset_days"].fillna(0) != 0)
        ).sum()
    )

    ambiguous = int(
        runs["needs_alignment_check"].sum()
    )

    print()
    print("=" * 65)
    print("计算完成")
    print("=" * 65)

    print(f"运行总次数: {len(runs)}")
    print(f"成功计算: {valid}")
    print(f"无法计算: {invalid}")
    print(f"结束时间发生校正: {corrected}")
    print(f"需要人工核对的时间匹配: {ambiguous}")

    print()
    print(f"每次运行结果: {detail_path}")
    print(f"函数汇总结果: {summary_path}")

    print()
    print("=" * 65)
    print("函数功率与能耗汇总")
    print("=" * 65)

    print(
        summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.6f}"
        )
    )

    if invalid:

        print()
        print("=" * 65)
        print("无法计算的记录")
        print("=" * 65)

        print(
            runs.loc[
                runs["average_power_w"].isna(),
                [
                    "run_type",
                    "service_name",
                    "iteration",
                    "original_curl_time",
                    "interval_start",
                    "interval_end",
                    "align_status",
                    "power_status"
                ]
            ].to_string(index=False)
        )

    if ambiguous:
        print()
        print(
            "注意：存在多种有效时间匹配。"
            "请核对 power_by_run.csv 中"
            " align_status 为 calculated_check_alignment "
            "的记录。"
        )


# =========================================================
# 8. 程序入口
# =========================================================

if __name__ == "__main__":
    main()
