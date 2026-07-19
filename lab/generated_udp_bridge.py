# Legacy generated bridge sample. LAB-SDK now owns generated Lab bridge settings.
# RootMe child-process UDP bridge. Upload target: /python/python_raw.dsp

COMMAND_PORT = 40923
TELEMETRY_PORT = 40924
COMMAND_TIMEOUT_SEC = 0.3
CONTROL_PERIOD_SEC = 0.02
TELEMETRY_PERIOD_SEC = 0.02
MAX_CHASSIS_SPEED = 1.0
MAX_CHASSIS_YAW_SPEED = 120.0
MAX_GIMBAL_SPEED = 120.0


def rm_import(module):
    for provider_name in ("rm_define", "rm_log", "Random"):
        provider = globals().get(provider_name)
        if provider is None:
            continue
        try:
            builtins = provider.__dict__["__builtins__"]
            real_import = builtins["__import__"] if isinstance(builtins, dict) else builtins.__import__
            return real_import(module, globals(), locals(), [], 0)
        except Exception:
            pass
    raise RuntimeError("RootMe provider was not found: tried rm_define, rm_log, Random")


subprocess = None
select = None
json = None
os = None
sys = None
time = None
adb_process = None


def init_root_modules():
    global subprocess, select, json, os, sys, time
    if subprocess is None:
        subprocess = rm_import("subprocess")
    if select is None:
        select = rm_import("select")
    if json is None:
        json = rm_import("json")
    if os is None:
        os = rm_import("os")
    if sys is None:
        sys = rm_import("sys")
    if time is None:
        time = rm_import("time")


