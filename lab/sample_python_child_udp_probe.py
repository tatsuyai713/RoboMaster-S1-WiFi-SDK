def root_me(module):
    builtins = rm_define.__dict__["__builtins__"]
    real_import = builtins["__import__"] if isinstance(builtins, dict) else builtins.__import__
    return real_import(module, globals(), locals(), [], 0)


def mark_success():
    chassis_ctrl.rotate_with_time(rm_define.clockwise, 0.12)
    chassis_ctrl.stop()


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


def apply_test_motion_phase(phase):
    try:
        if phase == 0:
            chassis_ctrl.move_with_speed(0.25, 0, 0)
            gimbal_ctrl.rotate_with_speed(0, 0)
        elif phase == 1:
            chassis_ctrl.move_with_speed(-0.25, 0, 0)
            gimbal_ctrl.rotate_with_speed(0, 0)
        elif phase == 2:
            chassis_ctrl.move_with_speed(0, 0.20, 0)
            gimbal_ctrl.rotate_with_speed(0, 0)
        elif phase == 3:
            chassis_ctrl.move_with_speed(0, -0.20, 0)
            gimbal_ctrl.rotate_with_speed(0, 0)
        elif phase == 4:
            chassis_ctrl.move_with_speed(0, 0, 45)
            gimbal_ctrl.rotate_with_speed(0, 0)
        elif phase == 5:
            chassis_ctrl.move_with_speed(0, 0, -45)
            gimbal_ctrl.rotate_with_speed(0, 0)
        elif phase == 6:
            chassis_ctrl.move_with_speed(0, 0, 0)
            gimbal_ctrl.rotate_with_speed(35, 0)
        elif phase == 7:
            chassis_ctrl.move_with_speed(0, 0, 0)
            gimbal_ctrl.rotate_with_speed(-35, 0)
        elif phase == 8:
            chassis_ctrl.move_with_speed(0, 0, 0)
            gimbal_ctrl.rotate_with_speed(0, 35)
        elif phase == 9:
            chassis_ctrl.move_with_speed(0, 0, 0)
            gimbal_ctrl.rotate_with_speed(0, -35)
        else:
            stop_motion()
    except Exception:
        stop_motion()


def build_telemetry_text(sequence, time_ms):
    try:
        x = chassis_ctrl.get_position_based_power_on(rm_define.chassis_forward)
        x_text = str(float(x))
    except Exception:
        x_text = "null"
    try:
        y = chassis_ctrl.get_position_based_power_on(rm_define.chassis_translation)
        y_text = str(float(y))
    except Exception:
        y_text = "null"
    try:
        yaw = chassis_ctrl.get_attitude(rm_define.chassis_yaw)
        yaw_text = str(float(yaw))
    except Exception:
        yaw_text = "null"
    try:
        vx = chassis_ctrl.get_speed(rm_define.chassis_forward)
        vx_text = str(float(vx))
    except Exception:
        vx_text = "null"
    try:
        vy = chassis_ctrl.get_speed(rm_define.chassis_translation)
        vy_text = str(float(vy))
    except Exception:
        vy_text = "null"
    try:
        gimbal_yaw = gimbal_ctrl.get_axis_angle(rm_define.gimbal_axis_yaw)
        gimbal_yaw_text = str(float(gimbal_yaw))
    except Exception:
        gimbal_yaw_text = "null"
    try:
        gimbal_pitch = gimbal_ctrl.get_axis_angle(rm_define.gimbal_axis_pitch)
        gimbal_pitch_text = str(float(gimbal_pitch))
    except Exception:
        gimbal_pitch_text = "null"
    return (
        '{"type":"telemetry"'
        + ',"sequence":' + str(sequence)
        + ',"time_ms":' + str(time_ms)
        + ',"x":' + x_text
        + ',"y":' + y_text
        + ',"yaw":' + yaw_text
        + ',"vx":' + vx_text
        + ',"vy":' + vy_text
        + ',"gimbal_yaw":' + gimbal_yaw_text
        + ',"gimbal_pitch":' + gimbal_pitch_text
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
        tx = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_DGRAM)
        tx.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_REUSEADDR, 1)
        tx.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_BROADCAST, 1)
        sequence = 0
        last_phase = -1
        next_send_time = time_module.time()
        while True:
            phase = (sequence // 25) % 12
            if phase != last_phase:
                apply_test_motion_phase(phase)
                last_phase = phase
            now = time_module.time()
            telemetry_text = build_telemetry_text(sequence, int(now * 1000))
            tx.sendto(telemetry_text.encode("utf-8"), ("255.255.255.255", 40924))
            sequence += 1
            next_send_time += 0.02
            wait_time = next_send_time - time_module.time()
            if wait_time > 0:
                time_module.sleep(wait_time)
            else:
                next_send_time = time_module.time()
    except Exception as exc:
        print("child udp tx failed:", str(exc))
        mark_failure(time_module)
        return
