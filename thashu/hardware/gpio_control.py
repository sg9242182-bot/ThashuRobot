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

    def __new__(cls, port=None, baud=DEFAULT_BAUD):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init(port, baud)
        return cls._instance

    def _init(self, port, baud):
        self._serial = None
        self._port = port
        self._baud = baud
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._sequence_lock = threading.Lock()
        self._next_sequence = 1

        self._incoming = queue.Queue()
        self._last_heartbeat = 0.0
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
        """Return the configured port, or the first likely USB serial device."""
        if self._port:
            return self._port

        candidates = []
        for info in serial.tools.list_ports.comports():
            device = info.device or ""
            description = (info.description or "").lower()
            manufacturer = (info.manufacturer or "").lower()
            if device.startswith("/dev/ttyACM") or device.startswith("/dev/ttyUSB"):
                candidates.append((device, description, manufacturer))

        # Prefer an ESP32-like USB description when available, otherwise use
        # the first USB serial device. The final identity check is EVENT|READY.
        for device, description, manufacturer in candidates:
            if "esp32" in description or "espressif" in description or "esp32" in manufacturer:
                return device
        return candidates[0][0] if candidates else None

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
            print(f"[GPIO] ESP32 connected on {port} @ {self._baud}")
            return True
        except (serial.SerialException, OSError) as exc:
            with self._state_lock:
                self._serial = None
            print(f"[GPIO] ESP32 connection unavailable: {exc}")
            return False

    def _disconnect(self, reason="unknown"):
        with self._state_lock:
            serial_conn = self._serial
            self._serial = None

        if serial_conn is not None:
            try:
                serial_conn.close()
            except Exception:
                pass
            print(f"[GPIO] ESP32 disconnected: {reason}")

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
                self._disconnect(f"write failed: {exc}")
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
                    continue
                line = raw.decode("ascii", errors="replace").strip()
                if line:
                    self._incoming.put(line)
            except (serial.SerialException, OSError) as exc:
                self._disconnect(f"read failed: {exc}")
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
