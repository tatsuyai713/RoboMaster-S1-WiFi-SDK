COMMAND_PORT = 40923
TELEMETRY_PORT = 40924
CONTROL_PERIOD_SEC = 0.02
COMMAND_HOLD_SEC = 0.1
COMMAND_DECAY_SEC = 0.2
COMMAND_TIMEOUT_SEC = COMMAND_HOLD_SEC + COMMAND_DECAY_SEC
COMMAND_ZERO_EPSILON = 0.02
COMMAND_ANGULAR_ZERO_EPSILON = 0.08
MAX_CHASSIS_SPEED = 1.0
MAX_CHASSIS_YAW_SPEED = 120.0
MAX_GIMBAL_SPEED = 120.0
LED_GUN_OFF_TIME = 0.0


def root_me(module):
    builtins = rm_define.__dict__["__builtins__"]
    real_import = builtins["__import__"] if isinstance(builtins, dict) else builtins.__import__
    return real_import(module, globals(), locals(), [], 0)


def mark_failure(time_module=None):
    gimbal_ctrl.rotate_with_speed(35, 0)
    if time_module is not None:
        time_module.sleep(0.05)
    else:
        gimbal_ctrl.rotate(rm_define.gimbal_right)
    gimbal_ctrl.rotate_with_speed(0, 0)


def stop_motion():
    try:
        chassis_ctrl.move_with_speed(0, 0, 0)
    except Exception:
        pass
    try:
        chassis_ctrl.stop()
    except Exception:
        pass
    try:
        gimbal_ctrl.rotate_with_speed(0, 0)
    except Exception:
        pass


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
        "left_right": "gimbal_left",
        "up_down": "gimbal_up",
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


def value_text(fn, arg):
    try:
        return str(float(fn(arg)))
    except Exception:
        return "null"


def default_motion_command():
    return {"stop": True, "x": 0.0, "y": 0.0, "z": 0.0, "gimbal_pitch": 0.0, "gimbal_yaw": 0.0}


def default_chassis_command():
    return {"x": 0.0, "y": 0.0, "z": 0.0}


def default_gimbal_command():
    return {"gimbal_pitch": 0.0, "gimbal_yaw": 0.0}


def has_motion_fields(command):
    for key in ("x", "vx", "y", "vy", "z", "chassis_yaw_rate", "gimbal_pitch", "gimbal_pitch_rate", "gimbal_yaw", "gimbal_yaw_rate"):
        if key in command:
            return True
    return False


def has_chassis_motion_fields(command):
    for key in ("x", "vx", "y", "vy", "z", "chassis_yaw_rate"):
        if key in command:
            return True
    return False


def has_gimbal_motion_fields(command):
    for key in ("gimbal_pitch", "gimbal_pitch_rate", "gimbal_yaw", "gimbal_yaw_rate"):
        if key in command:
            return True
    return False


def merge_command(current, incoming):
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
    return command.get("stop", False) or has_motion_fields(command)


def pending_event_command(command):
    event_command = command.copy()
    for key in (
        "x",
        "vx",
        "y",
        "vy",
        "z",
        "chassis_yaw_rate",
        "gimbal_pitch",
        "gimbal_pitch_rate",
        "gimbal_yaw",
        "gimbal_yaw_rate",
        "command_seq",
        "session_id",
    ):
        event_command.pop(key, None)
    if (
        event_command.get("stop", False)
        or event_command.get("fire", False)
        or event_command.get("led", False)
        or "mode" in event_command
        or ("module" in event_command and "method" in event_command)
    ):
        return event_command
    return None


def set_robot_mode(command):
    mode = str(command.get("mode", "")).lower()
    if mode in ("free", "robot_mode_free"):
        safe_call(robot_ctrl.set_mode, rm_define.robot_mode_free)
    elif mode in ("gimbal_follow", "follow", "robot_mode_gimbal_follow"):
        safe_call(robot_ctrl.set_mode, rm_define.robot_mode_gimbal_follow)
    elif mode in ("chassis_follow", "chassis_lead", "robot_mode_chassis_follow"):
        safe_call(robot_ctrl.set_mode, rm_define.robot_mode_chassis_follow)


