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


def show_success(time_module):
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    gimbal_ctrl.set_rotate_speed(120)
    gimbal_ctrl.rotate(rm_define.gimbal_right)
    time_module.sleep(0.25)
    gimbal_ctrl.rotate(rm_define.gimbal_left)
    time_module.sleep(0.25)
    gimbal_ctrl.rotate_with_speed(0, 0)


def show_failure():
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    chassis_ctrl.set_rotate_speed(45)
    chassis_ctrl.rotate_with_time(rm_define.clockwise, 0.15)
    chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.15)
    chassis_ctrl.stop()


def start():
    try:
        subprocess = rm_import("subprocess")
        time_module = rm_import("time")
        output = subprocess.check_output(
            ["/data/python_files/bin/python", "-u", "-c", "print('root-child-ok')"]
        )
        print("root probe:", output.decode("utf-8", "replace").strip())
        show_success(time_module)
    except Exception as exc:
        print("root probe failed:", str(exc))
        show_failure()
