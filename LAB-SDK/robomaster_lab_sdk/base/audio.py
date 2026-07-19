from __future__ import annotations

from pathlib import Path
import queue
import threading
import time

from .action import (
    ACTION_ABORTED,
    ACTION_FAILED,
    ACTION_RUNNING,
    ACTION_SUCCEEDED,
    Action,
)

MIC_SAMPLE_RATE = 48000
MIC_CHANNELS = 1
MIC_SAMPLE_WIDTH_BYTES = 2
MIC_BLOCK_FRAMES = 480
MIC_AUDIO_CHUNK_BYTES = (
    MIC_BLOCK_FRAMES * MIC_CHANNELS * MIC_SAMPLE_WIDTH_BYTES
)
MIC_START_PAYLOAD = bytes.fromhex(
    "00000001000500d2110000000000000000"
)
MIC_STOP_PAYLOAD = bytes.fromhex(
    "0200000000000000000000000000000000"
)


class OpusDecoder:
    """Decode S1 Opus packets to 48 kHz mono signed-16 PCM."""

    def __init__(self) -> None:
        self._av = None
        self._codec = None
        self._resampler = None
        try:
            import av

            codec = av.CodecContext.create("opus", "r")
            codec.sample_rate = MIC_SAMPLE_RATE
            codec.layout = "mono"
            self._av = av
            self._codec = codec
            self._resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=MIC_SAMPLE_RATE,
            )
        except Exception:
            # Raw Opus delivery remains available without the optional codec.
            pass

    @property
    def available(self) -> bool:
        return (
            self._av is not None
            and self._codec is not None
            and self._resampler is not None
        )

    @staticmethod
    def _frames(value):  # noqa: ANN001
        if value is None:
            return ()
        if isinstance(value, (list, tuple)):
            return value
        return (value,)

    def decode(self, payload: bytes) -> bytes | None:
        if not payload or not self.available:
            return None
        try:
            decoded = self._codec.decode(self._av.Packet(payload))
        except Exception:
            return None
        chunks: list[bytes] = []
        for frame in decoded:
            try:
                converted = self._resampler.resample(frame)
            except Exception:
                continue
            for output in self._frames(converted):
                byte_count = (
                    int(output.samples)
                    * MIC_CHANNELS
                    * MIC_SAMPLE_WIDTH_BYTES
                )
                if output.planes:
                    chunks.append(bytes(output.planes[0])[:byte_count])
        return b"".join(chunks) or None


