def root_me(module):
    builtins = rm_define.__dict__["__builtins__"]
    real_import = builtins["__import__"] if isinstance(builtins, dict) else builtins.__import__
    return real_import(module, globals(), locals(), [], 0)


COMMAND_PORT = 40923
TELEMETRY_PORT = 40924

subprocess = None
select = None
json = None
os = None
time = None
bridge_process = None
bridge_stdout_buffer = ""


def mark_stage(stage):
    try:
        robot_ctrl.set_mode(rm_define.robot_mode_free)
        chassis_ctrl.set_rotate_speed(50)
        gimbal_ctrl.set_rotate_speed(90)
        chassis_ctrl.stop()
        gimbal_ctrl.rotate_with_speed(0, 0)
        if stage % 2 == 0:
            chassis_ctrl.rotate_with_time(rm_define.clockwise, 0.12)
            chassis_ctrl.stop()
        else:
            gimbal_ctrl.rotate_with_speed(35, 0)
            if time is not None:
                time.sleep(0.05)
            gimbal_ctrl.rotate_with_speed(0, 0)
    except Exception as exc:
        print("mark stage failed", stage, str(exc))


def init_root_modules():
    global subprocess, select, json, os, time
    subprocess = root_me("subprocess")
    select = root_me("select")
    json = root_me("json")
    os = root_me("os")
    time = root_me("time")


def enable_latest_fw_adb():
    try:
        proc = subprocess.Popen(
            "/system/bin/adb_en.sh",
            shell=True,
            executable="/system/bin/sh",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("root helper pid", proc.pid)
        time.sleep(0.5)
        print("root helper poll", proc.poll())
        return True
    except Exception as exc:
        print("root helper failed", str(exc))
        return False


CHILD_CODE = r'''
import json
import select
import socket
import sys
import time
import traceback

COMMAND_PORT = 40923
TELEMETRY_PORT = 40924


def send_parent(message):
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main():
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind(("0.0.0.0", COMMAND_PORT))
    rx.setblocking(False)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    stdin_fd = sys.stdin.fileno()
    sequence = 0
    send_parent({"type": "child_ready", "command_port": COMMAND_PORT, "telemetry_port": TELEMETRY_PORT})
    while True:
        readable, _, _ = select.select([rx, stdin_fd], [], [], 0.02)
        if rx in readable:
            data, source = rx.recvfrom(2048)
            reply = {
                "type": "root_child_echo",
                "sequence": sequence,
                "time_ms": int(time.time() * 1000),
                "bytes": len(data),
            }
            tx.sendto(json.dumps(reply, separators=(",", ":")).encode("utf-8"), (source[0], TELEMETRY_PORT))
            send_parent({"type": "udp_rx", "sequence": sequence, "bytes": len(data)})
            sequence += 1
        if stdin_fd in readable:
            line = sys.stdin.readline()
            if not line:
                break
            try:
                command = json.loads(line)
                if command.get("type") == "shutdown":
                    break
            except Exception:
                pass
    rx.close()
    tx.close()


try:
    main()
except Exception:
    send_parent({"type": "fatal_error", "traceback": traceback.format_exc()})
'''


def start_child():
    global bridge_process
    mark_stage(4)
    bridge_process = subprocess.Popen(
        ["/data/python_files/bin/python", "-u", "-c", CHILD_CODE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    os.set_blocking(bridge_process.stdout.fileno(), False)
    os.set_blocking(bridge_process.stderr.fileno(), False)
    print("child pid", bridge_process.pid)
    mark_stage(5)


def receive_child_messages():
    global bridge_stdout_buffer
    if bridge_process is None:
        return
    if bridge_process.poll() is not None:
        try:
            err = bridge_process.stderr.read()
            if err:
                print("child terminated", err.decode("utf-8", "replace"))
        except Exception:
            pass
        return
    try:
        readable, _, _ = select.select([bridge_process.stdout.fileno()], [], [], 0)
        if not readable:
            return
        chunk = os.read(bridge_process.stdout.fileno(), 4096)
        if not chunk:
            return
        bridge_stdout_buffer += chunk.decode("utf-8", "replace")
    except Exception as exc:
        print("child read failed", str(exc))
        return
    while "\n" in bridge_stdout_buffer:
        line, bridge_stdout_buffer = bridge_stdout_buffer.split("\n", 1)
        if line:
            print("child", line)


def stop_child():
    global bridge_process
    if bridge_process is None:
        return
    try:
        bridge_process.stdin.write(b'{"type":"shutdown"}\n')
        bridge_process.stdin.flush()
    except Exception:
        pass
    try:
        bridge_process.terminate()
    except Exception:
        pass
    bridge_process = None


def start():
    mark_stage(0)
    init_root_modules()
    mark_stage(1)
    enable_latest_fw_adb()
    mark_stage(3)
    start_child()
    try:
        while True:
            receive_child_messages()
            time.sleep(0.02)
    finally:
        stop_child()
