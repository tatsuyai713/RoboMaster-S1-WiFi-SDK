from __future__ import annotations

import queue
import threading


class _EventStreamConnection:
    def __init__(self):
        self._sock_queue = queue.Queue(maxsize=256)

    def put(self, payload):
        try:
            self._sock_queue.put_nowait(payload)
        except queue.Full:
            try:
                self._sock_queue.get_nowait()
            except queue.Empty:
                return
            try:
                self._sock_queue.put_nowait(payload)
            except queue.Full:
                pass

    def read_buf(self):
        try:
            return self._sock_queue.get(timeout=0.1)
        except queue.Empty:
            return b""

    def disconnect(self):
        self.put(b"")


class LiveView:
    """Event-backed LiveView subset used by robomaster_ros."""

    def __init__(self, robot):
        self._robot = robot
        self._video_stream_conn = _EventStreamConnection()
        self._audio_stream_conn = _EventStreamConnection()
        self._video_decoder_thread = None
        self._audio_decoder_thread = None
        self._video_frame_queue = queue.Queue(maxsize=64)
        self._audio_frame_queue = queue.Queue(maxsize=32)
        self._video_streaming = False
        self._audio_streaming = False
        self._video_frame_count = 0
        self._audio_frame_count = 0
        self._video_codec = None

    def _on_video(self, payload):
        if self._video_streaming:
            self._video_stream_conn.put(payload)

    def _on_audio(self, payload):
        if self._audio_streaming:
            self._audio_stream_conn.put(payload)

    def start_video_stream(self, display=True, addr=None, ip_proto="udp"):
        if self._video_streaming:
            return True
        self._video_streaming = True
        self._robot.on("video", self._on_video)
        self._video_decoder_thread = threading.Thread(
            target=self._video_decoder_task,
            daemon=True,
        )
        self._video_decoder_thread.start()
        return True

    def stop_video_stream(self):
        self._video_streaming = False
        self._robot.off("video", self._on_video)
        self._video_stream_conn.disconnect()
        if self._video_decoder_thread is not None:
            self._video_decoder_thread.join(timeout=1.0)
        self._video_decoder_thread = None
        return True

    def start_audio_stream(self, addr=None, ip_proto="udp"):
        if self._audio_streaming:
            return True
        self._audio_streaming = True
        self._robot.on("audio_rx", self._on_audio)
        self._audio_decoder_thread = threading.Thread(
            target=self._audio_decoder_task,
            daemon=True,
        )
        self._audio_decoder_thread.start()
        return True

    def stop_audio_stream(self):
        self._audio_streaming = False
        self._robot.off("audio_rx", self._on_audio)
        self._audio_stream_conn.disconnect()
        if self._audio_decoder_thread is not None:
            self._audio_decoder_thread.join(timeout=1.0)
        self._audio_decoder_thread = None
        return True

    def _h264_decode(self, data):
        try:
            import av

            if self._video_codec is None:
                self._video_codec = av.CodecContext.create("h264", "r")
            images = []
            for packet in self._video_codec.parse(data):
                for frame in self._video_codec.decode(packet):
                    images.append(frame.to_ndarray(format="bgr24"))
            return images
        except Exception:
            return []

    def _video_decoder_task(self):
        while self._video_streaming:
            data = self._video_stream_conn.read_buf()
            if not data:
                continue
            for frame in self._h264_decode(data):
                self._video_frame_count += 1
                try:
                    self._video_frame_queue.put_nowait(frame)
                except queue.Full:
                    try:
                        self._video_frame_queue.get_nowait()
                        self._video_frame_queue.put_nowait(frame)
                    except (queue.Empty, queue.Full):
                        pass

    def _audio_decoder_task(self):
        while self._audio_streaming:
            data = self._audio_stream_conn.read_buf()
            if not data:
                continue
            self._audio_frame_count += 1
            try:
                self._audio_frame_queue.put_nowait(data)
            except queue.Full:
                pass

    def stop(self):
        if self._video_streaming:
            self.stop_video_stream()
        if self._audio_streaming:
            self.stop_audio_stream()


class Media:
    def __init__(self, robot) -> None:
        self._robot = robot
