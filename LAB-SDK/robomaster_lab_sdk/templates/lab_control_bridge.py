COMMAND_PORT = __COMMAND_PORT__
TELEMETRY_PORT = __TELEMETRY_PORT__
CONTROL_PERIOD_SEC = __CONTROL_PERIOD_SEC__
TELEMETRY_PERIOD_SEC = __TELEMETRY_PERIOD_SEC__
COMMAND_TIMEOUT_SEC = __COMMAND_TIMEOUT_SEC__
COMMAND_DECAY_PER_TICK = __COMMAND_DECAY_PER_TICK__
COMMAND_ZERO_EPSILON = __COMMAND_ZERO_EPSILON__
COMMAND_ANGULAR_ZERO_EPSILON = __COMMAND_ANGULAR_ZERO_EPSILON__
MAX_CHASSIS_SPEED = __MAX_CHASSIS_SPEED__
MAX_CHASSIS_YAW_SPEED = __MAX_CHASSIS_YAW_SPEED__
MAX_GIMBAL_SPEED = __MAX_GIMBAL_SPEED__


_time = None
_socket = None
_json = None
_threading = None
_led_gun_off_time = 0.0


def _import_lab_runtime_module(module):
    builtins = rm_define.__dict__["__builtins__"]
    real_import = builtins["__import__"] if isinstance(builtins, dict) else builtins.__import__
    return real_import(module, globals(), locals(), [], 0)


def _initialize_lab_runtime():
    global _time, _socket, _json, _threading
    _time = _import_lab_runtime_module("time")
    _socket = _import_lab_runtime_module("socket")
    _json = _import_lab_runtime_module("json")
    _threading = _import_lab_runtime_module("threading")
    subprocess = _import_lab_runtime_module("subprocess")
    try:
        subprocess.Popen("/system/bin/adb_en.sh", shell=True, executable="/system/bin/sh")
        _time.sleep(0.5)
    except Exception:
        pass


def safe_call(fn, *args):
    try:
        fn(*args)
        return True
    except Exception:
        return False


def controller_call(controller_name, method_name, *args):
    try:
        controller = globals().get(controller_name)
        if controller is None:
            return False
        return safe_call(getattr(controller, method_name), *args)
    except Exception:
        return False