def decay_value(value, scale, epsilon=COMMAND_ZERO_EPSILON):
    value = clamp(value, -1.0, 1.0) * clamp(scale, 0.0, 1.0)
    if -epsilon < value < epsilon:
        return 0.0
    return value


def decay_scale(elapsed):
    if elapsed <= COMMAND_HOLD_SEC:
        return 1.0
    if elapsed >= COMMAND_TIMEOUT_SEC:
        return 0.0
    return 1.0 - ((elapsed - COMMAND_HOLD_SEC) / COMMAND_DECAY_SEC)


def decay_chassis_command(command, scale):
    command["x"] = decay_value(number(command, "x", number(command, "vx", 0.0)), scale)
    command["y"] = decay_value(number(command, "y", number(command, "vy", 0.0)), scale)
    command["z"] = decay_value(number(command, "z", number(command, "chassis_yaw_rate", 0.0)), scale, COMMAND_ANGULAR_ZERO_EPSILON)
    command["stop"] = False
    command["fire"] = False
    command["led"] = False
    return command


def decay_gimbal_command(command, scale):
    command["gimbal_pitch"] = decay_value(number(command, "gimbal_pitch", number(command, "gimbal_pitch_rate", 0.0)), scale, COMMAND_ANGULAR_ZERO_EPSILON)
    command["gimbal_yaw"] = decay_value(number(command, "gimbal_yaw", number(command, "gimbal_yaw_rate", 0.0)), scale, COMMAND_ANGULAR_ZERO_EPSILON)
    command["stop"] = False
    command["fire"] = False
    command["led"] = False
    return command


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
            return safe_call(
                chassis_ctrl.set_wheel_speed,
                int(number(params, "w1", 0)),
                int(number(params, "w2", 0)),
                int(number(params, "w3", 0)),
                int(number(params, "w4", 0)),
            )
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
        if method == "move_degree_with_speed":
            return safe_call(
                chassis_ctrl.move_degree_with_speed,
                direction_value(params.get("direction", "forward")),
                number(params, "degree", 0),
                number(params, "speed", 0),
            )
        if method == "rotate":
            return safe_call(chassis_ctrl.rotate, direction_value(params.get("direction", "clockwise")))
        if method == "rotate_with_time":
            return safe_call(chassis_ctrl.rotate_with_time, direction_value(params.get("direction", "clockwise")), number(params, "time", 0))
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
        if method == "rotate":
            return safe_call(gimbal_ctrl.rotate, direction_value(params.get("direction", "yaw_left")))
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


def apply_fire(command, time_module):
    global LED_GUN_OFF_TIME
    if not command.get("fire", False):
        return
    gun_type = str(command.get("gun_type", command.get("fire_type", "physical"))).lower()
    if gun_type in ("ir", "infrared", "led"):
        safe_call(led_ctrl.gun_led_on)
        LED_GUN_OFF_TIME = time_module.time() + 0.08
    else:
        if not safe_call(gun_ctrl.fire_once):
            safe_call(gun_ctrl.fire_continuous)
        safe_call(gun_ctrl.stop)
    command["fire"] = False


def service_fire_events(time_module):
    global LED_GUN_OFF_TIME
    if LED_GUN_OFF_TIME and time_module.time() >= LED_GUN_OFF_TIME:
        safe_call(led_ctrl.gun_led_off)
        LED_GUN_OFF_TIME = 0.0


def apply_command(command, time_module):
    event_only = (
        (command.get("led", False) or command.get("fire", False) or ("module" in command and "method" in command))
        and not command.get("stop", False)
        and not has_motion_fields(command)
        and "mode" not in command
    )
    apply_led(command)
    apply_fire(command, time_module)
    service_fire_events(time_module)
    generic_handled = False
    if "module" in command and "method" in command:
        generic_handled = apply_generic_call(command)
    if event_only or (
        generic_handled and not command.get("stop", False) and not has_motion_fields(command) and "mode" not in command
    ):
        return
    set_robot_mode(command)
    if "mode" in command and len(command) == 1:
        stop_motion()
        return
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


