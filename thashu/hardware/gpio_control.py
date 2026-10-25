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

    Phase 1 contract:
      - USB CDC serial, 115200 baud
      - line-delimited ASCII frames
      - Pi commands: CMD|sequence|...
      - ESP32 responses/events: ACK|..., TEL|..., EVENT|..., FAULT|...
      - heartbeat every 100 ms
      - ESP32 watchdog: 500 ms (enforced on ESP32)

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
        for device, _, _ in candidates:
            if device == self._port:
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
            sequence = self._next_sequence
            self._next_sequence += 1
            if self._next_sequence > 0x7FFFFFFF:
                self._next_sequence = 1
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
        frame = f"CMD|{sequence}|{command}\n".encode("ascii")

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

    def wait_for_ack(self, sequence, timeout=0.75):
        """Wait for one command ACK; return its payload (for example, OK or ERROR|OBSTACLE)."""
        deadline = time.monotonic() + timeout
        with self._ack_condition:
            while sequence not in self._acknowledgements:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._ack_condition.wait(remaining)
            return self._acknowledgements.pop(sequence)

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
        while not self._stop_event.is_set():
            with self._state_lock:
                serial_conn = self._serial

            if serial_conn is None:
                self._stop_event.wait(0.05)
                continue

            try:
                raw = serial_conn.readline()
                if not raw:
                    with self._state_lock:
                        is_current = self._serial is serial_conn
                        last_rx = self._last_rx_monotonic
                    if is_current and time.monotonic() - last_rx >= self.RX_SILENCE_TIMEOUT:
                        self._disconnect(
                            f"no ESP32 serial data for {self.RX_SILENCE_TIMEOUT:.0f}s",
                            expected_serial=serial_conn,
                        )
                    continue

                with self._state_lock:
                    if self._serial is not serial_conn:
                        continue
                    self._last_rx_monotonic = time.monotonic()

                line = raw.decode("ascii", errors="replace").strip()
                if line:
                    self._incoming.put(line)
                    if line.startswith("ACK|"):
                        fields = line.split("|", 2)
                        try:
                            sequence = int(fields[1])
                            result = fields[2] if len(fields) == 3 else ""
                        except (ValueError, IndexError):
                            sequence = None
                            result = ""

                        if sequence is not None and result != "ALIVE":
                            with self._ack_condition:
                                self._acknowledgements[sequence] = result
                                while len(self._acknowledgements) > 128:
                                    self._acknowledgements.pop(next(iter(self._acknowledgements)))
                                self._ack_condition.notify_all()
                        if result.startswith("ERROR"):
                            print(f"[ESP32] {line}")
                    if line.startswith(("EVENT|", "FAULT|")):
                        print(f"[ESP32] {line}")
                        self._events.put(line)
            except (serial.SerialException, OSError) as exc:
                self._disconnect(f"read failed: {exc}", expected_serial=serial_conn)
            except Exception as exc:
                # A malformed inbound frame must not kill the reader thread.
                print(f"[GPIO] ESP32 receive error: {exc}")

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
