from __future__ import annotations

import queue
import threading
import time
from typing import Optional

from px_device_interfaces.transports import BaseTransport
from px_device_interfaces.transports.base import BaseTransportConfig



class ConnectionOrganiserAdapter:
    """High-level ConnectionOrganiser adapter using transport factory.

    This adapter provides a minimal, non-breaking API that mimics the
    original `ConnectionOrganiser` behaviour for sending and receiving
    textual commands. It intentionally stays small so it can be used
    in unit tests with `MockTransport`.
    """

    def __init__(
        self,
        transport_config: Optional["BaseTransportConfig"] = None,
        debug: bool = False,
    ):
        self.debug = debug

        # queues exposed to callers
        self.send_q: "queue.Queue[str]" = queue.Queue()
        self.receive_q: "queue.Queue[str]" = queue.Queue()

        # internal
        self._transport: Optional[BaseTransport] = None
        self._running = False
        self._send_thread: Optional[threading.Thread] = None
        self._recv_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        self._transport = None
        if transport_config is not None:
            self._transport = transport_config.create_transport()


        # Attempt to create transport from provided parameters


    # --- public API -------------------------------------------------
    def start(self) -> None:
        """Start worker threads and connect transport."""
        with self._lock:
            if self._running:
                return
            if not self._transport:
                raise RuntimeError("no transport configured for this ConnectionOrganiserAdapter instance")
            self._transport.connect()
            self._running = True
            self._send_thread = threading.Thread(target=self._send_worker, name="CO_send", daemon=True)
            self._recv_thread = threading.Thread(target=self._recv_worker, name="CO_recv", daemon=True)
            self._send_thread.start()
            self._recv_thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop workers and disconnect transport."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        # join threads
        if self._send_thread:
            self._send_thread.join(timeout)
        if self._recv_thread:
            self._recv_thread.join(timeout)

        try:
            if self._transport:
                self._transport.disconnect()
        except Exception:
            pass

    def is_connected(self) -> bool:
        """Return transport connection state."""
        try:
            return bool(self._transport and self._transport.is_connected)
        except Exception:
            return False

    def send_command(self, cmd: str) -> None:
        """Queue a command to be sent to the device."""
        self.send_q.put(str(cmd))

    def receive_nowait(self) -> Optional[str]:
        try:
            return self.receive_q.get_nowait()
        except Exception:
            return None

    # --- internal workers -------------------------------------------
    def _send_worker(self) -> None:
        if not self._transport:
            return
        if self.debug:
            print("send_worker started")
        while self._running:
            try:
                cmd = self.send_q.get(timeout=0.2)
            except Exception:
                continue
            try:
                if self.debug:
                    print("sending:", cmd)
                self._transport.send(cmd)
            except Exception as e:
                if self.debug:
                    print("send error:", e)
            finally:
                # slight pause to be cooperative
                time.sleep(0.001)

    def _recv_worker(self) -> None:
        if not self._transport:
            return
        if self.debug:
            print("recv_worker started")
        while self._running:
            try:
                data = self._transport.receive()
                if data is not None:
                    if self.debug:
                        print("received:", data)
                    self.receive_q.put(data)
            except Exception as e:
                if self.debug:
                    print("receive error:", e)
            finally:
                time.sleep(0.001)


__all__ = ["ConnectionOrganiserAdapter"]