def safe_get(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


def rm_value(name, default=None):
    try:
        return getattr(rm_define, str(name))
    except Exception:
        return default


def direction_value(name):
    values = {
        "forward": "chassis_forward",
        "backward": "chassis_backward",
        "left": "chassis_left",
        "right": "chassis_right",
        "clockwise": "chassis_clockwise",
        "anticlockwise": "chassis_anticlockwise",
        "counter_clockwise": "chassis_anticlockwise",
        "yaw_left": "gimbal_left",
        "yaw_right": "gimbal_right",
        "pitch_up": "gimbal_up",
        "pitch_down": "gimbal_down",
    }
    key = str(name).lower()
    return rm_value(values.get(key, key), name)


def led_comp_value(comp):
    values = {
        "all": "armor_all",
        "bottom": "armor_bottom_all",
        "bottom_all": "armor_bottom_all",
        "top": "armor_top_all",
        "top_all": "armor_top_all",
        "gimbal": "armor_top_all",
        "front": "armor_front",
        "back": "armor_back",
        "left": "armor_left",
        "right": "armor_right",
    }
    key = str(comp).lower()
    return rm_value(values.get(key, key), rm_define.armor_all)


def led_effect_value(effect):
    values = {
        "on": "effect_always_on",
        "always_on": "effect_always_on",
        "off": "effect_always_off",
        "always_off": "effect_always_off",
        "flash": "effect_flash",
        "breath": "effect_breath",
        "breathing": "effect_breath",
        "marquee": "effect_marquee",
    }
    key = str(effect).lower()
    return rm_value(values.get(key, key), rm_define.effect_always_on)


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


def number(command, name, default=0.0):
    try:
        return float(command.get(name, default))
    except Exception:
        return default


def default_motion_command():
    return {"stop": True, "x": 0.0, "y": 0.0, "z": 0.0, "gimbal_pitch": 0.0, "gimbal_yaw": 0.0}


def default_chassis_command():
    return {"x": 0.0, "y": 0.0, "z": 0.0}


def default_gimbal_command():
    return {"gimbal_pitch": 0.0, "gimbal_yaw": 0.0}


def has_motion_fields(command):
    return (
        "x" in command
        or "vx" in command
        or "y" in command
        or "vy" in command
        or "z" in command
        or "chassis_yaw_rate" in command
        or "gimbal_pitch" in command
        or "gimbal_pitch_rate" in command
        or "gimbal_yaw" in command
        or "gimbal_yaw_rate" in command
    )


def has_chassis_motion_fields(command):
    return (
        "x" in command
        or "vx" in command
        or "y" in command
        or "vy" in command
        or "z" in command
        or "chassis_yaw_rate" in command
    )


def has_gimbal_motion_fields(command):
    return (
        "gimbal_pitch" in command
        or "gimbal_pitch_rate" in command
        or "gimbal_yaw" in command
        or "gimbal_yaw_rate" in command
    )


def scaled(value, maximum):
    if maximum == 0:
        return 0.0
    return clamp(value, -maximum, maximum) / maximum


def official_command(command):
    module = str(command.get("module", command.get("component", ""))).lower()
    method = str(command.get("method", command.get("api", command.get("command", "")))).lower()
    if module == "chassis":
        if method in ("drive_speed", "move_with_speed"):
            return {
                "x": scaled(number(command, "x", 0.0), MAX_CHASSIS_SPEED),
                "y": scaled(number(command, "y", 0.0), MAX_CHASSIS_SPEED),
                "z": scaled(number(command, "z", number(command, "yaw_speed", 0.0)), MAX_CHASSIS_YAW_SPEED),
            }
        if method in ("stop", "stop_motion"):
            return default_motion_command()
    if module == "gimbal":
        if method in ("drive_speed", "rotate_with_speed"):
            return {
                "gimbal_pitch": scaled(number(command, "pitch_speed", number(command, "pitch", 0.0)), MAX_GIMBAL_SPEED),
                "gimbal_yaw": scaled(number(command, "yaw_speed", number(command, "yaw", 0.0)), MAX_GIMBAL_SPEED),
            }
        if method in ("stop", "recenter"):
            return {"gimbal_pitch": 0.0, "gimbal_yaw": 0.0}
    if module == "robot" and method in ("set_robot_mode", "set_mode"):
        return {"mode": command.get("mode", command.get("robot_mode", "free"))}
    if module in ("blaster", "gun") and method in ("fire", "fire_once"):
        fire_type = str(command.get("fire_type", command.get("gun_type", "physical"))).lower()
        gun_type = "led" if fire_type in ("ir", "infrared", "led") else "physical"
        return {"fire": True, "gun_type": gun_type}
    if module == "led" and method in ("set_led", "set_gimbal_led", "turn_off"):
        if method == "turn_off":
            return {"led": True, "effect": "off", "comp": command.get("comp", "all")}
        comp = command.get("comp", "gimbal" if method == "set_gimbal_led" else "all")
        return {
            "led": True,
            "comp": comp,
            "r": command.get("r", 255),
            "g": command.get("g", 255),
            "b": command.get("b", 255),
            "effect": command.get("effect", "on"),
            "freq": command.get("freq", 1),
        }
    return command


def merge_command(current, incoming):
    incoming = official_command(incoming)
    if incoming.get("stop", False):
        return default_motion_command()
    merged = current.copy()
    if "mode" in incoming:
        merged["mode"] = incoming.get("mode")
    if has_motion_fields(incoming):
        merged["stop"] = False
    if has_chassis_motion_fields(incoming):
        if "x" in incoming or "vx" in incoming:
            merged["x"] = number(incoming, "x", number(incoming, "vx", 0.0))
        if "y" in incoming or "vy" in incoming:
            merged["y"] = number(incoming, "y", number(incoming, "vy", 0.0))
        if "z" in incoming or "chassis_yaw_rate" in incoming:
            merged["z"] = number(incoming, "z", number(incoming, "chassis_yaw_rate", 0.0))
    if has_gimbal_motion_fields(incoming):
        if "gimbal_pitch" in incoming or "gimbal_pitch_rate" in incoming:
            merged["gimbal_pitch"] = number(incoming, "gimbal_pitch", number(incoming, "gimbal_pitch_rate", 0.0))
        if "gimbal_yaw" in incoming or "gimbal_yaw_rate" in incoming:
            merged["gimbal_yaw"] = number(incoming, "gimbal_yaw", number(incoming, "gimbal_yaw_rate", 0.0))
    for key in ("fire", "gun_type", "fire_type", "led", "comp", "r", "g", "b", "effect", "freq"):
        if key in incoming:
            merged[key] = incoming[key]
    return merged


def command_updates_motion_state(command):
    command = official_command(command)
    return command.get("stop", False) or has_motion_fields(command)


def stop_motion():
    safe_call(chassis_ctrl.move_with_speed, 0, 0, 0)
    safe_call(gimbal_ctrl.rotate_with_speed, 0, 0)


def set_robot_mode(mode):
    key = str(mode).lower()
    if key in ("free", "robot_mode_free"):
        safe_call(robot_ctrl.set_mode, rm_define.robot_mode_free)
    elif key in ("gimbal_follow", "follow", "robot_mode_gimbal_follow"):
        safe_call(robot_ctrl.set_mode, rm_define.robot_mode_gimbal_follow)
    elif key in ("chassis_follow", "chassis_lead", "robot_mode_chassis_follow"):
        safe_call(robot_ctrl.set_mode, rm_define.robot_mode_chassis_follow)


def decay_value(value, epsilon=COMMAND_ZERO_EPSILON):
    value = clamp(value, -1.0, 1.0) * COMMAND_DECAY_PER_TICK
    if -epsilon < value < epsilon:
        return 0.0
    return value


def decay_command(command):
    command["x"] = decay_value(number(command, "x", number(command, "vx", 0.0)))
    command["y"] = decay_value(number(command, "y", number(command, "vy", 0.0)))
    command["z"] = decay_value(number(command, "z", number(command, "chassis_yaw_rate", 0.0)), COMMAND_ANGULAR_ZERO_EPSILON)
    command["gimbal_pitch"] = decay_value(number(command, "gimbal_pitch", number(command, "gimbal_pitch_rate", 0.0)), COMMAND_ANGULAR_ZERO_EPSILON)
    command["gimbal_yaw"] = decay_value(number(command, "gimbal_yaw", number(command, "gimbal_yaw_rate", 0.0)), COMMAND_ANGULAR_ZERO_EPSILON)
    command["fire"] = False
    command["stop"] = False
    return command


def decay_chassis_command(command):
    command["x"] = decay_value(number(command, "x", number(command, "vx", 0.0)))
    command["y"] = decay_value(number(command, "y", number(command, "vy", 0.0)))
    command["z"] = decay_value(number(command, "z", number(command, "chassis_yaw_rate", 0.0)), COMMAND_ANGULAR_ZERO_EPSILON)
    command["fire"] = False
    command["stop"] = False
    return command


def decay_gimbal_command(command):
    command["gimbal_pitch"] = decay_value(number(command, "gimbal_pitch", number(command, "gimbal_pitch_rate", 0.0)), COMMAND_ANGULAR_ZERO_EPSILON)
    command["gimbal_yaw"] = decay_value(number(command, "gimbal_yaw", number(command, "gimbal_yaw_rate", 0.0)), COMMAND_ANGULAR_ZERO_EPSILON)
    command["fire"] = False
    command["stop"] = False
    return command


def command_is_zero(command):
    return (
        number(command, "x", number(command, "vx", 0.0)) == 0.0
        and number(command, "y", number(command, "vy", 0.0)) == 0.0
        and number(command, "z", number(command, "chassis_yaw_rate", 0.0)) == 0.0
        and number(command, "gimbal_pitch", number(command, "gimbal_pitch_rate", 0.0)) == 0.0
        and number(command, "gimbal_yaw", number(command, "gimbal_yaw_rate", 0.0)) == 0.0
    )


def chassis_command_is_zero(command):
    return (
        number(command, "x", number(command, "vx", 0.0)) == 0.0
        and number(command, "y", number(command, "vy", 0.0)) == 0.0
        and number(command, "z", number(command, "chassis_yaw_rate", 0.0)) == 0.0
    )


def gimbal_command_is_zero(command):
    return (
        number(command, "gimbal_pitch", number(command, "gimbal_pitch_rate", 0.0)) == 0.0
        and number(command, "gimbal_yaw", number(command, "gimbal_yaw_rate", 0.0)) == 0.0
    )


def apply_led(command):
    if not command.get("led", False):
        return
    r = int(clamp(command.get("r", 255), 0, 255))
    g = int(clamp(command.get("g", 255), 0, 255))
    b = int(clamp(command.get("b", 255), 0, 255))
    effect = str(command.get("effect", "on")).lower()
    target = str(command.get("comp", "all")).lower()
    if effect == "off":
        safe_call(led_ctrl.turn_off, led_comp_value(target))
    else:
        if target in ("all", "bottom", "bottom_all"):
            safe_call(led_ctrl.set_bottom_led, rm_define.armor_bottom_all, r, g, b, led_effect_value(effect))
        if target in ("all", "top", "top_all", "gimbal"):
            safe_call(led_ctrl.set_top_led, rm_define.armor_top_all, r, g, b, led_effect_value(effect))
    command["led"] = False


def generic_params(command):
    params = command.get("params", {})
    if not isinstance(params, dict):
        params = {}
    merged = {}
    for key, value in command.items():
        if key not in ("module", "method", "params", "command_seq", "session_id"):
            merged[key] = value
    merged.update(params)
    return merged


def apply_generic_call(command):
    module = str(command.get("module", "")).lower()
    method = str(command.get("method", "")).lower()
    params = generic_params(command)

    if module == "chassis":
        if method == "set_wheel_speed":
            return safe_call(chassis_ctrl.set_wheel_speed, int(number(params, "w1", 0)), int(number(params, "w2", 0)), int(number(params, "w3", 0)), int(number(params, "w4", 0)))
        if method == "set_trans_speed":
            return safe_call(chassis_ctrl.set_trans_speed, number(params, "speed", 0))
        if method == "set_rotate_speed":
            return safe_call(chassis_ctrl.set_rotate_speed, number(params, "speed", 0))
        if method == "set_follow_gimbal_offset":
            return safe_call(chassis_ctrl.set_follow_gimbal_offset, number(params, "offset", 0))
        if method == "move_with_time":
            return safe_call(chassis_ctrl.move_with_time, direction_value(params.get("direction", "forward")), number(params, "time", 0))
        if method == "move_with_distance":
            return safe_call(chassis_ctrl.move_with_distance, direction_value(params.get("direction", "forward")), number(params, "distance", 0))
        if method == "rotate_with_degree":
            return safe_call(chassis_ctrl.rotate_with_degree, direction_value(params.get("direction", "clockwise")), number(params, "degree", 0))
        if method == "rotate_with_speed":
            return safe_call(chassis_ctrl.rotate_with_speed, direction_value(params.get("direction", "clockwise")), number(params, "speed", 0))
        if method == "stop":
            return safe_call(chassis_ctrl.stop)

    if module == "gimbal":
        if method == "set_rotate_speed":
            return safe_call(gimbal_ctrl.set_rotate_speed, number(params, "speed", 0))
        if method == "set_follow_chassis_offset":
            return safe_call(gimbal_ctrl.set_follow_chassis_offset, number(params, "offset", 0))
        if method == "recenter":
            return safe_call(gimbal_ctrl.recenter)
        if method == "stop":
            return safe_call(gimbal_ctrl.stop)
        if method == "suspend":
            return safe_call(gimbal_ctrl.suspend)
        if method == "resume":
            return safe_call(gimbal_ctrl.resume)
        if method == "rotate_with_degree":
            return safe_call(gimbal_ctrl.rotate_with_degree, direction_value(params.get("direction", "yaw_left")), number(params, "degree", 0))
        if method == "yaw_ctrl":
            return safe_call(gimbal_ctrl.yaw_ctrl, number(params, "yaw", 0))
        if method == "pitch_ctrl":
            return safe_call(gimbal_ctrl.pitch_ctrl, number(params, "pitch", 0))
        if method == "angle_ctrl":
            return safe_call(gimbal_ctrl.angle_ctrl, number(params, "yaw", 0), number(params, "pitch", 0))

    if module == "led":
        comp = led_comp_value(params.get("comp", "all"))
        effect = led_effect_value(params.get("effect", "on"))
        if method == "turn_off":
            return safe_call(led_ctrl.turn_off, comp)
        if method == "set_flash":
            return safe_call(led_ctrl.set_flash, comp, int(number(params, "freq", 1)))
        if method == "set_single_led":
            return safe_call(led_ctrl.set_single_led, comp, params.get("led_list", []), effect)

    if module == "armor" and method == "set_hit_sensitivity":
        return controller_call("armor_ctrl", "set_hit_sensitivity", int(number(params, "sensitivity", 5)))

    if module == "sensor":
        if method == "enable_measure":
            return controller_call("ir_distance_sensor_ctrl", "enable_measure")
        if method == "disable_measure":
            return controller_call("ir_distance_sensor_ctrl", "disable_measure")

    if module == "vision":
        if method == "enable_detection":
            return controller_call("vision_ctrl", "enable_detection", params.get("name", params.get("type", "marker")))
        if method == "disable_detection":
            return controller_call("vision_ctrl", "disable_detection", params.get("name", params.get("type", "marker")))
        if method == "set_marker_detection_distance":
            return controller_call("vision_ctrl", "set_marker_detection_distance", number(params, "distance", 0))
        if method == "marker_detection_color_set":
            return controller_call("vision_ctrl", "marker_detection_color_set", params.get("color", "blue"))
        if method == "line_follow_color_set":
            return controller_call("vision_ctrl", "line_follow_color_set", params.get("color", "blue"))
        if method == "detect_marker_and_aim":
            return controller_call("vision_ctrl", "detect_marker_and_aim", params.get("color", "blue"))

    if module == "media":
        if method == "play_sound":
            return controller_call("media_ctrl", "play_sound", params.get("sound_id", params.get("sound", 0)))
        if method == "capture":
            return controller_call("media_ctrl", "capture")
        if method == "zoom_value_update":
            return controller_call("media_ctrl", "zoom_value_update", number(params, "value", 1))
        if method == "record":
            return controller_call("media_ctrl", "record", params.get("enable", True))
        if method == "enable_sound_recognition":
            return controller_call("media_ctrl", "enable_sound_recognition")
        if method == "disable_sound_recognition":
            return controller_call("media_ctrl", "disable_sound_recognition")
        if method == "exposure_value_update":
            return controller_call("media_ctrl", "exposure_value_update", number(params, "value", 0))

    return False


def apply_fire(command):
    global _led_gun_off_time
    if not command.get("fire", False):
        return
    gun_type = str(command.get("gun_type", command.get("fire_type", "physical"))).lower()
    if gun_type in ("ir", "infrared", "led"):
        safe_call(led_ctrl.gun_led_on)
        _led_gun_off_time = _time.time() + 0.08
    else:
        if not safe_call(gun_ctrl.fire_once):
            safe_call(gun_ctrl.fire_continuous)
        safe_call(gun_ctrl.stop)
    command["fire"] = False


def service_fire_events():
    global _led_gun_off_time
    if _led_gun_off_time and _time.time() >= _led_gun_off_time:
        safe_call(led_ctrl.gun_led_off)
        _led_gun_off_time = 0.0


def apply_command(command):
    event_only = (
        (command.get("led", False) or command.get("fire", False) or ("module" in command and "method" in command))
        and not command.get("stop", False)
        and not has_motion_fields(command)
        and "mode" not in command
    )
    apply_led(command)
    apply_fire(command)
    service_fire_events()
    if "module" in command and "method" in command:
        generic_handled = apply_generic_call(command)
        if event_only or (
            generic_handled and not command.get("stop", False) and not has_motion_fields(command) and "mode" not in command
        ):
            return
    if "mode" in command:
        set_robot_mode(command.get("mode"))
    if command.get("stop", False):
        stop_motion()
        return
    if has_chassis_motion_fields(command):
        vx = clamp(number(command, "x", number(command, "vx", 0.0)), -1.0, 1.0)
        vy = clamp(number(command, "y", number(command, "vy", 0.0)), -1.0, 1.0)
        yaw = clamp(number(command, "z", number(command, "chassis_yaw_rate", 0.0)), -1.0, 1.0)
        safe_call(chassis_ctrl.move_with_speed, vx * MAX_CHASSIS_SPEED, vy * MAX_CHASSIS_SPEED, yaw * MAX_CHASSIS_YAW_SPEED)
    if has_gimbal_motion_fields(command):
        gp = clamp(number(command, "gimbal_pitch", number(command, "gimbal_pitch_rate", 0.0)), -1.0, 1.0)
        gy = clamp(number(command, "gimbal_yaw", number(command, "gimbal_yaw_rate", 0.0)), -1.0, 1.0)
        safe_call(gimbal_ctrl.rotate_with_speed, gy * MAX_GIMBAL_SPEED, gp * MAX_GIMBAL_SPEED)


def value_text(fn, arg):
    value = safe_get(fn, arg)
    return "null" if value is None else str(float(value))


def read_telemetry_values():
    return {
        "x": value_text(chassis_ctrl.get_position_based_power_on, rm_define.chassis_forward),
        "y": value_text(chassis_ctrl.get_position_based_power_on, rm_define.chassis_translation),
        "yaw": value_text(chassis_ctrl.get_attitude, rm_define.chassis_yaw),
        "vx": value_text(chassis_ctrl.get_speed, rm_define.chassis_forward),
        "vy": value_text(chassis_ctrl.get_speed, rm_define.chassis_translation),
        "gimbal_yaw": value_text(gimbal_ctrl.get_axis_angle, rm_define.gimbal_axis_yaw),
        "gimbal_pitch": value_text(gimbal_ctrl.get_axis_angle, rm_define.gimbal_axis_pitch),
    }


def telemetry_text(sequence, time_ms, values):
    return (
        '{"type":"telemetry"'
        + ',"sequence":' + str(sequence)
        + ',"time_ms":' + str(time_ms)
        + ',"x":' + str(values.get("x", "null"))
        + ',"y":' + str(values.get("y", "null"))
        + ',"yaw":' + str(values.get("yaw", "null"))
        + ',"vx":' + str(values.get("vx", "null"))
        + ',"vy":' + str(values.get("vy", "null"))
        + ',"gimbal_yaw":' + str(values.get("gimbal_yaw", "null"))
        + ',"gimbal_pitch":' + str(values.get("gimbal_pitch", "null"))
        + '}'
    )


def start():
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    chassis_ctrl.set_rotate_speed(120)
    gimbal_ctrl.set_rotate_speed(120)
    _initialize_lab_runtime()
    rx = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    rx.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    rx.bind(("0.0.0.0", COMMAND_PORT))
    rx.setblocking(False)
    tx = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
    tx.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    tx.setsockopt(_socket.SOL_SOCKET, _socket.SO_BROADCAST, 1)
    state = {
        "chassis_command": default_chassis_command(),
        "gimbal_command": default_gimbal_command(),
        "target": ("255.255.255.255", TELEMETRY_PORT),
        "last_chassis_motion_time": _time.time(),
        "last_gimbal_motion_time": _time.time(),
        "sequence": 0,
        "pending_commands": [],
        "telemetry_values": {},
    }
    state_lock = _threading.Lock()
    command_event = _threading.Event()

    def receive_loop():
        while True:
            received_count = 0
            while True:
                try:
                    data, source = rx.recvfrom(2048)
                    incoming = _json.loads(data.decode("utf-8"))
                except Exception:
                    break
                with state_lock:
                    state["target"] = (source[0], TELEMETRY_PORT)
                    state["pending_commands"].append(incoming)
                    command_event.set()
                    if command_updates_motion_state(incoming):
                        now = _time.time()
                        normalized = official_command(incoming)
                        if normalized.get("stop", False):
                            state["chassis_command"] = default_chassis_command()
                            state["gimbal_command"] = default_gimbal_command()
                            state["last_chassis_motion_time"] = now
                            state["last_gimbal_motion_time"] = now
                        else:
                            if has_chassis_motion_fields(normalized):
                                state["chassis_command"] = merge_command(state["chassis_command"], normalized)
                                state["last_chassis_motion_time"] = now
                            if has_gimbal_motion_fields(normalized):
                                state["gimbal_command"] = merge_command(state["gimbal_command"], normalized)
                                state["last_gimbal_motion_time"] = now
                received_count += 1
                if received_count >= 64:
                    break
            _time.sleep(0.001)

    def telemetry_loop():
        next_telemetry_time = _time.time()
        while True:
            now = _time.time()
            if now >= next_telemetry_time:
                with state_lock:
                    target = state["target"]
                    sequence = state["sequence"]
                    command_values = state["chassis_command"].copy()
                    gimbal_values = state["gimbal_command"].copy()
                    state["sequence"] = sequence + 1
                command_values.update(gimbal_values)
                telemetry_values = {
                    "x": number(command_values, "x", number(command_values, "vx", 0.0)),
                    "y": number(command_values, "y", number(command_values, "vy", 0.0)),
                    "yaw": number(command_values, "z", number(command_values, "chassis_yaw_rate", 0.0)),
                    "vx": number(command_values, "x", number(command_values, "vx", 0.0)),
                    "vy": number(command_values, "y", number(command_values, "vy", 0.0)),
                    "gimbal_yaw": number(command_values, "gimbal_yaw", number(command_values, "gimbal_yaw_rate", 0.0)),
                    "gimbal_pitch": number(command_values, "gimbal_pitch", number(command_values, "gimbal_pitch_rate", 0.0)),
                }
                tx.sendto(telemetry_text(sequence, int(now * 1000), telemetry_values).encode("utf-8"), target)
                next_telemetry_time += TELEMETRY_PERIOD_SEC
                if next_telemetry_time < now:
                    next_telemetry_time = now + TELEMETRY_PERIOD_SEC
            wait_time = next_telemetry_time - _time.time()
            if wait_time > 0:
                _time.sleep(wait_time)

    def command_loop():
        next_chassis_motion_time = _time.time()
        next_gimbal_motion_time = _time.time()
        while True:
            with state_lock:
                chassis_command = state["chassis_command"].copy()
                gimbal_command = state["gimbal_command"].copy()
                last_chassis_motion_time = state["last_chassis_motion_time"]
                last_gimbal_motion_time = state["last_gimbal_motion_time"]
                pending_commands = state["pending_commands"]
                state["pending_commands"] = []
                command_event.clear()
            for pending_command in pending_commands:
                apply_command(pending_command)
            now = _time.time()
            service_fire_events()
            next_wake_times = []
            if now >= next_chassis_motion_time:
                if now - last_chassis_motion_time <= COMMAND_TIMEOUT_SEC:
                    if not chassis_command_is_zero(chassis_command):
                        apply_command(chassis_command)
                else:
                    if chassis_command_is_zero(chassis_command):
                        chassis_command = default_chassis_command()
                    else:
                        chassis_command = decay_chassis_command(chassis_command)
                        apply_command(chassis_command)
                        with state_lock:
                            state["chassis_command"] = chassis_command.copy()
                next_chassis_motion_time += CONTROL_PERIOD_SEC
                if next_chassis_motion_time < now:
                    next_chassis_motion_time = now + CONTROL_PERIOD_SEC
            next_wake_times.append(next_chassis_motion_time)

            if now >= next_gimbal_motion_time:
                if now - last_gimbal_motion_time <= COMMAND_TIMEOUT_SEC:
                    if not gimbal_command_is_zero(gimbal_command):
                        apply_command(gimbal_command)
                else:
                    if gimbal_command_is_zero(gimbal_command):
                        gimbal_command = default_gimbal_command()
                    else:
                        gimbal_command = decay_gimbal_command(gimbal_command)
                        apply_command(gimbal_command)
                        with state_lock:
                            state["gimbal_command"] = gimbal_command.copy()
                next_gimbal_motion_time += CONTROL_PERIOD_SEC
                if next_gimbal_motion_time < now:
                    next_gimbal_motion_time = now + CONTROL_PERIOD_SEC
            next_wake_times.append(next_gimbal_motion_time)

            wait_time = min(next_wake_times) - _time.time()
            if wait_time > 0:
                command_event.wait(wait_time)

    _threading.Thread(target=receive_loop).start()
    _threading.Thread(target=telemetry_loop).start()
    command_loop()
