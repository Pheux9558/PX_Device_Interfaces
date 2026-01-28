import threading
import time

from px_device_interfaces.transports.mock import MockTransport, MockTransportConfig
from px_device_interfaces.GPIO_Lib import GPIO_Lib, CMD_DIGITAL_WRITE, CMD_DEVICE_OK


def _start_worker_threads(gpio, mock):
    # Ensure transport is connected and workers are running
    # Use _await_device_ready() to detect the READY banner instead of running
    # the full recv worker so tests can control readiness deterministically.
    mock.connect()
    gpio._transport = mock
    gpio._running = True

    # start a background thread to perform the synchronous readiness probe
    def _ready_probe():
        try:
            gpio._await_device_ready(timeout=1.0)
        except Exception:
            pass
    gpio._ready_thread = threading.Thread(target=_ready_probe, daemon=True)
    gpio._ready_thread.start()

    # start send worker
    gpio._send_running = True
    gpio._send_thread = threading.Thread(target=gpio._send_worker, daemon=True)
    gpio._send_thread.start()


def _stop_worker_threads(gpio):
    gpio._send_running = False
    gpio._running = False
    # join the readiness probe thread (if used in tests)
    if getattr(gpio, "_ready_thread", None) is not None:
        gpio._ready_thread.join(0.2)
    if getattr(gpio, "_recv_thread", None) is not None:
        gpio._recv_thread.join(0.2)
    if getattr(gpio, "_send_thread", None) is not None:
        gpio._send_thread.join(0.2)


def test_send_worker_waits_for_ready():
    mock = MockTransport(loopback=False)
    cfg = MockTransportConfig(loopback=False, debug=True, timeout=0.1, auto_io=False)
    gpio = GPIO_Lib(transport_config=cfg, debug_enabled=True)

    _start_worker_threads(gpio, mock)
    try:
        # enqueue a packet (send worker should block until READY is seen)
        pkt = gpio._build_packet(CMD_DIGITAL_WRITE, bytes([10, 1]))
        assert mock.pop_sent(raw=True) == []
        queued = gpio._add_packet_to_send_queue(pkt, wait_ack=False)
        assert queued
        # give the worker a short moment to attempt sending (it should wait for READY)
        time.sleep(0.05)
        assert mock.pop_sent(raw=True) == []

        # now simulate device READY banner
        mock._incoming.put(b"GPIO_READY\r\n")
        # allow some time for recv to process and send to occur
        time.sleep(0.1)
        sent = mock.pop_sent(raw=True)
        assert len(sent) == 1
        assert isinstance(sent[0], (bytes, bytearray))
    finally:
        _stop_worker_threads(gpio)


def test_send_waits_for_ok_blocks_then_completes():
    mock = MockTransport(loopback=False)
    cfg = MockTransportConfig(loopback=False, debug=True, timeout=0.1, auto_io=False)
    gpio = GPIO_Lib(transport_config=cfg, debug_enabled=True)

    _start_worker_threads(gpio, mock)
    # start recv worker so the OK we inject will be parsed
    gpio._recv_thread = threading.Thread(target=gpio._recv_worker, daemon=True)
    gpio._recv_thread.start()
    try:
        # mark device ready so we don't block on READY
        with gpio._ready_cv:
            gpio._ready = True
            gpio._ready_cv.notify_all()

        # make send worker wait for OK for up to 0.5s
        gpio.send_ack_timeout = 0.5
        pkt = gpio._build_packet(CMD_DIGITAL_WRITE, bytes([11, 1]))
        queued = gpio._add_packet_to_send_queue(pkt, wait_ack=True)
        assert queued

        # short await should fail because worker is waiting for OK
        assert not gpio.await_send_empty(timeout=0.05)

        # now simulate device OK arriving
        ok_pkt = gpio._build_packet(CMD_DEVICE_OK, b"")
        mock._incoming.put(ok_pkt)

        # longer await should now succeed
        assert gpio.await_send_empty(timeout=1.0)
    finally:
        _stop_worker_threads(gpio)


def test_per_packet_wait_ack_records_sent_packet():
    mock = MockTransport(loopback=False)
    cfg = MockTransportConfig(loopback=False, debug=True, timeout=0.1, auto_io=False)
    gpio = GPIO_Lib(transport_config=cfg, debug_enabled=True)

    _start_worker_threads(gpio, mock)
    # start recv worker so the OK we inject will be parsed
    gpio._recv_thread = threading.Thread(target=gpio._recv_worker, daemon=True)
    gpio._recv_thread.start()
    try:
        with gpio._ready_cv:
            gpio._ready = True
            gpio._ready_cv.notify_all()

        pkt = gpio._build_packet(CMD_DIGITAL_WRITE, bytes([12, 1]))
        queued = gpio._add_packet_to_send_queue(pkt, wait_ack=True)
        assert queued

        # give it a moment and then send the OK that the worker is waiting for
        time.sleep(0.05)
        mock._incoming.put(gpio._build_packet(CMD_DEVICE_OK, b""))

        # await send completion
        assert gpio.await_send_empty(timeout=1.0)
        sent = mock.pop_sent(raw=True)
        assert len(sent) == 1
    finally:
        _stop_worker_threads(gpio)
