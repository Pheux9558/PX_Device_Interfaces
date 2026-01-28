#!/usr/bin/env python3
"""Run the blink test, capture timestamped logs, and plot "is" vs "should be" times.

Usage:
  ./.venv/Scripts/python.exe ./scripts/plot_is_should.py --show  # shows interactive plot
  ./.venv/Scripts/python.exe ./scripts/plot_is_should.py --dump-data  # dumps debug data instead of plotting
  python scripts/plot_is_should.py  # runs blink_com7_pin10.py and plots
  python scripts/plot_is_should.py --log path/to/log.txt  # use existing log file

Output: writes `scripts/is_should_plot.png` and prints summary stats.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import matplotlib
except Exception:
    print("matplotlib is required. Install with: pip install matplotlib")
    raise

SENDING_RE = re.compile(r"sending\(hex\): (?P<hex>[0-9a-fA-F]+)")
OK_RE = re.compile(r"device: OK(?: @ (?P<ok_ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+))?")

LOG_PATH = Path(__file__).resolve().parent / "blink_run.log"
OUT_PNG = Path(__file__).resolve().parent / "is_should_plot.png"

# Threshold and styling for hardware max delay visualization
MAX_HARDWARE_DELAY = 0.01  # seconds (10 ms)
MAX_HARDWARE_LINE_COLOR = 'purple'
EXCEED_POINT_COLOR = 'darkred'
EXCEED_POINT_SIZE = 36


def run_blink_and_capture():
    env = dict(os.environ)
    env["PYTHONPATH"] = env.get("PYTHONPATH", "")
    if env["PYTHONPATH"] != "":
        env["PYTHONPATH"] = env["PYTHONPATH"] + os.pathsep + str(Path(__file__).resolve().parents[1])
    else:
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])

    print("Running blink script and capturing output to", LOG_PATH)
    try:
        # use a timeout to avoid blocking indefinitely if the blink script waits on hardware
        p = subprocess.run([sys.executable, "px_device_interfaces/utils/blink_builtin.py"], env=env, capture_output=True, text=True, timeout=30)
        LOG_PATH.write_text(p.stdout + "\n" + p.stderr)
        return LOG_PATH
    except subprocess.TimeoutExpired:
        LOG_PATH.write_text("ERROR: blink script timed out after 30s\n")
        return LOG_PATH


def parse_log(path: Path):
    sends = []  # timestamps of sends
    oks = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if " - " in line:
            ts_str, rest = line.split(" - ", 1)
            try:
                ts = datetime.fromisoformat(ts_str)
            except Exception:
                continue
            if SENDING_RE.search(rest):
                sends.append(ts)
            m_ok = OK_RE.search(rest)
            if m_ok:
                ok_ts = m_ok.group("ok_ts")
                if ok_ts:
                    try:
                        oks.append(datetime.fromisoformat(ok_ts))
                    except Exception:
                        oks.append(ts)
                else:
                    oks.append(ts)
        
    return sends, oks


def plot_events(sends, oks, out_png: Path, show: bool = False, max_points: int = 200, dump_data: bool = False):
    # normalize to start
    if not sends and not oks:
        raise SystemExit("No events found in log")
    all_ts = (sends + oks)
    start = min(all_ts)
    sends_secs = [(t - start).total_seconds() for t in sends]
    oks_secs = [(t - start).total_seconds() for t in oks]

    # Keep copies of original sequences for mapping
    orig_sends_secs = list(sends_secs)
    orig_sends = list(sends)
    orig_oks_secs = list(oks_secs)
    orig_oks = list(oks)

    # Compress send data if too many points (average per chunk) to keep plots readable
    comp_note = ""
    factor = 1
    if max_points and len(orig_sends_secs) > int(max_points):
        import math
        def _compress_vals_and_indices(vals, indices, factor: int):
            out_vals = []
            out_idx = []
            for i in range(0, len(vals), factor):
                chunk_vals = vals[i : i + factor]
                chunk_idx = indices[i : i + factor]
                out_vals.append(sum(chunk_vals) / len(chunk_vals))
                out_idx.append(sum(chunk_idx) / len(chunk_idx))
            return out_vals, out_idx
        factor = math.ceil(len(orig_sends_secs) / int(max_points))
        sends_secs_plot, send_plot_indices = _compress_vals_and_indices(orig_sends_secs, list(range(len(orig_sends_secs))), factor)
        comp_note = f" (compressed by factor {factor})"
    else:
        sends_secs_plot = orig_sends_secs
        send_plot_indices = list(range(len(orig_sends_secs)))

    # Map OK timestamps to original packet indices for plotting (so x-axis always uses real packet numbers)
    import bisect
    oks_mapped_indices = []
    for ok_dt in orig_oks:
        # find insertion point amongst original sends datetimes
        idx = bisect.bisect_left(orig_sends, ok_dt)
        if idx >= len(orig_sends):
            idx = len(orig_sends) - 1
        oks_mapped_indices.append(idx)

    # Compress OKs by the same send-based chunks so both series align
    if factor > 1:
        oks_secs_plot = []
        oks_plot_indices = []
        total_sends = len(orig_sends_secs)
        for i in range(0, total_sends, factor):
            chunk_start = i
            chunk_end = i + factor
            # collect OK secs (seconds-from-start) falling into this send-range
            chunk_ok_secs = [orig_oks_secs[j] for j, mapped in enumerate(oks_mapped_indices) if mapped >= chunk_start and mapped < chunk_end]
            chunk_ok_mapped = [mapped for mapped in oks_mapped_indices if mapped >= chunk_start and mapped < chunk_end]
            if chunk_ok_secs:
                oks_secs_plot.append(sum(chunk_ok_secs) / len(chunk_ok_secs))
                # representative x position = mean of mapped indices in this chunk
                oks_plot_indices.append(sum(chunk_ok_mapped) / len(chunk_ok_mapped))
    else:
        oks_secs_plot = list(orig_oks_secs)
        oks_plot_indices = list(oks_mapped_indices)

    # Compute per-send latencies from original timestamps (more accurate)
    # For each original send, find the next OK and the previous OK and record seconds
    import statistics
    orig_send_to_next = []
    orig_since_last = []
    oks_sorted_dt = sorted(orig_oks)
    for s_dt in orig_sends:
        # find first OK >= send
        idx = bisect.bisect_left(oks_sorted_dt, s_dt)
        if idx < len(oks_sorted_dt):
            delta = (oks_sorted_dt[idx] - s_dt).total_seconds()
            orig_send_to_next.append(delta)
        else:
            orig_send_to_next.append(None)
        # previous OK
        if idx - 1 >= 0:
            prev = (s_dt - oks_sorted_dt[idx - 1]).total_seconds()
            orig_since_last.append(prev)
        else:
            orig_since_last.append(None)

    # Aggregate per-send latencies into chunks (median across sends in chunk)
    latency_send_to_next = []  # per-chunk median send->next OK
    since_last_ok = []         # per-chunk median time since last OK
    total_sends = len(orig_send_to_next)
    for i in range(0, total_sends, factor):
        chunk = orig_send_to_next[i : i + factor]
        nums = [v for v in chunk if v is not None]
        if nums:
            latency_send_to_next.append(statistics.median(nums))
        else:
            latency_send_to_next.append(None)
        chunk2 = orig_since_last[i : i + factor]
        nums2 = [v for v in chunk2 if v is not None]
        if nums2:
            since_last_ok.append(statistics.median(nums2))
        else:
            since_last_ok.append(None)

    # number of plotted send points (post-compression)
    n = len(sends_secs_plot)

    # Choose an interactive backend if `show` requested, then import pyplot
    import matplotlib
    if show:
        for backend in ("TkAgg", "Qt5Agg", "WXAgg", "GTK3Agg", "Qt4Agg"):
            try:
                matplotlib.use(backend, force=True)
                break
            except Exception:
                continue
    import matplotlib.pyplot as plt

    # Two-panel plot: top = send & recv times; bottom = latency metrics
    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(10, 6), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})

    # Top: send and OK times (x uses original packet indices so axis shows real counts)
    ax1.plot(send_plot_indices, sends_secs_plot, marker='o', label='send time (s)', color='tab:blue')
    # plot OKs mapped to original packet indices (compressed)
    ax1.plot(oks_plot_indices, oks_secs_plot, marker='x', label='ok time (s)', color='tab:orange')
    ax1.set_ylabel('time (s) from start')
    ax1.set_title(f'Send times vs Device OK times{comp_note}')
    ax1.grid(True, linestyle='--', alpha=0.4)
    ax1.legend(loc='upper left')

    # Bottom: two separate latency lines (no stacking)
    x = send_plot_indices
    lat1 = [v if v is not None else float('nan') for v in latency_send_to_next]
    lat2 = [v if v is not None else float('nan') for v in since_last_ok]
    ax2.plot(x, lat1, marker='.', linestyle='-', color='gray', label='send -> next OK (s)')
    ax2.plot(x, lat2, marker='.', linestyle='-', color='green', label='time since last OK at send (s)')

    ax2.set_xlabel('packet index (send count)')
    ax2.set_ylabel('seconds')
    ax2.grid(True, linestyle='--', alpha=0.4)
    # annotate summary stats for send->next OK only
    import statistics
    lat_values = [v for v in lat1 if not (v is None or (isinstance(v, float) and (v != v)))]
    avg = statistics.mean(lat_values) if lat_values else 0.0
    med = statistics.median(lat_values) if lat_values else 0.0

    # Dump debug data if requested (print compressed & original samples)
    if dump_data:
        print("--- PLOT DEBUG DUMP ---")
        print(f"original sends: {len(orig_sends_secs)} points, plotted sends: {len(sends_secs_plot)} points, factor={factor}")
        print("sample plotted sends (x index, time s):")
        for i, (xi, v) in enumerate(zip(send_plot_indices[:20], sends_secs_plot[:20])):
            print(f"  [{i}] x={xi} time={v:.6f}")
        print("sample plotted oks (x index, time s):")
        for i, (xi, v) in enumerate(zip(oks_plot_indices[:20], oks_secs_plot[:20])):
            print(f"  [{i}] x={xi} time={v:.6f}")
        print("sample latencies (send->next OK):")
        for i, v in enumerate(lat_values[:20]):
            print(f"  [{i}] {v:.6f}")
        # count points above MAX_HARDWARE_DELAY in plotted aggregated latencies
        count_exceeds = sum(1 for v in lat1 if not (v is None or (isinstance(v, float) and (v != v))) and v > MAX_HARDWARE_DELAY)
        print(f"points above MAX_HARDWARE_DELAY ({MAX_HARDWARE_DELAY}s): {count_exceeds}")
        print(f"summary: avg={avg:.6f}s median={med:.6f}s")

    ax2.axhline(avg, color='red', linestyle='--', label=f'avg {avg:.3f}s')
    # Max hardware delay reference line (user-requested)
    ax2.axhline(MAX_HARDWARE_DELAY, color=MAX_HARDWARE_LINE_COLOR, linestyle=':', linewidth=1.5, label=f'Max hardware delay ({MAX_HARDWARE_DELAY:.3f}s)')

    # Highlight points that exceed MAX_HARDWARE_DELAY in dark red
    import math
    exceed_mask1 = [False if (v is None or (isinstance(v, float) and math.isnan(v))) else (v > MAX_HARDWARE_DELAY) for v in lat1]
    exceed_x1 = [xi for xi, m in zip(x, exceed_mask1) if m]
    exceed_y1 = [v for v, m in zip(lat1, exceed_mask1) if m]
    if exceed_x1:
        ax2.scatter(exceed_x1, exceed_y1, color=EXCEED_POINT_COLOR, s=EXCEED_POINT_SIZE, zorder=5, label='exceeds max hw delay')

    exceed_mask2 = [False if (v is None or (isinstance(v, float) and math.isnan(v))) else (v > MAX_HARDWARE_DELAY) for v in lat2]
    exceed_x2 = [xi for xi, m in zip(x, exceed_mask2) if m]
    exceed_y2 = [v for v, m in zip(lat2, exceed_mask2) if m]
    if exceed_x2:
        ax2.scatter(exceed_x2, exceed_y2, color=EXCEED_POINT_COLOR, s=EXCEED_POINT_SIZE, zorder=5, marker='x')

    ax2.legend(loc='upper right')
    fig.tight_layout()
    fig.savefig(out_png)
    print(f"Wrote plot to {out_png} (ploted points={n}) — plot length={n * factor} avg latency={avg:.4f}s median={med:.4f}s")

    # only show the interactive plot when requested and not dumping data
    if show and not dump_data:
        try:
            plt.show()
        except Exception:
            # fallback: open the saved PNG using OS default program (Windows)
            try:
                import os
                os.startfile(out_png)
            except Exception:
                print("Could not show plot interactively; saved to", out_png)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--log', help='Optional existing log file to parse')
    p.add_argument('--show', action='store_true', help='Show the plot interactively (requires display)')
    p.add_argument('--max-points', type=int, default=200, help='Maximum points to show on plot (compress when larger). Set 0 to disable compression. Default: 200')
    p.add_argument('--dump-data', action='store_true', help='Do not show plot; print compressed/original arrays and latency samples for debugging')
    args = p.parse_args()

    if args.log:
        path = Path(args.log)
        if not path.exists():
            raise SystemExit("Log file not found: " + str(path))
    else:
        path = run_blink_and_capture()

    sends, oks = parse_log(path)
    print(f"Found {len(sends)} sends, {len(oks)} oks")
    if not sends or not oks:
        print("Not enough events to plot; ensure blink script runs with debug enabled")
        raise SystemExit(1)

    plot_events(sends, oks, OUT_PNG, show=bool(args.show), max_points=args.max_points, dump_data=bool(args.dump_data))


if __name__ == '__main__':
    main()
