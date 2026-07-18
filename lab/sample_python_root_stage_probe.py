def mark_stage(stage, time_module=None):
    # Strict global alternation:
    #   stage 0 wheel -> stop
    #   stage 1 gimbal -> stop
    #   stage 2 wheel -> stop
    #   stage 3 gimbal -> stop
    # There is never wheel and gimbal movement in the same stage.
    chassis_ctrl.stop()
    gimbal_ctrl.rotate_with_speed(0, 0)

    if stage % 2 == 0:
        if (stage // 2) % 2 == 0:
            chassis_ctrl.rotate_with_time(rm_define.clockwise, 0.12)
        else:
            chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.12)
    else:
        if (stage // 2) % 2 == 0:
            gimbal_ctrl.rotate_with_speed(35, 0)
        else:
            gimbal_ctrl.rotate_with_speed(-35, 0)
        if time_module is not None:
            time_module.sleep(0.05)
        else:
            for _index in range(100):
                pass

    chassis_ctrl.stop()
    gimbal_ctrl.rotate_with_speed(0, 0)

    if time_module is not None:
        time_module.sleep(0.03)
    else:
        for _index in range(100):
            pass


def start():
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    chassis_ctrl.set_rotate_speed(50)
    gimbal_ctrl.set_rotate_speed(90)
    time_module = None

    # Stage 0: start() reached.
    mark_stage(0)

    try:
        builtins = rm_define.__dict__["__builtins__"]
        if isinstance(builtins, dict):
            real_import = builtins["__import__"]
        else:
            real_import = builtins.__import__

        try:
            time_module = real_import("time", globals(), locals(), [], 0)
        except Exception:
            time_module = None

        # Stage 1: import backdoor exists.
        mark_stage(1, time_module)
    except Exception as exc:
        print("stage1 failed:", str(exc))
        return

    try:
        sub_process = real_import("subprocess", globals(), locals(), [], 0)

        # Stage 2: process module import succeeded.
        mark_stage(2, time_module)
    except Exception as exc:
        print("stage2 failed:", str(exc))
        return

    try:
        shell_path = "/system/bin/sh"
        adb_path = "/system/bin/adb_en.sh"
        proc = sub_process.Popen(
            adb_path,
            shell=True,
            executable=shell_path,
            stdout=sub_process.PIPE,
            stderr=sub_process.PIPE,
        )
        print("stage3 process pid:", proc.pid)

        # Stage 3: adb helper process started.
        mark_stage(3, time_module)
    except Exception as exc:
        print("stage3 failed:", str(exc))
        return

    try:
        if time_module is not None:
            time_module.sleep(0.5)

        # Stage 4: delay after helper succeeded.
        mark_stage(4, time_module)
    except Exception as exc:
        print("stage4 failed:", str(exc))
        return

    try:
        child = sub_process.Popen(
            ["/data/python_files/bin/python", "-u", "-c", "print('ok')"],
            stdout=sub_process.PIPE,
            stderr=sub_process.PIPE,
        )
        print("stage5 child pid:", child.pid)

        # Stage 5: unrestricted child Python process started.
        mark_stage(5, time_module)
    except Exception as exc:
        print("stage5 failed:", str(exc))
        return
