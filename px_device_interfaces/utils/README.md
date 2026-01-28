Plot utility — `plot_is_should.py`
===============================

Overview

This directory contains a small tooling script used to run the blink test, capture timestamped debug logs, and plot the observed send/ack timings to help diagnose latency and ACK/OK burst behaviour.

The script is intentionally minimal and useful for:
- Visualizing send times vs device OK times
- Compressing long traces when there are many sends
- Dumping intermediate arrays for debugging
- Highlighting points that exceed an expected hardware delay threshold

Quick usage
-----------

- Run and plot interactively (requires a GUI):

  ```bash
  ./.venv/Scripts/python.exe px_device_interfaces/utils/plot_is_should.py --show
  ```

- Use an existing log file instead of running the blink script:

  ```bash
  ./.venv/Scripts/python.exe px_device_interfaces/utils/plot_is_should.py --log path/to/log.txt --show
  ```

- Dump debug arrays instead of plotting (helpful for CI or quick checks):

  ```bash
  ./.venv/Scripts/python.exe px_device_interfaces/utils/plot_is_should.py --dump-data
  ```

Blink runner
------------

The plot script obtains log data by running the included blink runner script `px_device_interfaces/utils/blink_builtin.py` (30s timeout by default). This helper:

- Uses `USBTransportConfig` and `GPIO_Lib` to open the configured serial port (defaults: `port="COM7"`, `baud=115200`).
- Blinks a test pin (defaults: `led_pin=10`) a number of times (defaults: `blink_count=100`) and emits timestamped debug lines including `sending(hex): ...` and `device: OK` which the plot parser uses.

You can run `blink_builtin.py` directly to capture a log without plotting (handy for device debugging):

```bash
python px_device_interfaces/utils/blink_builtin.py > my_blink_run.log 2>&1
```

Or let `plot_is_should.py` run it and it will save output to `px_device_interfaces/utils/blink_run.log` for you.

What it does (short)
--------------------
- Runs `px_device_interfaces/utils/blink_builtin.py` (a small blink runner) and captures stdout/stderr into `px_device_interfaces/utils/blink_run.log` (30s timeout by default).
- Parses log lines for:
  - Send events (lines containing `sending(hex): ...`) — timestamps of when packets were queued/built.
  - OK events (`device: OK` optionally with an inline timestamp `device: OK @ <iso-ts>`).
- Normalizes timestamps to the run start and produces two panels:
  1. Top: per-send time and OK time (x-axis uses packet indices, with optional compression).
  2. Bottom: latency metrics ("send -> next OK" and "time since last OK at send").
- Writes `is_should_plot.png` to the same folder and optionally opens it interactively.

Important flags & behaviour
--------------------------
- `--max-points N` (default 200): if there are more than `N` sends, the script aggregates/compresses the sends into chunks (averaging timestamps) so the plotted X-axis remains readable. Set `--max-points 0` to disable compression.

- `--dump-data`: don't show the plot; instead print compressed/original arrays and summary stats (including the count of points above the hardware delay).

- Hardware delay reference (`MAX_HARDWARE_DELAY`): the script draws a horizontal reference line at 0.01 s (10 ms) and highlights any plotted latency points above it in **dark red**. The value and colours are defined in the script and printed in the dump output.

Why this is useful
------------------
- The plot visually reveals bursts (many OKs in a single read) and long gaps (periods with no OKs).
- Compression + median-based aggregation reduces the effect of outlier packets and makes trends clearer.
- Dumping arrays makes it easy to write unit tests or to inspect corner cases programmatically.

Debugging tips
----------------
- If you see replacement characters (EF BF BD) in the logs, ensure the device/transport is emitting binary frames and that the transport uses `receive_bytes()` rather than decoding with `errors='replace'`.
- Use `--max-points` to change compression granularity and rerun to check stability of trends.
- If many points exceed the `MAX_HARDWARE_DELAY`, investigate device-side processing (firmware) or transport pacing (send worker loop delay).
