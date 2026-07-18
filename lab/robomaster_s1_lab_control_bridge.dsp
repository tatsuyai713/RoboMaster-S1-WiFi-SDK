<dji><attribute><creation_date>2019/03/27</creation_date><sign>58958c2c42992b0f</sign><modify_time>7/18/2026 3:28:31 PM</modify_time><guid>f956500c57747ce908aab54c74f3137c</guid><creator>Anonymous</creator><firmware_version_dependency>00.00.0000</firmware_version_dependency><title>Twister-Py</title><code_type>python</code_type><app_min_version></app_min_version><app_max_version></app_max_version></attribute><audio-list /><code><python_code><![CDATA[COMMAND_PORT = 40923
TELEMETRY_PORT = 40924
CONTROL_PERIOD_SEC = 0.02
COMMAND_TIMEOUT_SEC = 0.3
COMMAND_DECAY_PER_TICK = 0.92
COMMAND_ZERO_EPSILON = 0.02
COMMAND_ANGULAR_ZERO_EPSILON = 0.08
MAX_CHASSIS_SPEED = 1.0
MAX_CHASSIS_YAW_SPEED = 120.0
MAX_GIMBAL_SPEED = 120.0


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


def value_text(fn, arg):
    try:
        return str(float(fn(arg)))
    except Exception:
        return "null"


def set_robot_mode(command):
    mode = str(command.get("mode", "")).lower()
    if mode in ("free", "robot_mode_free"):
        safe_call(robot_ctrl.set_mode, rm_define.robot_mode_free)
    elif mode in ("gimbal_follow", "follow", "robot_mode_gimbal_follow"):
        safe_call(robot_ctrl.set_mode, rm_define.robot_mode_gimbal_follow)
    elif mode in ("chassis_follow", "chassis_lead", "robot_mode_chassis_follow"):
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
    command["stop"] = False
    command["fire"] = False
    command["led"] = False
    return command


def command_is_zero(command):
    return (
        number(command, "x", number(command, "vx", 0.0)) == 0.0
        and number(command, "y", number(command, "vy", 0.0)) == 0.0
        and number(command, "z", number(command, "chassis_yaw_rate", 0.0)) == 0.0
        and number(command, "gimbal_pitch", number(command, "gimbal_pitch_rate", 0.0)) == 0.0
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
        safe_call(led_ctrl.turn_off, rm_define.armor_all)
    else:
        if target in ("all", "bottom", "bottom_all"):
            safe_call(led_ctrl.set_bottom_led, rm_define.armor_bottom_all, r, g, b, rm_define.effect_always_on)
        if target in ("all", "top", "top_all", "gimbal"):
            safe_call(led_ctrl.set_top_led, rm_define.armor_top_all, r, g, b, rm_define.effect_always_on)
    command["led"] = False


def apply_fire(command, time_module):
    if not command.get("fire", False):
        return
    gun_type = str(command.get("gun_type", command.get("fire_type", "physical"))).lower()
    if gun_type in ("ir", "infrared", "led"):
        safe_call(led_ctrl.gun_led_on)
        time_module.sleep(0.08)
        safe_call(led_ctrl.gun_led_off)
    else:
        if not safe_call(gun_ctrl.fire_once):
            safe_call(gun_ctrl.fire_continuous)
        safe_call(gun_ctrl.stop)
    command["fire"] = False


def apply_command(command, time_module):
    set_robot_mode(command)
    if "mode" in command and len(command) == 1:
        stop_motion()
        return
    if command.get("stop", False):
        stop_motion()
        return
    vx = clamp(number(command, "x", number(command, "vx", 0.0)), -1.0, 1.0)
    vy = clamp(number(command, "y", number(command, "vy", 0.0)), -1.0, 1.0)
    yaw = clamp(number(command, "z", number(command, "chassis_yaw_rate", 0.0)), -1.0, 1.0)
    gp = clamp(number(command, "gimbal_pitch", number(command, "gimbal_pitch_rate", 0.0)), -1.0, 1.0)
    gy = clamp(number(command, "gimbal_yaw", number(command, "gimbal_yaw_rate", 0.0)), -1.0, 1.0)
    safe_call(chassis_ctrl.move_with_speed, vx * MAX_CHASSIS_SPEED, vy * MAX_CHASSIS_SPEED, yaw * MAX_CHASSIS_YAW_SPEED)
    safe_call(gimbal_ctrl.rotate_with_speed, gy * MAX_GIMBAL_SPEED, gp * MAX_GIMBAL_SPEED)
    apply_led(command)
    apply_fire(command, time_module)


def build_telemetry_text(sequence, time_ms):
    return (
        '{"type":"telemetry"'
        + ',"sequence":' + str(sequence)
        + ',"time_ms":' + str(time_ms)
        + ',"x":' + value_text(chassis_ctrl.get_position_based_power_on, rm_define.chassis_forward)
        + ',"y":' + value_text(chassis_ctrl.get_position_based_power_on, rm_define.chassis_translation)
        + ',"yaw":' + value_text(chassis_ctrl.get_attitude, rm_define.chassis_yaw)
        + ',"vx":' + value_text(chassis_ctrl.get_speed, rm_define.chassis_forward)
        + ',"vy":' + value_text(chassis_ctrl.get_speed, rm_define.chassis_translation)
        + ',"gimbal_yaw":' + value_text(gimbal_ctrl.get_axis_angle, rm_define.gimbal_axis_yaw)
        + ',"gimbal_pitch":' + value_text(gimbal_ctrl.get_axis_angle, rm_define.gimbal_axis_pitch)
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
        rx.bind(("0.0.0.0", COMMAND_PORT))
        rx.setblocking(False)
        tx = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_DGRAM)
        tx.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_REUSEADDR, 1)
        tx.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_BROADCAST, 1)
        command = {"stop": True, "x": 0.0, "y": 0.0, "z": 0.0, "gimbal_pitch": 0.0, "gimbal_yaw": 0.0}
        target = ("255.255.255.255", TELEMETRY_PORT)
        last_command_time = time_module.time()
        sequence = 0
        next_send_time = time_module.time()
        while True:
            try:
                data, source = rx.recvfrom(2048)
                target = (source[0], TELEMETRY_PORT)
                command = json_module.loads(data.decode("utf-8"))
                last_command_time = time_module.time()
            except Exception:
                pass

            if time_module.time() - last_command_time > COMMAND_TIMEOUT_SEC:
                if command_is_zero(command):
                    command = {"stop": True, "x": 0.0, "y": 0.0, "z": 0.0, "gimbal_pitch": 0.0, "gimbal_yaw": 0.0}
                else:
                    command = decay_command(command)

            apply_command(command, time_module)
            telemetry_text = build_telemetry_text(sequence, int(time_module.time() * 1000))
            tx.sendto(telemetry_text.encode("utf-8"), target)
            sequence += 1
            next_send_time += CONTROL_PERIOD_SEC
            wait_time = next_send_time - time_module.time()
            if wait_time > 0:
                time_module.sleep(wait_time)
            else:
                next_send_time = time_module.time()
    except Exception as exc:
        print("child udp bridge failed:", str(exc))
        mark_failure(time_module)
        return
]]></python_code><scratch_description><![CDATA[]]></scratch_description></code></dji>