class AudioFileAction(Action):
    """Host-tracked Action for real-time file streaming to the S1 speaker."""

    def __init__(self, audio: "Audio", filename: str) -> None:
        super().__init__(completed=False, accepted=True)
        self.filename = str(filename)
        self._audio = audio
        self._cancel = threading.Event()
        self._state = ACTION_RUNNING
        self._thread = threading.Thread(
            target=self._run,
            name="robomaster-s1-audio-file",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        try:
            completed = self._audio.play_file(
                self.filename,
                stop_event=self._cancel,
            )
        except Exception:
            self._failure_reason = -1
            self._changeto_state(ACTION_FAILED)
            return
        self._changeto_state(
            ACTION_SUCCEEDED if completed else ACTION_ABORTED
        )

    def _abort(self) -> None:
        self._cancel.set()
        super()._abort()


class Audio:
    """S1 bidirectional audio transport captured from the Unified app."""

    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._block_index = 0
        self._microphone_stream = None
        self._microphone_callback_user = None
        self._tx_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=8)
        self._tx_stop = threading.Event()
        self._tx_thread: threading.Thread | None = None
        self._play_lock = threading.Lock()
        self._microphone_owns_play_lock = False
        self._file_action: AudioFileAction | None = None

    def request_rx(self) -> bool:
        """Ask the robot to start sending Opus microphone frames."""
        self._robot.send_duss(
            0x02,
            0x01,
            0x40,
            0x3F,
            0x1E,
            b"\x01",
        )
        return True

    def start_tx(self) -> bool:
        """Start a PC-to-robot 48 kHz mono PCM audio session."""
        self._block_index = 0
        self._robot.send_duss(
            0x02,
            0x09,
            0x40,
            0x3F,
            0x5F,
            MIC_START_PAYLOAD,
        )
        return True

    def stop_tx(self) -> bool:
        self._robot.send_duss(
            0x02,
            0x09,
            0x40,
            0x3F,
            0x5F,
            MIC_STOP_PAYLOAD,
        )
        return True

    def send_pcm_block(self, pcm: bytes) -> bool:
        if not pcm:
            return False
        view = memoryview(pcm)
        for offset in range(0, len(view), MIC_AUDIO_CHUNK_BYTES):
            chunk = bytes(view[offset : offset + MIC_AUDIO_CHUNK_BYTES])
            self._robot.send_audio_block(chunk, self._block_index)
            self._block_index = (self._block_index + 1) & 0xFFFFFFFF
        return True

    def _queue_pcm(self, pcm: bytes) -> None:
        if not pcm:
            return
        try:
            self._tx_queue.put_nowait(pcm)
        except queue.Full:
            try:
                self._tx_queue.get_nowait()
            except queue.Empty:
                return
            try:
                self._tx_queue.put_nowait(pcm)
            except queue.Full:
                pass

    def _microphone_callback(
        self,
        indata,  # noqa: ANN001
        frames: int,
        time_info,  # noqa: ANN001
        status,  # noqa: ANN001
    ) -> None:
        del frames, time_info, status
        pcm = bytes(indata)
        callback = self._microphone_callback_user
        if callback is not None:
            try:
                callback(pcm)
            except Exception:
                pass
        self._queue_pcm(pcm)

    def _tx_loop(self) -> None:
        while not self._tx_stop.is_set():
            try:
                pcm = self._tx_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if pcm is None:
                break
            self.send_pcm_block(pcm)

    def start_microphone(
        self,
        device=None,  # noqa: ANN001
        callback=None,  # noqa: ANN001
    ) -> bool:
        """Stream the Host microphone to S1 without blocking the audio callback."""
        if self._microphone_stream is not None:
            return True
        if not self._play_lock.acquire(blocking=False):
            raise RuntimeError("Another Host-to-S1 audio stream is active")
        self._microphone_owns_play_lock = True
        try:
            import sounddevice
        except ImportError as exc:
            self._microphone_owns_play_lock = False
            self._play_lock.release()
            raise RuntimeError(
                "Microphone streaming requires sounddevice"
            ) from exc
        try:
            self.start_tx()
        except Exception:
            self._microphone_owns_play_lock = False
            self._play_lock.release()
            raise
        self._microphone_callback_user = callback
        self._tx_stop.clear()
        self._tx_thread = threading.Thread(
            target=self._tx_loop,
            name="robomaster-s1-audio-tx",
            daemon=True,
        )
        self._tx_thread.start()
        try:
            stream = sounddevice.RawInputStream(
                samplerate=MIC_SAMPLE_RATE,
                channels=MIC_CHANNELS,
                dtype="int16",
                blocksize=MIC_BLOCK_FRAMES,
                device=device,
                callback=self._microphone_callback,
            )
            stream.start()
            self._microphone_stream = stream
        except Exception:
            try:
                self._stop_tx_worker()
                self.stop_tx()
            finally:
                self._microphone_owns_play_lock = False
                self._play_lock.release()
            raise
        return True

    def _stop_tx_worker(self) -> None:
        self._tx_stop.set()
        try:
            self._tx_queue.put_nowait(None)
        except queue.Full:
            try:
                self._tx_queue.get_nowait()
                self._tx_queue.put_nowait(None)
            except (queue.Empty, queue.Full):
                pass
        if self._tx_thread is not None:
            self._tx_thread.join(timeout=1.0)
        self._tx_thread = None
        while True:
            try:
                self._tx_queue.get_nowait()
            except queue.Empty:
                break

    def stop_microphone(self) -> bool:
        stream = self._microphone_stream
        self._microphone_stream = None
        self._microphone_callback_user = None
        try:
            if stream is not None:
                try:
                    stream.stop()
                finally:
                    stream.close()
        finally:
            self._stop_tx_worker()
            if stream is not None:
                try:
                    self.stop_tx()
                finally:
                    if self._microphone_owns_play_lock:
                        self._microphone_owns_play_lock = False
                        self._play_lock.release()
            elif self._microphone_owns_play_lock:
                self._microphone_owns_play_lock = False
                self._play_lock.release()
        return True

    @staticmethod
    def _pcm_from_audio_file(filename: str):
        try:
            import av
        except ImportError as exc:
            raise RuntimeError("Audio file playback requires av") from exc
        path = Path(filename).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        with av.open(str(path)) as container:
            if not container.streams.audio:
                raise ValueError(f"No audio stream found in {path}")
            resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=MIC_SAMPLE_RATE,
            )
            pending = bytearray()
            for frame in container.decode(audio=0):
                converted = resampler.resample(frame)
                frames = (
                    converted
                    if isinstance(converted, (list, tuple))
                    else (converted,)
                )
                for output in frames:
                    if output is None or not output.planes:
                        continue
                    byte_count = (
                        int(output.samples)
                        * MIC_CHANNELS
                        * MIC_SAMPLE_WIDTH_BYTES
                    )
                    pending.extend(bytes(output.planes[0])[:byte_count])
                    while len(pending) >= MIC_AUDIO_CHUNK_BYTES:
                        yield bytes(pending[:MIC_AUDIO_CHUNK_BYTES])
                        del pending[:MIC_AUDIO_CHUNK_BYTES]
            if pending:
                pending.extend(
                    b"\x00" * (MIC_AUDIO_CHUNK_BYTES - len(pending))
                )
                yield bytes(pending)

    def play_file(
        self,
        filename: str,
        stop_event: threading.Event | None = None,
    ) -> bool:
        """Decode and stream an audio file to S1 at real-time PCM cadence."""
        if not self._play_lock.acquire(blocking=False):
            raise RuntimeError("Another Host-to-S1 audio stream is active")
        try:
            self.start_tx()
            deadline = time.monotonic()
            for pcm in self._pcm_from_audio_file(filename):
                if stop_event is not None and stop_event.is_set():
                    return False
                self.send_pcm_block(pcm)
                deadline += MIC_BLOCK_FRAMES / MIC_SAMPLE_RATE
                delay = deadline - time.monotonic()
                if delay > 0.0:
                    if stop_event is None:
                        time.sleep(delay)
                    elif stop_event.wait(delay):
                        return False
            return True
        finally:
            try:
                self.stop_tx()
            finally:
                self._play_lock.release()

    def play_file_action(self, filename: str) -> AudioFileAction:
        action = self._file_action
        if action is not None and not action.is_completed:
            raise RuntimeError("Another audio file Action is active")
        action = AudioFileAction(self, filename)
        self._file_action = action
        return action

    def close(self) -> None:
        if self._file_action is not None and not self._file_action.is_completed:
            self._file_action._abort()
            self._file_action._thread.join(timeout=2.0)
        self.stop_microphone()
