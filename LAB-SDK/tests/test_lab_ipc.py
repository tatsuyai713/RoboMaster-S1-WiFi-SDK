from __future__ import annotations

import ast
import json
import os
import select
import socket
import subprocess
import sys
import time
import unittest

from robomaster_lab_sdk.program import render_bridge_python


def _child_sources() -> dict[str, str]:
    tree = ast.parse(render_bridge_python())
    sources = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {
                "RECEIVER_PROCESS_CODE",
                "SENDER_PROCESS_CODE",
            }:
                sources[target.id] = ast.literal_eval(node.value)
    return sources


def _free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _read_frames(stream, count: int, timeout: float = 2.0) -> list[bytes]:  # noqa: ANN001
    deadline = time.monotonic() + timeout
    data = bytearray()
    frames = []
    while time.monotonic() < deadline:
        while len(data) >= 4:
            frame_size = int.from_bytes(data[:4], "big")
            if len(data) < 4 + frame_size:
                break
            frames.append(bytes(data[4:4 + frame_size]))
            del data[:4 + frame_size]
            if len(frames) >= count:
                return frames
        readable, _, _ = select.select(
            [stream.fileno()],
            [],
            [],
            max(0.0, deadline - time.monotonic()),
        )
        if not readable:
            break
        chunk = os.read(stream.fileno(), 4096)
        if not chunk:
            break
        data.extend(chunk)
    raise TimeoutError("framed child-process output timed out")


def _read_frames_until_idle(
    stream,
    timeout: float = 2.0,
    idle: float = 0.1,
) -> list[bytes]:  # noqa: ANN001
    deadline = time.monotonic() + timeout
    idle_deadline = None
    data = bytearray()
    frames = []
    while time.monotonic() < deadline:
        while len(data) >= 4:
            frame_size = int.from_bytes(data[:4], "big")
            if len(data) < 4 + frame_size:
                break
            frames.append(bytes(data[4:4 + frame_size]))
            del data[:4 + frame_size]
            idle_deadline = time.monotonic() + idle
        if frames and idle_deadline is not None:
            wait_until = min(deadline, idle_deadline)
        else:
            wait_until = deadline
        readable, _, _ = select.select(
            [stream.fileno()],
            [],
            [],
            max(0.0, wait_until - time.monotonic()),
        )
        if not readable:
            if frames and idle_deadline is not None:
                return frames
            break
        chunk = os.read(stream.fileno(), 4096)
        if not chunk:
            break
        data.extend(chunk)
    return frames


class LabIpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = _child_sources()

    def test_receiver_prioritizes_stop_and_keeps_latest_motion(self) -> None:
        port = _free_udp_port()
        source = self.sources["RECEIVER_PROCESS_CODE"].replace(
            "COMMAND_PORT = 40923",
            f"COMMAND_PORT = {port}",
        )
        source = source.replace(
            '    rx.bind(("0.0.0.0", COMMAND_PORT))',
            '    rx.bind(("0.0.0.0", COMMAND_PORT))\n'
            '    sys.stderr.write("READY\\n")\n'
            '    sys.stderr.flush()',
        )
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", source],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.assertEqual(process.stderr.readline(), b"READY\n")
            commands = (
                {"command_seq": 1, "x": 0.2},
                {
                    "command_seq": 2,
                    "module": "chassis",
                    "method": "stop",
                    "params": {},
                },
                {"command_seq": 3, "x": 0.8},
            )
            for command in commands:
                sender.sendto(
                    json.dumps(command, separators=(",", ":")).encode(),
                    ("127.0.0.1", port),
                )
            bodies = _read_frames_until_idle(process.stdout)
            decoded = [
                json.loads(body.split(b"\x00", 1)[1])
                for body in bodies
            ]
            sequences = [item["command_seq"] for item in decoded]
            self.assertIn(2, sequences)
            self.assertIn(3, sequences)
            self.assertLess(sequences.index(2), sequences.index(3))
            self.assertNotIn(1, sequences[sequences.index(2) + 1:])
        finally:
            sender.close()
            process.terminate()
            process.wait(timeout=1.0)
            process.stdout.close()
            process.stderr.close()

    def test_sender_accepts_partial_length_prefixed_writes(self) -> None:
        port = _free_udp_port()
        source = self.sources["SENDER_PROCESS_CODE"].replace(
            "TELEMETRY_PORT = 40924",
            f"TELEMETRY_PORT = {port}",
        )
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", port))
        receiver.settimeout(2.0)
        process = subprocess.Popen(
            [sys.executable, "-u", "-c", source],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            payload = b'{"type":"telemetry","sequence":7,"x":1.5}'
            body = b"127.0.0.1\x00" + payload
            frame = len(body).to_bytes(4, "big") + body
            for value in frame:
                process.stdin.write(bytes((value,)))
                process.stdin.flush()
            received, _addr = receiver.recvfrom(4096)
            self.assertEqual(received, payload)
        finally:
            receiver.close()
            process.terminate()
            process.wait(timeout=1.0)
            process.stdin.close()
            process.stderr.close()


if __name__ == "__main__":
    unittest.main()