def enable_latest_fw_adb():
    global adb_process
    try:
        adb_process = subprocess.Popen(
            "/system/bin/adb_en.sh",
            shell=True,
            executable="/system/bin/sh",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("Latest FW root helper started:", adb_process.pid)
        time.sleep(0.5)
        print("Latest FW root helper poll:", adb_process.poll())
        return True
    except Exception as exc:
        print("Latest FW root helper failed:", str(exc))
        return False


SOCKET_BRIDGE_CODE = r'''
import json
import select
import socket
import sys
import time
import traceback

COMMAND_PORT = 40923
TELEMETRY_PORT = 40924
COMMAND_TIMEOUT_SEC = 0.3


def send_parent(message):
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\\n")
    sys.stdout.flush()


def number(command, *names):
    for name in names:
        if name in command:
            try:
                return float(command.get(name, 0.0))
            except Exception:
                return 0.0
    return 0.0


def main():
    command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    command_socket.bind(("0.0.0.0", COMMAND_PORT))
    command_socket.setblocking(False)
    telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    stdin_fd = sys.stdin.fileno()
    last_command_time = time.time()
    last_sequence = 0
    timeout_notified = False
    last_source = None
    send_parent({"type": "bridge_ready", "command_port": COMMAND_PORT, "telemetry_port": TELEMETRY_PORT})
    while True:
        readable, _, _ = select.select([command_socket, stdin_fd], [], [], 0.01)
        if command_socket in readable:
            try:
                data, source = command_socket.recvfrom(2048)
                last_source = source
                command = json.loads(data.decode("utf-8"))
                sequence = int(command.get("sequence", last_sequence + 1))
                send_parent({
                    "type": "command",
                    "sequence": sequence,
                    "stop": bool(command.get("stop", False)),
                    "fire": bool(command.get("fire", False)),
                    "vx": number(command, "vx", "x"),
                    "vy": number(command, "vy", "y"),
                    "chassis_yaw_rate": number(command, "chassis_yaw_rate", "z", "chassis_yaw"),
                    "gimbal_yaw_rate": number(command, "gimbal_yaw_rate", "gimbal_yaw"),
                    "gimbal_pitch_rate": number(command, "gimbal_pitch_rate", "gimbal_pitch"),
                })
                last_sequence = sequence
                last_command_time = time.time()
                timeout_notified = False
            except Exception as exc:
                send_parent({"type": "receive_error", "message": str(exc)})
        if stdin_fd in readable:
            line = sys.stdin.readline()
            if not line:
                break
            try:
                message = json.loads(line)
                if message.get("type") == "telemetry" and last_source is not None:
                    telemetry_socket.sendto(
                        json.dumps(message, separators=(",", ":")).encode("utf-8"),
                        (last_source[0], TELEMETRY_PORT),
                    )
                elif message.get("type") == "shutdown":
                    break
            except Exception as exc:
                send_parent({"type": "telemetry_error", "message": str(exc)})
        now = time.time()
        if now - last_command_time > COMMAND_TIMEOUT_SEC and not timeout_notified:
            last_sequence += 1
            send_parent({
                "type": "command",
                "sequence": last_sequence,
                "timeout": True,
                "stop": True,
                "fire": False,
                "vx": 0.0,
                "vy": 0.0,
                "chassis_yaw_rate": 0.0,
                "gimbal_yaw_rate": 0.0,
                "gimbal_pitch_rate": 0.0,
            })
            timeout_notified = True
    command_socket.close()
    telemetry_socket.close()


try:
    main()
except Exception:
    send_parent({"type": "fatal_error", "traceback": traceback.format_exc()})
'''

latest_command = {
    "sequence": 0,
    "stop": True,
    "fire": False,
    "vx": 0.0,
    "vy": 0.0,
    "chassis_yaw_rate": 0.0,
    "gimbal_yaw_rate": 0.0,
    "gimbal_pitch_rate": 0.0,
}
bridge_process = None
bridge_stdout_buffer = ""
telemetry_sequence = 0


def clamp(value, minimum, maximum):
    try:
        value = float(value)
    except Exception:
        value = 0.0
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def safe_call(fn, *args):
    try:
        fn(*args)
        return True
    except Exception:
        return False


def safe_get(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


def write_bridge(message):
    global bridge_process
    if bridge_process is None or bridge_process.poll() is not None:
        return False
    try:
        bridge_process.stdin.write((json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8"))
        bridge_process.stdin.flush()
        return True
    except Exception as exc:
        print("bridge write error:", str(exc))
        return False


def start_bridge_process():
    global bridge_process
    try:
        bridge_process = subprocess.Popen(
            ["/data/python_files/bin/python", "-u", "-c", SOCKET_BRIDGE_CODE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        os.set_blocking(bridge_process.stdout.fileno(), False)
        os.set_blocking(bridge_process.stderr.fileno(), False)
        print("Socket bridge child process started:", bridge_process.pid)
        return True
    except Exception as exc:
        print("Socket bridge child process failed:", str(exc))
        bridge_process = None
        return False


def stop_bridge_process():
    global bridge_process
    if bridge_process is None:
        return
    write_bridge({"type": "shutdown"})
    try:
        bridge_process.terminate()
    except Exception:
        pass
    bridge_process = None


def receive_bridge_messages():
    global bridge_stdout_buffer, latest_command
    if bridge_process is None:
        return
    if bridge_process.poll() is not None:
        try:
            error_data = bridge_process.stderr.read()
            if error_data:
                print("bridge terminated:", error_data.decode("utf-8", "replace"))
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
    except Exception:
        return
    while "\n" in bridge_stdout_buffer:
        line, bridge_stdout_buffer = bridge_stdout_buffer.split("\n", 1)
        if not line:
            continue
        try:
            message = json.loads(line)
        except Exception:
            print("invalid bridge output:", line)
            continue
        message_type = message.get("type")
        if message_type == "command":
            latest_command["sequence"] = int(message.get("sequence", 0))
            latest_command["stop"] = bool(message.get("stop", False))
            latest_command["fire"] = bool(message.get("fire", False))
            latest_command["vx"] = clamp(message.get("vx", 0.0), -1.0, 1.0)
            latest_command["vy"] = clamp(message.get("vy", 0.0), -1.0, 1.0)
            latest_command["chassis_yaw_rate"] = clamp(message.get("chassis_yaw_rate", 0.0), -1.0, 1.0)
            latest_command["gimbal_yaw_rate"] = clamp(message.get("gimbal_yaw_rate", 0.0), -1.0, 1.0)
            latest_command["gimbal_pitch_rate"] = clamp(message.get("gimbal_pitch_rate", 0.0), -1.0, 1.0)
        elif message_type == "bridge_ready":
            print("Socket bridge ready on UDP", message.get("command_port"))
        elif message_type in ("fatal_error", "receive_error", "telemetry_error"):
            print("bridge error:", message)


def stop_robot_motion():
    safe_call(gimbal_ctrl.rotate_with_speed, 0, 0)
    safe_call(chassis_ctrl.move_with_speed, 0, 0, 0)
    safe_call(chassis_ctrl.stop)


def apply_robot_command():
    if latest_command.get("stop", False):
        stop_robot_motion()
        return
    safe_call(
        chassis_ctrl.move_with_speed,
        latest_command["vx"] * MAX_CHASSIS_SPEED,
        latest_command["vy"] * MAX_CHASSIS_SPEED,
        latest_command["chassis_yaw_rate"] * MAX_CHASSIS_YAW_SPEED,
    )
    safe_call(
        gimbal_ctrl.rotate_with_speed,
        latest_command["gimbal_pitch_rate"] * MAX_GIMBAL_SPEED,
        latest_command["gimbal_yaw_rate"] * MAX_GIMBAL_SPEED,
    )
    if latest_command.get("fire", False):
        if not safe_call(gun_ctrl.fire_once):
            safe_call(gun_ctrl.fire_continuous)
        latest_command["fire"] = False


def read_robot_telemetry():
    return {
        "x": safe_get(chassis_ctrl.get_position_based_power_on, rm_define.axis_x),
        "y": safe_get(chassis_ctrl.get_position_based_power_on, rm_define.axis_y),
        "yaw": safe_get(chassis_ctrl.get_attitude, rm_define.chassis_yaw),
        "vx": safe_get(chassis_ctrl.get_speed, rm_define.chassis_forward),
        "vy": safe_get(chassis_ctrl.get_speed, rm_define.chassis_translation),
        "yaw_rate": None,
        "gimbal_yaw": safe_get(gimbal_ctrl.get_axis_angle, rm_define.gimbal_axis_yaw),
        "gimbal_pitch": safe_get(gimbal_ctrl.get_axis_angle, rm_define.gimbal_axis_pitch),
    }


def send_telemetry():
    global telemetry_sequence
    message = {"type": "telemetry", "sequence": telemetry_sequence, "time_ms": int(time.time() * 1000)}
    message.update(read_robot_telemetry())
    write_bridge(message)
    telemetry_sequence += 1


def start():
    init_root_modules()
    enable_latest_fw_adb()
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    start_bridge_process()
    next_control_time = time.time()
    next_telemetry_time = time.time()
    try:
        while True:
            now = time.time()
            receive_bridge_messages()
            if now >= next_control_time:
                apply_robot_command()
                next_control_time += CONTROL_PERIOD_SEC
                if now - next_control_time > CONTROL_PERIOD_SEC * 5:
                    next_control_time = now + CONTROL_PERIOD_SEC
            if now >= next_telemetry_time:
                send_telemetry()
                next_telemetry_time += TELEMETRY_PERIOD_SEC
                if now - next_telemetry_time > TELEMETRY_PERIOD_SEC * 5:
                    next_telemetry_time = now + TELEMETRY_PERIOD_SEC
            time.sleep(0.002)
    finally:
        stop_robot_motion()
        stop_bridge_process()
