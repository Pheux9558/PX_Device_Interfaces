Transports
==========

This package provides transport implementations used by the connection
adapter layer. It's intentionally small and focused on testability so you
can implement transports without hardware.

Files:
- `base.py` — `BaseTransport` abstract interface (connect/disconnect/send/receive/is_connected).
- `mock.py` — `MockTransport`, an in-memory transport useful for unit tests.
- `__init__.py` — simple factory `create_transport(transport_type, settings)`.

Adding a new transport:

1. Create `python/transports/<your_transport>.py` implementing `BaseTransport`.
2. Add the implementation to the factory in `__init__.py` (map a transport `type` string to your class).
3. Add unit tests under `tests/` that exercise connect/send/receive using the mock and your transport.

Use the `MockTransport` for writing tests and exercising queue/worker logic
without touching real devices.
