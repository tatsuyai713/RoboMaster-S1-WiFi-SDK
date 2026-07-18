#block id="wCfDdMEtWBGKNnBZaCUo" color="#1088F2" name="robot_on_start" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
def start():
    #block id="7g86etu44i3C7e3XvCiF" color="#7EBAD9" name="robot_switch_chassis_mode" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    #block id="NV2TnzJGO2LFslvvlL8K" color="#651FFF" name="robot_set_rotate_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    chassis_ctrl.set_rotate_speed(120)
    #block id="ZtC6jfhgFhcShiYL9Lrh" color="#E04C41" name="robot_set_gimbal_rotate_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    gimbal_ctrl.set_rotate_speed(120)
    #block id="qU3bUxjlpK0hjPCf3mOG" color="#EC6337" name="robot_fire_continuous" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    gun_ctrl.fire_continuous()
    #block id="73eej6LndeL06tzwzyIY" color="#4350AF" name="control_forever" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    while True:
        #block id="lUWzgRCckhVkRUZWzzQY" color="#E04C41" name="robot_rotate_gimbal_with_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        gimbal_ctrl.rotate(rm_define.gimbal_right)
        #block id="IbalbwDmdsi5wPaBeZbM" color="#651FFF" name="robot_rotate_chassis_withDuration" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.2)
        #block id="cTltI0ZsU5Bha28sMYmM" color="#E04C41" name="robot_rotate_gimbal_with_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        gimbal_ctrl.rotate(rm_define.gimbal_left)
        #block id="mPtFn9VjgdI8dsl74ZGV" color="#651FFF" name="robot_rotate_chassis_withDuration" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        chassis_ctrl.rotate_with_time(rm_define.clockwise, 0.4)
        #block id="5oE5DaTfOKr3FMM2WtNU" color="#E04C41" name="robot_rotate_gimbal_with_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        gimbal_ctrl.rotate(rm_define.gimbal_right)
        #block id="dcpLRxiNsZj8E3cQj0DP" color="#651FFF" name="robot_rotate_chassis_withDuration" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.2)
