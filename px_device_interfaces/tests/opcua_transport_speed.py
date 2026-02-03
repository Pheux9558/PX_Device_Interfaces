import time
import statistics


from px_device_interfaces.transports.opcua import OPCUATransportConfig


ENDPOINT = "opc.tcp://169.254.152.1:4840"
NODEID = 'ns=3;s="K4331_IN_SW".Array'
# Payload is a 16-byte array with first byte=1, rest=0
PAYLOAD = [0 for i in range(16)]
PAYLOAD[0] = 1

delay = 0.0
count = 1000


config = OPCUATransportConfig(opcua_endpoint=ENDPOINT, default_node=NODEID, timeout=2.0, debug=False)
t = config.create_transport()

t.connect()

if not t.is_connected:
    print("Failed to connect to OPC UA server")
    exit(1)

# Measurements
latencies = []  # seconds per write
errors = 0

try:
    time.sleep(0.1)  # allow some time for the server to process

    start_all = time.perf_counter()
    for i in range(count):
        # blink the first byte between 1 and 0
        PAYLOAD[0] = 1 if (i % 2) == 0 else 0
        start = time.perf_counter()
        try:
            t.write(NODEID, PAYLOAD)
        except Exception as e:
            errors += 1
            print(f"Write error at iteration {i}: {e}")
            # still record failed attempt as None and continue
            latencies.append(None)
            time.sleep(delay)
            continue
        end = time.perf_counter()
        latencies.append(end - start)
        time.sleep(delay)  # allow some time for the server to process
    total_time = time.perf_counter() - start_all

    # compute analytics excluding None (failed writes)
    valid = [v for v in latencies if v is not None]
    n_valid = len(valid)
    n_total = len(latencies)

    if n_valid:
        avg = statistics.mean(valid)
        med = statistics.median(valid)
        mn = min(valid)
        mx = max(valid)
        stdev = statistics.pstdev(valid) if n_valid > 1 else 0.0
        # p95 via sorting
        vs = sorted(valid)
        idx95 = min(int(0.95 * (n_valid - 1)), n_valid - 1)
        p95 = vs[idx95]
        writes_per_sec = n_valid / total_time if total_time > 0 else float('inf')
    else:
        avg = med = mn = mx = stdev = p95 = writes_per_sec = 0.0

    print("--- OPC UA write performance summary ---")
    print(f"Total writes attempted: {n_total}")
    print(f"Successful writes: {n_valid}")
    print(f"Failed writes: {errors}")
    print(f"Total elapsed time: {total_time:.4f} s")
    print(f"Writes/sec (successful): {writes_per_sec:.2f}")
    print(f"Avg latency: {avg:.6f} s")
    print(f"Median latency: {med:.6f} s")
    print(f"P95 latency: {p95:.6f} s")
    print(f"Min latency: {mn:.6f} s")
    print(f"Max latency: {mx:.6f} s")
    print(f"Std dev: {stdev:.6f} s")

except Exception as e:
    print(f"Error getting node data type: {e}")




t.disconnect()
