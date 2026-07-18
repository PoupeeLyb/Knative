#!/usr/bin/env python3

import argparse
import csv
import re
import shutil
from pathlib import Path


MAIN_DATE_RE = re.compile(r"time:\s*(\d{4}-\d{2}-\d{2})[ T]")
PROGRAM_START_RE = re.compile(r"Program start time:\s*(.+)$")
PROGRAM_END_RE = re.compile(r"Program end time:\s*(.+)$")
CHINESE_PAREN_RE = re.compile(
    r"\((\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})(?:\s+北京时间)?\)"
)
CHINESE_TIME_RE = re.compile(r"时间:\s*(\d{2}:\d{2}:\d{2}\.\d{3})")


def main_date_from_row(row):
    for key in ("program_main_start", "program_main_end"):
        match = MAIN_DATE_RE.search(row.get(key, ""))
        if match:
            return match.group(1)
    return ""


def extract_logic_times(log_path, row):
    logic_start = ""
    logic_end = ""
    main_date = main_date_from_row(row)

    for raw_line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()

        start_match = PROGRAM_START_RE.search(line)
        if start_match:
            logic_start = start_match.group(1).strip()
            continue

        end_match = PROGRAM_END_RE.search(line)
        if end_match:
            logic_end = end_match.group(1).strip()
            continue

        if "[程序启动]" in line:
            paren_match = CHINESE_PAREN_RE.search(line)
            if paren_match:
                logic_start = paren_match.group(1)
                continue

            time_match = CHINESE_TIME_RE.search(line)
            if time_match:
                logic_start = f"{main_date} {time_match.group(1)}" if main_date else time_match.group(1)
                continue

        if "[程序结束]" in line:
            paren_match = CHINESE_PAREN_RE.search(line)
            if paren_match:
                logic_end = paren_match.group(1)
                continue

            time_match = CHINESE_TIME_RE.search(line)
            if time_match:
                logic_end = f"{main_date} {time_match.group(1)}" if main_date else time_match.group(1)
                continue

    return logic_start, logic_end


def update_csv(csv_path, log_dir, kind):
    rows = []
    updated = 0
    missing_logs = []
    missing_times = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        for row in reader:
            service = row["service_name"]
            iteration = row["iteration"]
            log_path = log_dir / f"{service}_{kind}_{iteration}.log"

            if not log_path.exists():
                missing_logs.append(str(log_path))
                rows.append(row)
                continue

            logic_start, logic_end = extract_logic_times(log_path, row)
            if logic_start:
                row["program_logic_start"] = logic_start
            if logic_end:
                row["program_logic_end"] = logic_end

            if logic_start and logic_end:
                updated += 1
            else:
                missing_times.append(str(log_path))

            rows.append(row)

    backup_path = csv_path.with_suffix(csv_path.suffix + ".bak")
    shutil.copy2(csv_path, backup_path)

    output_path = csv_path
    try:
        handle = output_path.open("w", encoding="utf-8", newline="")
    except PermissionError:
        output_path = csv_path.with_name(f"{csv_path.stem}_filled{csv_path.suffix}")
        handle = output_path.open("w", encoding="utf-8", newline="")

    with handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "csv": str(csv_path),
        "written_to": str(output_path),
        "backup": str(backup_path),
        "rows_updated": updated,
        "missing_logs": missing_logs,
        "missing_times": missing_times,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill program_logic_start/program_logic_end in cold/hot CSV files from saved logs."
    )
    parser.add_argument("--log-dir", default="logs", help="Directory containing *_cold_N.log and *_hot_N.log files.")
    parser.add_argument("--cold-csv", default=None, help="Path to cold_start_all.csv. Defaults to LOG_DIR/cold_start_all.csv.")
    parser.add_argument("--hot-csv", default=None, help="Path to hot_start_all.csv. Defaults to LOG_DIR/hot_start_all.csv.")
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    cold_csv = Path(args.cold_csv) if args.cold_csv else log_dir / "cold_start_all.csv"
    hot_csv = Path(args.hot_csv) if args.hot_csv else log_dir / "hot_start_all.csv"

    for csv_path, kind in ((cold_csv, "cold"), (hot_csv, "hot")):
        result = update_csv(csv_path, log_dir, kind)
        print(f"[INFO] updated {result['rows_updated']} rows from {result['csv']}")
        print(f"[INFO] wrote results to {result['written_to']}")
        print(f"[INFO] backup saved to {result['backup']}")
        if result["missing_logs"]:
            print(f"[WARN] missing {len(result['missing_logs'])} log file(s)")
        if result["missing_times"]:
            print(f"[WARN] missing logic time in {len(result['missing_times'])} log file(s)")


if __name__ == "__main__":
    main()
