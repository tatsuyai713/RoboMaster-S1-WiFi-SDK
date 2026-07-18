def start():
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    chassis_ctrl.set_rotate_speed(120)
    gimbal_ctrl.set_rotate_speed(120)
    gun_ctrl.fire_continuous()
    while True:
        gimbal_ctrl.rotate(rm_define.gimbal_right)
        chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.2)
        gimbal_ctrl.rotate(rm_define.gimbal_left)
        chassis_ctrl.rotate_with_time(rm_define.clockwise, 0.4)
        gimbal_ctrl.rotate(rm_define.gimbal_right)
        chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.2)
