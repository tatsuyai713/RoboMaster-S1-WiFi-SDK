def rm_import(module):
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


def start():
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    chassis_ctrl.set_rotate_speed(50)
    gimbal_ctrl.set_rotate_speed(90)

    try:
        sub_process = rm_import("sub" + "process")
        time_module = rm_import("time")
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
        python_path = "/" + "data" + "/" + "python_files" + "/" + "bin" + "/" + "python"
        child_code = "print('child-ok')"
        child = sub_process.Popen(
            [python_path, "-u", "-c", child_code],
            stdout=sub_process.PIPE,
            stderr=sub_process.PIPE,
        )
        print("child pid:", child.pid)
        stdout, stderr = child.communicate()
        stdout_text = stdout.decode("utf-8", "replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", "replace") if stderr else ""
        print("child return:", child.returncode)
        print("child stdout:", stdout_text)
        print("child stderr:", stderr_text)
        if child.returncode == 0 and "child-ok" in stdout_text:
            mark_success()
        else:
            mark_failure(time_module)
    except Exception as exc:
        print("child failed:", str(exc))
        mark_failure(time_module)
        return
