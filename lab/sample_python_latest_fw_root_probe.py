def rm_import(module):
    builtins = rm_define.__dict__["__builtins__"]
    real_import = builtins["__import__"] if isinstance(builtins, dict) else builtins.__import__
    return real_import(module, globals(), locals(), [], 0)


def signal_success(time_module):
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    gimbal_ctrl.set_rotate_speed(120)
    gimbal_ctrl.rotate(rm_define.gimbal_right)
    time_module.sleep(0.20)
    gimbal_ctrl.rotate(rm_define.gimbal_left)
    time_module.sleep(0.20)
    gimbal_ctrl.rotate_with_speed(0, 0)


def signal_failure():
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    chassis_ctrl.set_rotate_speed(45)
    chassis_ctrl.rotate_with_time(rm_define.clockwise, 0.15)
    time.sleep(0.05)
    chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.15)
    chassis_ctrl.stop()


def start():
    try:
        sub_process = rm_import("subprocess")
        time_module = rm_import("time")
        proc = sub_process.Popen(
            "/system/bin/adb_en.sh",
            shell=True,
            executable="/system/bin/sh",
            stdout=sub_process.PIPE,
            stderr=sub_process.PIPE,
        )
        print("latest fw root probe started:", proc.pid)
        time_module.sleep(0.5)
        print("latest fw root probe poll:", proc.poll())
        signal_success(time_module)
    except Exception as exc:
        print("latest fw root probe failed:", str(exc))
        signal_failure()
