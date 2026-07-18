#block id="RMmPcLmmMtEFuS1Z03ov" color="#1088F2" name="robot_on_start" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
def start():
    #block id="rhJU6LqgcqxhSaLMP9LC" color="#7EBAD9" name="robot_switch_chassis_mode" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    robot_ctrl.set_mode(rm_define.robot_mode_free)
    #block id="7i8LO8D90xDEkIsRu0o8" color="#651FFF" name="robot_set_rotate_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    chassis_ctrl.set_rotate_speed(120)
    #block id="YMImUvlEuT2069urfokr" color="#E04C41" name="robot_set_gimbal_rotate_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    gimbal_ctrl.set_rotate_speed(120)
    #block id="ymuSLGnbP1ls4F2q0HKU" color="#EC6337" name="robot_fire_continuous" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    gun_ctrl.fire_continuous()
    #block id="jk9CbN2CY2wzDpB5qo6c" color="#4350AF" name="control_forever" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
    while True:
        #block id="5qHWyGihw5y1bqq9basv" color="#E04C41" name="robot_rotate_gimbal_with_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        gimbal_ctrl.rotate(rm_define.gimbal_right)
        #block id="xPTd5ur2HK51NSe6xBlV" color="#651FFF" name="robot_rotate_chassis_withDuration" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.2)
        #block id="DRpBpRfZiSf59gj2L3Na" color="#E04C41" name="robot_rotate_gimbal_with_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        gimbal_ctrl.rotate(rm_define.gimbal_left)
        #block id="3k6GCKOi1FGEAEB2zU5n" color="#651FFF" name="robot_rotate_chassis_withDuration" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        chassis_ctrl.rotate_with_time(rm_define.clockwise, 0.4)
        #block id="Br1o6a1B6rL09V28CTyv" color="#E04C41" name="robot_rotate_gimbal_with_speed" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        gimbal_ctrl.rotate(rm_define.gimbal_right)
        #block id="o1gSYcQv6N1pGc0iD6bl" color="#651FFF" name="robot_rotate_chassis_withDuration" curvar="" minVersion="" deviceMinVersion="" blockStatus=""
        chassis_ctrl.rotate_with_time(rm_define.anticlockwise, 0.2)
