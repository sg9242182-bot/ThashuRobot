import glob
import os
import queue
import serial
import serial.tools.list_ports
import threading
import time


class GPIOControl:
    """
    Singleton transport for the Raspberry Pi <-> ESP32 hardware controller.

    Current protocol-v0 contract:
      - USB CDC serial, 115200 baud, newline-delimited ASCII
      - Pi commands: CMD|sequence|payload...
      - ACK replies: ACK|sequence|result...
      - Encoder replies: ENC|sequence|count0|count1|count2|count3
      - Telemetry: TEL|0|SENSORS|...
      - No session ID or command-version field is transmitted
      - heartbeat every 100 ms; ESP32 watchdog is 500 ms

    This class owns transport/reconnection only. Motor, eye and servo classes
    remain high-level command owners and do not know GPIO pin assignments.
    """

    _instance = None
    _instance_lock = threading.Lock()

    HEARTBEAT_INTERVAL = 0.100
    RECONNECT_INTERVAL = 1.0
    DEFAULT_BAUD = 115200
    SERIAL_TIMEOUT = 0.2
    RX_SILENCE_TIMEOUT = 2.0
    MAX_FRAME_BYTES = 128

    def __new__(cls, port=None, baud=DEFAULT_BAUD):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init(port, baud)
        return cls._instance

    def _init(self, port, baud):
        self._serial = None
        self._configured_port = port
        self._port = port
        self._baud = baud
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._sequence_lock = threading.Lock()
        self._next_sequence = 1

        self._incoming = queue.Queue()
        self._events = queue.Queue()
        self._ack_condition = threading.Condition()
        self._acknowledgements = {}
        self._last_heartbeat = 0.0
        self._last_rx_monotonic = 0.0
        self._sensor_snapshot = None
        self._last_connect_attempt = 0.0
        self._stop_event = threading.Event()

        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="thashu-esp32-reader",
            daemon=True,
        )
        self._transport_thread = threading.Thread(
            target=self._transport_loop,
            name="thashu-esp32-transport",
            daemon=True,
        )

        self._connect()
        self._reader_thread.start()
        self._transport_thread.start()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _resolve_port(self):
        """Resolve a configured port or rediscover the ESP32 after USB re-enumeration."""
        if self._configured_port:
            return self._configured_port

        candidates = []
        for info in serial.tools.list_ports.comports():
            device = info.device or ""
            if not (device.startswith("/dev/ttyACM") or device.startswith("/dev/ttyUSB")):
                continue

            description = (info.description or "").lower()
            manufacturer = (info.manufacturer or "").lower()
            candidates.append((device, description, manufacturer))

        # Keep the current device while it still exists, then prefer an ESP32
        # description. USB port numbers can change after a disconnect.
        current_realpath = os.path.realpath(self._port) if self._port else None
        for device, _, _ in candidates:
            if current_realpath and os.path.realpath(device) == current_realpath:
                return self._stable_device_path(device)
        for device, description, manufacturer in candidates:
            if "esp32" in description or "espressif" in description or "esp32" in manufacturer:
                return self._stable_device_path(device)
        if candidates:
            return self._stable_device_path(candidates[0][0])
        return None

    @staticmethod
    def _stable_device_path(device):
        """Prefer a persistent /dev/serial/by-id symlink over a changing ttyUSB number."""
        resolved_device = os.path.realpath(device)
        for candidate in glob.glob("/dev/serial/by-id/*"):
            if os.path.realpath(candidate) == resolved_device:
                return candidate
        return device

    def _connect(self):
        port = self._resolve_port()
        if not port:
            return False

        try:
            serial_conn = serial.Serial(
                port,
                self._baud,
                timeout=self.SERIAL_TIMEOUT,
                write_timeout=self.SERIAL_TIMEOUT,
            )
            with self._state_lock:
                self._serial = serial_conn
                self._port = port
                self._last_heartbeat = 0.0
                self._last_rx_monotonic = time.monotonic()
            print(f"[GPIO] ESP32 connected on {port} @ {self._baud}")
            return True
        except (serial.SerialException, OSError) as exc:
            with self._state_lock:
                self._serial = None
            print(f"[GPIO] ESP32 connection unavailable: {exc}")
            return False

    def _disconnect(self, reason="unknown", expected_serial=None):
        with self._state_lock:
            # A delayed failure from an old reader/writer must not close a
            # connection that has already been restored.
            if expected_serial is not None and self._serial is not expected_serial:
                return False
            serial_conn = self._serial
            self._serial = None

        if serial_conn is not None:
            try:
                serial_conn.close()
            except Exception:
                pass
            print(f"[GPIO] ESP32 disconnected: {reason}")
        return serial_conn is not None

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def _allocate_sequence(self):
        with self._sequence_lock:
            if self._next_sequence > 0x7FFFFFFF:
                return None
            sequence = self._next_sequence
            self._next_sequence += 1
            return sequence

    def send(self, command: str):
        """
        Send a protocol payload.

        `command` is the unframed command body, e.g.:
            MOTOR|FORWARD|200
            STOP
            EYES|HAPPY

        Returns the sequence number when the frame was written, otherwise None.
        """
        if not command or "\n" in command or "\r" in command:
            raise ValueError("command must be a non-empty single-line payload")

        sequence = self._allocate_sequence()
        if sequence is None:
            return None
        frame = (
            f"CMD|{sequence}|{command}\n"
        ).encode("ascii")

        with self._write_lock:
            with self._state_lock:
                serial_conn = self._serial

            if serial_conn is None:
                return None

            try:
                serial_conn.write(frame)
                return sequence
            except (serial.SerialException, OSError) as exc:
                self._disconnect(f"write failed: {exc}", expected_serial=serial_conn)
                return None

    def heartbeat(self):
        return self.send("HEARTBEAT")

    def read_line(self, timeout=0.0):
        """Return the next received protocol line, or an empty string."""
        try:
            line = self._incoming.get(timeout=timeout)
        except queue.Empty:
            return ""
        return line

    def drain_messages(self):
        """Return all currently queued inbound protocol lines."""
        messages = []
        while True:
            try:
                messages.append(self._incoming.get_nowait())
            except queue.Empty:
                return messages

    def drain_events(self):
        """Return queued ESP32 EVENT/FAULT lines for high-level handling."""
        events = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def _record_acknowledgement(self, line):
        """Store a valid protocol-v0 ACK correlated by its sequence number."""
        fields = line.split("|", 2)
        if len(fields) != 3 or fields[0] != "ACK":
            return
        try:
            sequence = int(fields[1])
        except ValueError:
            return
        result = fields[2]
        if sequence < 0 or not (
            result in ("OK", "ALIVE") or result.startswith("ERROR|")
        ):
            return
        if result == "ALIVE":
            return

        with self._ack_condition:
            self._acknowledgements[sequence] = result
            while len(self._acknowledgements) > 128:
                self._acknowledgements.pop(next(iter(self._acknowledgements)))
            self._ack_condition.notify_all()
        if result.startswith("ERROR"):
            print(f"[ESP32] {line}")

    def wait_for_ack(self, sequence, timeout=0.75):
        """Wait for this process session's ACK; return OK or ERROR|reason."""
        key = sequence
        deadline = time.monotonic() + timeout
        with self._ack_condition:
            while key not in self._acknowledgements:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._ack_condition.wait(remaining)
            return self._acknowledgements.pop(key)

    # ------------------------------------------------------------------
    # Background transport
    # ------------------------------------------------------------------

    def _transport_loop(self):
        while not self._stop_event.is_set():
            now = time.monotonic()

            if not self.is_connected():
                if now - self._last_connect_attempt >= self.RECONNECT_INTERVAL:
                    self._last_connect_attempt = now
                    self._connect()
            elif now - self._last_heartbeat >= self.HEARTBEAT_INTERVAL:
                self._last_heartbeat = now
                self.heartbeat()

            self._stop_event.wait(0.01)

    def _reader_loop(self):
        rx_buffer = bytearray()
        discarding_oversized_frame = False
        reader_serial = None

        while not self._stop_event.is_set():
            with self._state_lock:
                serial_conn = self._serial

            if serial_conn is None:
                rx_buffer.clear()
                discarding_oversized_frame = False
                reader_serial = None
                self._stop_event.wait(0.05)
                continue

            if serial_conn is not reader_serial:
                # Never join a partial frame received before a disconnect to
                # bytes from a newly opened serial connection.
                rx_buffer.clear()
                discarding_oversized_frame = False
                reader_serial = serial_conn

            try:
                waiting = serial_conn.in_waiting
                raw = serial_conn.read(max(1, min(waiting or 1, self.MAX_FRAME_BYTES + 1)))
                if not raw:
                    with self._state_lock:
                        is_current = self._serial is serial_conn
                        last_rx = self._last_rx_monotonic
                    if is_current and time.monotonic() - last_rx >= self.RX_SILENCE_TIMEOUT:
                        self._disconnect(
                            f"no ESP32 serial data for {self.RX_SILENCE_TIMEOUT:.0f}s",
                            expected_serial=serial_conn,
                        )
                    self._stop_event.wait(0.01)
                    continue

                with self._state_lock:
                    if self._serial is not serial_conn:
                        continue
                    self._last_rx_monotonic = time.monotonic()

                discarding_oversized_frame = self._consume_serial_bytes(
                    raw, rx_buffer, discarding_oversized_frame
                )
            except (serial.SerialException, OSError) as exc:
                self._disconnect(f"read failed: {exc}", expected_serial=serial_conn)
            except Exception as exc:
                # A malformed inbound frame must not kill the reader thread.
                print(f"[GPIO] ESP32 receive error: {exc}")

    def _consume_serial_bytes(self, chunk, rx_buffer, discarding_oversized_frame=False):
        """Assemble newline-delimited frames without retaining partial/oversized lines."""
        for byte in chunk:
            if discarding_oversized_frame:
                if byte == ord("\n"):
                    discarding_oversized_frame = False
                continue

            if byte == ord("\n"):
                frame = bytes(rx_buffer)
                rx_buffer.clear()
                if frame.endswith(b"\r"):
                    frame = frame[:-1]
                if frame:
                    self._process_inbound_frame(frame)
                continue

            if len(rx_buffer) >= self.MAX_FRAME_BYTES:
                rx_buffer.clear()
                discarding_oversized_frame = True
                continue

            rx_buffer.append(byte)

        return discarding_oversized_frame

    def _process_inbound_frame(self, frame):
        """Decode and dispatch one complete ASCII protocol frame."""
        try:
            line = frame.decode("ascii")
        except UnicodeDecodeError:
            print("[GPIO] Ignoring non-ASCII ESP32 frame")
            return

        self._incoming.put(line)
        if line.startswith("TEL|"):
            self._update_sensor_snapshot(line)
        if line.startswith("ACK|"):
            self._record_acknowledgement(line)
        if line.startswith(("EVENT|", "FAULT|")):
            print(f"[ESP32] {line}")
            self._events.put(line)

    def _update_sensor_snapshot(self, line):
        """Parse protocol-v0 sensor telemetry and publish a fresh snapshot."""
        fields = line.split("|")
        if len(fields) != 11 or fields[:3] != ["TEL", "0", "SENSORS"]:
            return

        raw = dict(zip(fields[3::2], fields[4::2]))
        labels = ("TOF_L", "TOF_C", "TOF_R", "US_REAR")
        if any(label not in raw for label in labels):
            return

        def parse_value(value):
            if value == "FAR":
                return "FAR"
            if value == "NA":
                return None
            try:
                distance = int(value)
            except (TypeError, ValueError):
                return False
            return distance if distance >= 0 else False

        parsed = [parse_value(raw[label]) for label in labels]
        if any(value is False for value in parsed):
            return

        snapshot = {
            "tof_left_mm": parsed[0],
            "tof_center_mm": parsed[1],
            "tof_right_mm": parsed[2],
            "rear_mm": parsed[3],
            "received_at": time.monotonic(),
        }
        with self._state_lock:
            self._sensor_snapshot = snapshot

    def get_sensor_snapshot(self, max_age=0.2):
        """Return a copy of fresh sensor telemetry, or None if missing/stale.

        Numeric values are millimetres; out-of-range channels are "FAR";
        unavailable channels are None. The timestamp uses time.monotonic().
        """
        now = time.monotonic()
        with self._state_lock:
            snapshot = self._sensor_snapshot
            if snapshot is None or now - snapshot["received_at"] > max_age:
                return None
            return dict(snapshot)

    # ------------------------------------------------------------------
    # Lifecycle / status
    # ------------------------------------------------------------------

    def is_connected(self):
        with self._state_lock:
            return self._serial is not None and self._serial.is_open

    def close(self):
        """Stop background transport threads and close the serial connection."""
        self._stop_event.set()
        self._disconnect("transport closed")

    @classmethod
    def reset_singleton_for_tests(cls):
        """Reset the singleton so isolated transport tests can create a new instance."""
        with cls._instance_lock:
            if cls._instance is not None:
                try:
                    cls._instance.close()
                except Exception:
                    pass
            cls._instance = None
