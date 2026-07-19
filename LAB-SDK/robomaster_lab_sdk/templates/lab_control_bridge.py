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
MAX_PENDING_EVENTS = 32
MAX_PRIORITY_EVENTS = 8


_time = None
_json = None
_subprocess = None
_select = None
_os = None
_fcntl = None
_clock = None
_led_gun_off_time = 0.0


def _import_lab_runtime_module(module):
    builtins = rm_define.__dict__["__builtins__"]
    real_import = builtins["__import__"] if isinstance(builtins, dict) else builtins.__import__
    return real_import(module, globals(), locals(), [], 0)


def _initialize_lab_runtime():
    global _time, _json, _subprocess, _select, _os, _fcntl, _clock
    _time = _import_lab_runtime_module("time")
    _json = _import_lab_runtime_module("json")
    _subprocess = _import_lab_runtime_module("subprocess")
    _select = _import_lab_runtime_module("select")
    _os = _import_lab_runtime_module("os")
    _fcntl = _import_lab_runtime_module("fcntl")
    _clock = getattr(_time, "monotonic", _time.time)
    try:
        _subprocess.Popen("/system/bin/adb_en.sh", shell=True, executable="/system/bin/sh")
        _time.sleep(0.5)
    except Exception:
        pass


def set_nonblocking(fd):
    try:
        flags = _fcntl.fcntl(fd, _fcntl.F_GETFL)
        _fcntl.fcntl(fd, _fcntl.F_SETFL, flags | _os.O_NONBLOCK)
        return True
    except Exception:
        return False


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
        "top_left": "armor_top_left",
        "top_right": "armor_top_right",
        "bottom_left": "armor_bottom_left",
        "bottom_right": "armor_bottom_right",
        "bottom_front": "armor_bottom_front",
        "bottom_back": "armor_bottom_back",
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


def vision_detection_value(name):
    values = {
        "marker": "vision_detection_marker",
        "pose": "vision_detection_pose",
        "gesture": "vision_detection_pose",
        "people": "vision_detection_people",
        "person": "vision_detection_people",
        "car": "vision_detection_car",
        "robot": "vision_detection_car",
        "line": "vision_detection_line",
    }
    key = str(name).lower()
    return rm_value(values.get(key, key), None)


def vision_color_value(kind, color):
    key = str(color).lower()
    prefix = "marker_detection_color_" if str(kind).lower() == "marker" else "line_follow_color_"
    return rm_value(prefix + key, None)


def marker_value(marker):
    values = {
        "heart": "marker_trans_red_heart",
        "red_heart": "marker_trans_red_heart",
        "target": "marker_trans_target",
        "dice": "marker_trans_dice",
    }
    key = str(marker).lower()
    if len(key) == 1 and key.isdigit():
        values[key] = "marker_number_" + (
            "zero", "one", "two", "three", "four",
            "five", "six", "seven", "eight", "nine",
        )[int(key)]
    elif len(key) == 1 and "a" <= key <= "z":
        values[key] = "marker_letter_" + key.upper()
    return rm_value(values.get(key, key), None)


def sound_detection_value(name):
    key = str(name).lower()
    if key == "applause":
        return rm_value("sound_detection_applause", None)
    return rm_value(key, None)


def exposure_value(name):
    values = {
        "large": "exposure_value_large",
        "medium": "exposure_value_medium",
        "small": "exposure_value_small",
    }
    key = str(name).lower()
    return rm_value(values.get(key, key), None)


def sound_value(sound):
    if isinstance(sound, str):
        return rm_value(sound, None)
    return sound


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
    params = command.get("params", {})
    if not isinstance(params, dict):
        params = {}

    def command_value(name, default=None):
        return command.get(name, params.get(name, default))

    if module == "chassis":
        if method in ("drive_speed", "move_with_speed"):
            return {
                "x": scaled(command_value("x", 0.0), MAX_CHASSIS_SPEED),
                "y": scaled(command_value("y", 0.0), MAX_CHASSIS_SPEED),
                "z": scaled(command_value("z", command_value("yaw_speed", 0.0)), MAX_CHASSIS_YAW_SPEED),
            }
    if module == "gimbal":
        if method in ("drive_speed", "rotate_with_speed"):
            return {
                "gimbal_pitch": scaled(command_value("pitch_speed", command_value("pitch", 0.0)), MAX_GIMBAL_SPEED),
                "gimbal_yaw": scaled(command_value("yaw_speed", command_value("yaw", 0.0)), MAX_GIMBAL_SPEED),
            }
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
    command["x"] = decay_value(command.get("x", 0.0))
    command["y"] = decay_value(command.get("y", 0.0))
    command["z"] = decay_value(
        command.get("z", 0.0),
        COMMAND_ANGULAR_ZERO_EPSILON,
    )
    return command


