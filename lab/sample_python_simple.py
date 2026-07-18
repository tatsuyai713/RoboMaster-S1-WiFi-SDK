def start():
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    chassis_ctrl.set_rotate_speed(90)
    gimbal_ctrl.set_rotate_speed(90)

    gimbal_ctrl.rotate(rm_define.gimbal_right)
    time.sleep(0.5)
    gimbal_ctrl.rotate(rm_define.gimbal_left)
    time.sleep(0.5)
    gimbal_ctrl.rotate_with_speed(0, 0)

    chassis_ctrl.rotate_with_time(rm_define.clockwise, 0.4)
    chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.4)
    chassis_ctrl.stop()