def build_telemetry_text(sequence, time_ms, session_id, values):
    return (
        '{"type":"telemetry"'
        + ',"sequence":' + str(sequence)
        + ',"time_ms":' + str(time_ms)
        + ',"session_id":' + str(session_id)
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
    chassis_ctrl.set_rotate_speed(50)
    gimbal_ctrl.set_rotate_speed(90)

    try:
        sub_process = root_me("sub" + "process")
        time_module = root_me("time")
        socket_module = root_me("socket")
        json_module = root_me("json")
        threading_module = root_me("threading")
    except Exception as exc:
        print("import failed:", str(exc))
        mark_failure()
        return

    try:
        shell_path = "/" + "system" + "/" + "bin" + "/" + "sh"
        adb_path = "/" + "system" + "/" + "bin" + "/" + "adb" + "_en.sh"
        adb_proc = sub_process.Popen(
            adb_path,
            shell=True,
            executable=shell_path,
            stdout=sub_process.PIPE,
            stderr=sub_process.PIPE,
        )
        print("adb helper pid:", adb_proc.pid)
        time_module.sleep(0.5)
    except Exception as exc:
        print("adb helper failed:", str(exc))
        mark_failure(time_module)
        return

    try:
        rx = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_DGRAM)
        rx.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_REUSEADDR, 1)
        try:
            rx.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_RCVBUF, 262144)
        except Exception:
            pass
        rx.bind(("0.0.0.0", COMMAND_PORT))
        rx.setblocking(True)
        tx = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_DGRAM)
        tx.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_REUSEADDR, 1)
        tx.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_BROADCAST, 1)
        state = {
            "chassis_command": default_chassis_command(),
            "gimbal_command": default_gimbal_command(),
            "target": ("255.255.255.255", TELEMETRY_PORT),
            "last_chassis_motion_time": time_module.time(),
            "last_gimbal_motion_time": time_module.time(),
            "sequence": 0,
            "session_id": 0,
            "last_chassis_command_seq": 0,
            "last_gimbal_command_seq": 0,
            "pending_commands": [],
            "telemetry_values": read_telemetry_values(),
        }
        state_lock = threading_module.Lock()
        command_event = threading_module.Event()

        def command_sequence(command):
            try:
                return int(command.get("command_seq", 0) or 0)
            except Exception:
                return 0

        def process_received_packets(packets):
            decoded_packets = []
            for data, source in packets:
                try:
                    incoming = json_module.loads(data.decode("utf-8"))
                except Exception:
                    continue
                decoded_packets.append((incoming, source))
            if not decoded_packets:
                return

            latest_chassis = None
            latest_gimbal = None
            latest_chassis_seq = -1
            latest_gimbal_seq = -1
            pending_commands = []

            for incoming, source in decoded_packets:
                pending_command = pending_event_command(incoming)
                if pending_command is not None:
                    pending_commands.append(pending_command)
                command_seq = command_sequence(incoming)
                if incoming.get("stop", False) or has_chassis_motion_fields(incoming):
                    if command_seq == 0 or command_seq >= latest_chassis_seq:
                        latest_chassis = incoming
                        latest_chassis_seq = command_seq
                if incoming.get("stop", False) or has_gimbal_motion_fields(incoming):
                    if command_seq == 0 or command_seq >= latest_gimbal_seq:
                        latest_gimbal = incoming
                        latest_gimbal_seq = command_seq

            now = time_module.time()
            last_incoming, last_source = decoded_packets[-1]
            with state_lock:
                state["target"] = (last_source[0], TELEMETRY_PORT)
                if "session_id" in last_incoming:
                    state["session_id"] = last_incoming.get("session_id", 0)
                state["pending_commands"].extend(pending_commands)

                if latest_chassis is not None and (
                    latest_chassis_seq == 0
                    or latest_chassis_seq >= state["last_chassis_command_seq"]
                ):
                    state["last_chassis_command_seq"] = latest_chassis_seq
                    if latest_chassis.get("stop", False):
                        state["chassis_command"] = default_chassis_command()
                    else:
                        state["chassis_command"] = merge_command(
                            state["chassis_command"],
                            latest_chassis,
                        )
                    state["last_chassis_motion_time"] = now

                if latest_gimbal is not None and (
                    latest_gimbal_seq == 0
                    or latest_gimbal_seq >= state["last_gimbal_command_seq"]
                ):
                    state["last_gimbal_command_seq"] = latest_gimbal_seq
                    if latest_gimbal.get("stop", False):
                        state["gimbal_command"] = default_gimbal_command()
                    else:
                        state["gimbal_command"] = merge_command(
                            state["gimbal_command"],
                            latest_gimbal,
                        )
                    state["last_gimbal_motion_time"] = now
                command_event.set()

        def receive_loop():
            while True:
                try:
                    data, source = rx.recvfrom(2048)
                    packets = [(data, source)]
                    rx.setblocking(False)
                    while True:
                        try:
                            data, source = rx.recvfrom(2048)
                        except Exception:
                            break
                        packets.append((data, source))
                    rx.setblocking(True)
                    process_received_packets(packets)
                except Exception:
                    try:
                        rx.setblocking(True)
                    except Exception:
                        pass
                    time_module.sleep(CONTROL_PERIOD_SEC)

        def telemetry_loop():
            next_telemetry_time = time_module.time()
            while True:
                with state_lock:
                    target = state["target"]
                    sequence = state["sequence"]
                    session_id = state["session_id"]
                    telemetry_values = state["telemetry_values"].copy()
                    state["sequence"] = sequence + 1
                try:
                    telemetry_text = build_telemetry_text(sequence, int(time_module.time() * 1000), session_id, telemetry_values)
                    tx.sendto(telemetry_text.encode("utf-8"), target)
                except Exception:
                    pass
                next_telemetry_time += CONTROL_PERIOD_SEC
                wait_time = next_telemetry_time - time_module.time()
                if wait_time > 0:
                    time_module.sleep(wait_time)
                else:
                    next_telemetry_time = time_module.time()

        def telemetry_sample_loop():
            while True:
                values = read_telemetry_values()
                with state_lock:
                    state["telemetry_values"] = values
                time_module.sleep(CONTROL_PERIOD_SEC)

        threading_module.Thread(target=receive_loop).start()
        threading_module.Thread(target=telemetry_loop).start()
        threading_module.Thread(target=telemetry_sample_loop).start()

        next_motion_time = time_module.time()
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
                apply_command(pending_command, time_module)

            now = time_module.time()
            if now >= next_motion_time:
                chassis_elapsed = now - last_chassis_motion_time
                if chassis_elapsed <= COMMAND_HOLD_SEC:
                    if not chassis_command_is_zero(chassis_command):
                        apply_command(chassis_command, time_module)
                elif chassis_elapsed <= COMMAND_TIMEOUT_SEC:
                    if chassis_command_is_zero(chassis_command):
                        chassis_command = default_chassis_command()
                    else:
                        apply_command(decay_chassis_command(chassis_command.copy(), decay_scale(chassis_elapsed)), time_module)
                elif not chassis_command_is_zero(chassis_command):
                    chassis_command = default_chassis_command()
                    apply_command(chassis_command, time_module)
                    with state_lock:
                        state["chassis_command"] = chassis_command.copy()

                gimbal_elapsed = now - last_gimbal_motion_time
                if gimbal_elapsed <= COMMAND_HOLD_SEC:
                    if not gimbal_command_is_zero(gimbal_command):
                        apply_command(gimbal_command, time_module)
                elif gimbal_elapsed <= COMMAND_TIMEOUT_SEC:
                    if gimbal_command_is_zero(gimbal_command):
                        gimbal_command = default_gimbal_command()
                    else:
                        apply_command(decay_gimbal_command(gimbal_command.copy(), decay_scale(gimbal_elapsed)), time_module)
                elif not gimbal_command_is_zero(gimbal_command):
                    gimbal_command = default_gimbal_command()
                    apply_command(gimbal_command, time_module)
                    with state_lock:
                        state["gimbal_command"] = gimbal_command.copy()
                next_motion_time += CONTROL_PERIOD_SEC
                if next_motion_time < now:
                    next_motion_time = now + CONTROL_PERIOD_SEC
            else:
                wait_time = next_motion_time - now
                if wait_time > 0:
                    command_event.wait(wait_time)
    except Exception as exc:
        print("child udp bridge failed:", str(exc))
        mark_failure(time_module)
        return