def decay_gimbal_command(command):
    command["gimbal_pitch"] = decay_value(
        command.get("gimbal_pitch", 0.0),
        COMMAND_ANGULAR_ZERO_EPSILON,
    )
    command["gimbal_yaw"] = decay_value(
        command.get("gimbal_yaw", 0.0),
        COMMAND_ANGULAR_ZERO_EPSILON,
    )
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
        command.get("x", 0.0) == 0.0
        and command.get("y", 0.0) == 0.0
        and command.get("z", 0.0) == 0.0
    )


def gimbal_command_is_zero(command):
    return (
        command.get("gimbal_pitch", 0.0) == 0.0
        and command.get("gimbal_yaw", 0.0) == 0.0
    )


def apply_chassis_state(command):
    safe_call(
        chassis_ctrl.move_with_speed,
        command.get("x", 0.0) * MAX_CHASSIS_SPEED,
        command.get("y", 0.0) * MAX_CHASSIS_SPEED,
        command.get("z", 0.0) * MAX_CHASSIS_YAW_SPEED,
    )


def apply_gimbal_state(command):
    safe_call(
        gimbal_ctrl.rotate_with_speed,
        command.get("gimbal_yaw", 0.0) * MAX_GIMBAL_SPEED,
        command.get("gimbal_pitch", 0.0) * MAX_GIMBAL_SPEED,
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
        if target in ("all", "bottom", "bottom_all", "bottom_left", "bottom_right", "bottom_front", "bottom_back"):
            safe_call(led_ctrl.set_bottom_led, led_comp_value(target if target != "bottom" else "bottom_all"), r, g, b, led_effect_value(effect))
        if target in ("all", "top", "top_all", "gimbal", "top_left", "top_right"):
            safe_call(led_ctrl.set_top_led, led_comp_value(target if target not in ("top", "gimbal") else "top_all"), r, g, b, led_effect_value(effect))
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
        if method == "enable_stick_overlay":
            return safe_call(chassis_ctrl.enable_stick_overlay)
        if method == "disable_stick_overlay":
            return safe_call(chassis_ctrl.disable_stick_overlay)
        if method == "set_pwm_value":
            pwm = int(number(params, "pwm", 1))
            if pwm < 1 or pwm > 6:
                return False
            pwm_value = rm_value("pwm" + str(pwm), None)
            if pwm_value is None:
                return False
            return safe_call(chassis_ctrl.set_pwm_value, pwm_value, number(params, "value", 0))
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

    if module == "blaster" and method == "set_led":
        effect = str(params.get("effect", "on")).lower()
        if effect == "off":
            return safe_call(led_ctrl.gun_led_off)
        if effect == "on":
            return safe_call(led_ctrl.gun_led_on)
        return False

    if module == "armor" and method == "set_hit_sensitivity":
        return controller_call("armor_ctrl", "set_hit_sensitivity", int(number(params, "sensitivity", 5)))

    if module == "sensor":
        sensor_id = int(number(params, "sensor_id", number(params, "id", 1)))
        if method == "enable_measure":
            return controller_call("ir_distance_sensor_ctrl", "enable_measure", sensor_id)
        if method == "disable_measure":
            return controller_call("ir_distance_sensor_ctrl", "disable_measure", sensor_id)

    if module == "vision":
        if method == "enable_detection":
            value = vision_detection_value(params.get("name", params.get("type", "marker")))
            return False if value is None else controller_call("vision_ctrl", "enable_detection", value)
        if method == "disable_detection":
            value = vision_detection_value(params.get("name", params.get("type", "marker")))
            return False if value is None else controller_call("vision_ctrl", "disable_detection", value)
        if method == "set_marker_detection_distance":
            return controller_call("vision_ctrl", "set_marker_detection_distance", number(params, "distance", 0))
        if method == "marker_detection_color_set":
            value = vision_color_value("marker", params.get("color", "blue"))
            return False if value is None else controller_call("vision_ctrl", "marker_detection_color_set", value)
        if method == "line_follow_color_set":
            value = vision_color_value("line", params.get("color", "blue"))
            return False if value is None else controller_call("vision_ctrl", "line_follow_color_set", value)
        if method == "detect_marker_and_aim":
            value = marker_value(params.get("marker", "target"))
            return False if value is None else controller_call("vision_ctrl", "detect_marker_and_aim", value)

    if module == "media":
        if method == "play_sound":
            value = sound_value(params.get("sound_id", params.get("sound", 0)))
            return False if value is None else controller_call("media_ctrl", "play_sound", value)
        if method == "capture":
            return controller_call("media_ctrl", "capture")
        if method == "zoom_value_update":
            return controller_call("media_ctrl", "zoom_value_update", number(params, "value", 1))
        if method == "record":
            return controller_call("media_ctrl", "record", params.get("enable", True))
        if method == "enable_sound_recognition":
            value = sound_detection_value(params.get("name", "applause"))
            return False if value is None else controller_call("media_ctrl", "enable_sound_recognition", value)
        if method == "disable_sound_recognition":
            value = sound_detection_value(params.get("name", "applause"))
            return False if value is None else controller_call("media_ctrl", "disable_sound_recognition", value)
        if method == "exposure_value_update":
            value = exposure_value(params.get("value", "medium"))
            return False if value is None else controller_call("media_ctrl", "exposure_value_update", value)

    return False


def apply_fire(command):
    global _led_gun_off_time
    if not command.get("fire", False):
        return
    gun_type = str(command.get("gun_type", command.get("fire_type", "physical"))).lower()
    if gun_type in ("ir", "infrared", "led"):
        safe_call(led_ctrl.gun_led_on)
        _led_gun_off_time = _clock() + 0.08
    else:
        if not safe_call(gun_ctrl.fire_once):
            safe_call(gun_ctrl.fire_continuous)
        safe_call(gun_ctrl.stop)
    command["fire"] = False


def service_fire_events():
    global _led_gun_off_time
    if _led_gun_off_time and _clock() >= _led_gun_off_time:
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


def read_telemetry_values(fields):
    values = {}
    if "x" in fields:
        values["x"] = value_text(
            chassis_ctrl.get_position_based_power_on,
            rm_define.chassis_forward,
        )
    if "y" in fields:
        values["y"] = value_text(
            chassis_ctrl.get_position_based_power_on,
            rm_define.chassis_translation,
        )
    if "yaw" in fields:
        values["yaw"] = value_text(
            chassis_ctrl.get_attitude,
            rm_define.chassis_yaw,
        )
    if "vx" in fields:
        values["vx"] = value_text(
            chassis_ctrl.get_speed,
            rm_define.chassis_forward,
        )
    if "vy" in fields:
        values["vy"] = value_text(
            chassis_ctrl.get_speed,
            rm_define.chassis_translation,
        )
    if "gimbal_yaw" in fields:
        values["gimbal_yaw"] = value_text(
            gimbal_ctrl.get_axis_angle,
            rm_define.gimbal_axis_yaw,
        )
    if "gimbal_pitch" in fields:
        values["gimbal_pitch"] = value_text(
            gimbal_ctrl.get_axis_angle,
            rm_define.gimbal_axis_pitch,
        )
    return values


def telemetry_text(sequence, time_ms, values, session_id):
    parts = [
        '{"type":"telemetry"',
        ',"sequence":' + str(sequence),
        ',"time_ms":' + str(time_ms),
    ]
    if session_id is not None:
        parts.append(',"session_id":' + str(session_id))
    for name in (
        "x",
        "y",
        "yaw",
        "vx",
        "vy",
        "gimbal_yaw",
        "gimbal_pitch",
    ):
        if name in values:
            parts.append(',"' + name + '":' + str(values[name]))
    parts.append("}")
    return "".join(parts)


RECEIVER_PROCESS_CODE = r'''
from collections import deque
import fcntl
import os
import select
import socket
import sys

COMMAND_PORT = __COMMAND_PORT__
MAX_EVENT_FRAMES = 32
MAX_FRAME_SIZE = 4096


def set_nonblocking(fd):
    try:
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    except Exception:
        pass


def frame(source, payload):
    body = source.encode("ascii", "ignore") + b"\x00" + payload
    return len(body).to_bytes(4, "big") + body


def is_priority(payload):
    if b'"stop":true' in payload or b'"method":"stop"' in payload:
        return True
    if b'"method":"set_wheel_speed"' not in payload:
        return False
    return (
        b'"w1":0' in payload
        and b'"w2":0' in payload
        and b'"w3":0' in payload
        and b'"w4":0' in payload
    )


def is_event(payload):
    return (
        b'"module":' in payload
        or b'"method":' in payload
        or b'"fire":true' in payload
        or b'"led":true' in payload
        or b'"mode":' in payload
    )


def main():
    output_fd = sys.stdout.fileno()
    set_nonblocking(output_fd)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
    rx.bind(("0.0.0.0", COMMAND_PORT))
    rx.setblocking(False)
    priority = None
    events = deque(maxlen=MAX_EVENT_FRAMES)
    latest_state = None
    output = bytearray()
    while True:
        readable, writable, _ = select.select(
            [rx],
            [output_fd] if output or priority is not None or events or latest_state is not None else [],
            [],
            None,
        )
        if readable:
            while True:
                try:
                    data, source = rx.recvfrom(2048)
                except (BlockingIOError, OSError):
                    break
                if not data or len(data) > MAX_FRAME_SIZE:
                    continue
                item = frame(source[0], data)
                if is_priority(data):
                    priority = item
                    latest_state = None
                elif is_event(data):
                    events.append(item)
                else:
                    latest_state = item
        if writable:
            if not output:
                if priority is not None:
                    output = bytearray(priority)
                    priority = None
                elif events:
                    output = bytearray(events.popleft())
                elif latest_state is not None:
                    output = bytearray(latest_state)
                    latest_state = None
            if output:
                try:
                    written = os.write(output_fd, output)
                    if written > 0:
                        del output[:written]
                except (BlockingIOError, OSError):
                    pass


main()
'''


SENDER_PROCESS_CODE = r'''
import fcntl
import os
import select
import socket
import sys

TELEMETRY_PORT = __TELEMETRY_PORT__
MAX_FRAME_SIZE = 8192


def set_nonblocking(fd):
    try:
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    except Exception:
        pass


def main():
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    input_fd = sys.stdin.fileno()
    set_nonblocking(input_fd)
    buffer = bytearray()
    while True:
        readable, _, _ = select.select([input_fd], [], [], None)
        if not readable:
            continue
        try:
            chunk = os.read(input_fd, 16384)
        except (BlockingIOError, OSError):
            continue
        if not chunk:
            break
        buffer.extend(chunk)
        while len(buffer) >= 4:
            frame_size = int.from_bytes(buffer[:4], "big")
            if frame_size <= 0 or frame_size > MAX_FRAME_SIZE:
                buffer = bytearray()
                break
            if len(buffer) < 4 + frame_size:
                break
            body = bytes(buffer[4:4 + frame_size])
            del buffer[:4 + frame_size]
            separator = body.find(b"\x00")
            if separator <= 0:
                continue
            target = body[:separator].decode("ascii", "ignore")
            payload = body[separator + 1:]
            try:
                tx.sendto(payload, (target, TELEMETRY_PORT))
            except OSError:
                pass


main()
'''


def start_io_processes():
    python_path = "/data/python_files/bin/python"
    receiver_code = RECEIVER_PROCESS_CODE.replace("__COMMAND_PORT__", str(COMMAND_PORT))
    sender_code = SENDER_PROCESS_CODE.replace("__TELEMETRY_PORT__", str(TELEMETRY_PORT))
    receiver = _subprocess.Popen(
        [python_path, "-u", "-c", receiver_code],
        stdout=_subprocess.PIPE,
        stderr=_subprocess.DEVNULL,
        bufsize=0,
    )
    sender = _subprocess.Popen(
        [python_path, "-u", "-c", sender_code],
        stdin=_subprocess.PIPE,
        stderr=_subprocess.DEVNULL,
        bufsize=0,
    )
    set_nonblocking(receiver.stdout.fileno())
    set_nonblocking(sender.stdin.fileno())
    return receiver, sender


def drain_receiver(receiver, state):
    while True:
        try:
            readable, _, _ = _select.select([receiver.stdout.fileno()], [], [], 0)
            if not readable:
                break
            chunk = _os.read(receiver.stdout.fileno(), 16384)
            if not chunk:
                break
        except Exception:
            break
        state["receiver_buffer"].extend(chunk)
        if len(state["receiver_buffer"]) > 65536:
            del state["receiver_buffer"][:-65536]

    processed = 0
    buffer = state["receiver_buffer"]
    while len(buffer) >= 4 and processed < 256:
        frame_size = int.from_bytes(buffer[:4], "big")
        if frame_size <= 0 or frame_size > 4096:
            buffer.clear()
            break
        if len(buffer) < 4 + frame_size:
            break
        body = bytes(buffer[4:4 + frame_size])
        del buffer[:4 + frame_size]
        separator = body.find(b"\x00")
        if separator <= 0:
            continue
        source = body[:separator].decode("ascii", "ignore")
        try:
            incoming = _json.loads(body[separator + 1:])
        except Exception:
            continue
        if not isinstance(incoming, dict):
            continue
        state["target"] = source or state["target"]
        if incoming.get("session_id") is not None:
            state["session_id"] = int(number(incoming, "session_id", 0))
        module = str(incoming.get("module", "")).lower()
        method = str(incoming.get("method", "")).lower()
        params = generic_params(incoming)
        if module == "system" and method == "set_telemetry":
            fields = params.get("fields", [])
            allowed = {
                "x", "y", "yaw", "vx", "vy",
                "gimbal_yaw", "gimbal_pitch",
            }
            selected_fields = []
            if isinstance(fields, list):
                selected_fields = [
                    str(field) for field in fields if str(field) in allowed
                ]
            maximum_frequency = int(
                clamp(int(1.0 / TELEMETRY_PERIOD_SEC), 1, 50)
            )
            frequency = int(
                clamp(params.get("freq", 1), 1, maximum_frequency)
            )
            requested_rates = params.get("rates", {})
            if not isinstance(requested_rates, dict):
                requested_rates = {}
            telemetry_rates = {
                field: int(
                    clamp(
                        requested_rates.get(field, frequency),
                        1,
                        maximum_frequency,
                    )
                )
                for field in selected_fields
            }
            if telemetry_rates != state["telemetry_rates"]:
                state["telemetry_fields"] = selected_fields
                state["telemetry_rates"] = telemetry_rates
                state["telemetry_next"] = {
                    field: 0.0 for field in selected_fields
                }
                state["telemetry_reschedule"] = True
            processed += 1
            continue
        wheel_stop = (
            module == "chassis"
            and method == "set_wheel_speed"
            and int(number(params, "w1", 0)) == 0
            and int(number(params, "w2", 0)) == 0
            and int(number(params, "w3", 0)) == 0
            and int(number(params, "w4", 0)) == 0
        )
        command_sequence = int(number(incoming, "command_seq", 0))
        priority_stop = (
            wheel_stop
            or incoming.get("stop", False)
            or (method == "stop" and module in ("chassis", "gimbal"))
        )
        if (
            not priority_stop
            and command_sequence
            and command_sequence <= state["last_priority_sequence"]
        ):
            processed += 1
            continue
        if priority_stop and command_sequence:
            state["last_priority_sequence"] = max(
                state["last_priority_sequence"],
                command_sequence,
            )
        if wheel_stop:
            state["pending_commands"] = []
            state["priority_commands"].append(incoming)
            if len(state["priority_commands"]) > MAX_PRIORITY_EVENTS:
                del state["priority_commands"][:-MAX_PRIORITY_EVENTS]
            processed += 1
            continue
        if method == "stop" and module == "chassis":
            state["chassis_command"] = default_chassis_command()
            state["last_chassis_motion_time"] = _clock()
            state["pending_commands"] = []
            state["priority_commands"].append(incoming)
            if len(state["priority_commands"]) > MAX_PRIORITY_EVENTS:
                del state["priority_commands"][:-MAX_PRIORITY_EVENTS]
            processed += 1
            continue
        if method == "stop" and module == "gimbal":
            state["gimbal_command"] = default_gimbal_command()
            state["last_gimbal_motion_time"] = _clock()
            state["pending_commands"] = []
            state["priority_commands"].append(incoming)
            if len(state["priority_commands"]) > MAX_PRIORITY_EVENTS:
                del state["priority_commands"][:-MAX_PRIORITY_EVENTS]
            processed += 1
            continue
        updates_motion = command_updates_motion_state(incoming)
        if updates_motion:
            now = _clock()
            normalized = official_command(incoming)
            if normalized.get("stop", False):
                state["chassis_command"] = default_chassis_command()
                state["gimbal_command"] = default_gimbal_command()
                state["last_chassis_motion_time"] = now
                state["last_gimbal_motion_time"] = now
                state["pending_commands"] = []
                state["priority_commands"].append(normalized)
            else:
                if has_chassis_motion_fields(normalized):
                    chassis_was_moving = not chassis_command_is_zero(state["chassis_command"])
                    state["chassis_command"] = merge_command(state["chassis_command"], normalized)
                    state["last_chassis_motion_time"] = now
                    if chassis_was_moving and chassis_command_is_zero(state["chassis_command"]):
                        state["priority_commands"].append(
                            {"module": "chassis", "method": "stop"}
                        )
                if has_gimbal_motion_fields(normalized):
                    gimbal_was_moving = not gimbal_command_is_zero(state["gimbal_command"])
                    state["gimbal_command"] = merge_command(state["gimbal_command"], normalized)
                    state["last_gimbal_motion_time"] = now
                    if gimbal_was_moving and gimbal_command_is_zero(state["gimbal_command"]):
                        state["priority_commands"].append(
                            {"module": "gimbal", "method": "stop"}
                        )
        else:
            state["pending_commands"].append(incoming)
        if len(state["pending_commands"]) > MAX_PENDING_EVENTS:
            del state["pending_commands"][:-MAX_PENDING_EVENTS]
        if len(state["priority_commands"]) > MAX_PRIORITY_EVENTS:
            del state["priority_commands"][:-MAX_PRIORITY_EVENTS]
        processed += 1
    return processed


def make_pipe_frame(target, payload):
    body = target.encode("ascii", "ignore") + b"\x00" + payload.encode("utf-8")
    return len(body).to_bytes(4, "big") + body


def flush_telemetry(sender, state):
    if sender.poll() is not None:
        return False
    while True:
        if not state["sender_buffer"]:
            latest = state["sender_latest"]
            if latest is None:
                return True
            state["sender_buffer"] = bytearray(latest)
            state["sender_latest"] = None
        try:
            written = _os.write(sender.stdin.fileno(), state["sender_buffer"])
        except Exception:
            return False
        if written <= 0:
            return False
        del state["sender_buffer"][:written]


def queue_telemetry(sender, state, target, payload):
    frame = make_pipe_frame(target, payload)
    if state["sender_buffer"]:
        state["sender_latest"] = frame
    else:
        state["sender_buffer"] = bytearray(frame)
    return flush_telemetry(sender, state)


def start():
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    chassis_ctrl.set_rotate_speed(120)
    gimbal_ctrl.set_rotate_speed(120)
    _initialize_lab_runtime()
    receiver_process, sender_process = start_io_processes()
    state = {
        "chassis_command": default_chassis_command(),
        "gimbal_command": default_gimbal_command(),
        "target": "255.255.255.255",
        "last_chassis_motion_time": _clock(),
        "last_gimbal_motion_time": _clock(),
        "sequence": 0,
        "pending_commands": [],
        "priority_commands": [],
        "receiver_buffer": bytearray(),
        "sender_buffer": bytearray(),
        "sender_latest": None,
        "last_priority_sequence": -1,
        "telemetry_fields": [],
        "telemetry_rates": {},
        "telemetry_next": {},
        "telemetry_reschedule": False,
        "session_id": None,
    }

    def command_loop():
        scheduler_start = _clock()
        next_chassis_motion_time = scheduler_start
        next_gimbal_motion_time = scheduler_start
        next_telemetry_time = scheduler_start
        while True:
            if receiver_process.poll() is not None or sender_process.poll() is not None:
                stop_motion()
                return
            drain_receiver(receiver_process, state)
            flush_telemetry(sender_process, state)
            chassis_command = state["chassis_command"].copy()
            gimbal_command = state["gimbal_command"].copy()
            last_chassis_motion_time = state["last_chassis_motion_time"]
            last_gimbal_motion_time = state["last_gimbal_motion_time"]
            pending_commands = state["pending_commands"]
            priority_commands = state["priority_commands"]
            state["pending_commands"] = []
            state["priority_commands"] = []
            for priority_command in priority_commands:
                apply_command(priority_command)
            for pending_command in pending_commands:
                apply_command(pending_command)
            now = _clock()
            service_fire_events()
            next_wake_times = []
            chassis_active = not chassis_command_is_zero(chassis_command)
            if chassis_active and now >= next_chassis_motion_time:
                if now - last_chassis_motion_time <= COMMAND_TIMEOUT_SEC:
                    apply_chassis_state(chassis_command)
                else:
                    chassis_command = decay_chassis_command(chassis_command)
                    apply_chassis_state(chassis_command)
                    state["chassis_command"] = chassis_command.copy()
                next_chassis_motion_time += CONTROL_PERIOD_SEC
                after_chassis = _clock()
                if next_chassis_motion_time <= after_chassis:
                    missed_periods = int((after_chassis - next_chassis_motion_time) / CONTROL_PERIOD_SEC) + 1
                    next_chassis_motion_time += missed_periods * CONTROL_PERIOD_SEC
            if chassis_active:
                next_wake_times.append(next_chassis_motion_time)
            else:
                next_chassis_motion_time = now + CONTROL_PERIOD_SEC

            gimbal_active = not gimbal_command_is_zero(gimbal_command)
            if gimbal_active and now >= next_gimbal_motion_time:
                if now - last_gimbal_motion_time <= COMMAND_TIMEOUT_SEC:
                    apply_gimbal_state(gimbal_command)
                else:
                    gimbal_command = decay_gimbal_command(gimbal_command)
                    apply_gimbal_state(gimbal_command)
                    state["gimbal_command"] = gimbal_command.copy()
                next_gimbal_motion_time += CONTROL_PERIOD_SEC
                after_gimbal = _clock()
                if next_gimbal_motion_time <= after_gimbal:
                    missed_periods = int((after_gimbal - next_gimbal_motion_time) / CONTROL_PERIOD_SEC) + 1
                    next_gimbal_motion_time += missed_periods * CONTROL_PERIOD_SEC
            if gimbal_active:
                next_wake_times.append(next_gimbal_motion_time)
            else:
                next_gimbal_motion_time = now + CONTROL_PERIOD_SEC

            if state["telemetry_reschedule"]:
                next_telemetry_time = now
                state["telemetry_reschedule"] = False
            if now >= next_telemetry_time:
                # All Lab controller getters and setters run in this one loop.
                # The I/O child processes never import or call Lab controllers.
                telemetry_next = state["telemetry_next"]
                due_fields = [
                    field
                    for field in state["telemetry_fields"]
                    if now >= telemetry_next.get(field, 0.0)
                ]
                if due_fields:
                    telemetry_values = read_telemetry_values(due_fields)
                    target = state["target"]
                    sequence = state["sequence"]
                    state["sequence"] = sequence + 1
                    queue_telemetry(
                        sender_process,
                        state,
                        target,
                        telemetry_text(
                            sequence,
                            int(_time.time() * 1000),
                            telemetry_values,
                            state["session_id"],
                        ),
                    )
                    after_telemetry = _clock()
                    for field in due_fields:
                        field_period = 1.0 / state["telemetry_rates"][field]
                        field_deadline = telemetry_next.get(field, 0.0)
                        if field_deadline <= 0.0:
                            field_deadline = now
                        field_deadline += field_period
                        if field_deadline <= after_telemetry:
                            field_deadline += (
                                int(
                                    (after_telemetry - field_deadline)
                                    / field_period
                                )
                                + 1
                            ) * field_period
                        telemetry_next[field] = field_deadline
                if telemetry_next:
                    next_telemetry_time = min(telemetry_next.values())
                else:
                    next_telemetry_time = now + 1.0
            next_wake_times.append(next_telemetry_time)
            if _led_gun_off_time:
                next_wake_times.append(_led_gun_off_time)

            wait_time = min(next_wake_times) - _clock()
            if wait_time > 0:
                try:
                    _select.select([receiver_process.stdout.fileno()], [], [], wait_time)
                except Exception:
                    _time.sleep(wait_time)

    try:
        command_loop()
    finally:
        stop_motion()
        for process in (receiver_process, sender_process):
            try:
                process.terminate()
            except Exception:
                pass
