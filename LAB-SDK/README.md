# RoboMaster S1 LAB-SDK

This SDK provides a DJI RoboMaster SDK-style API for RoboMaster S1 by running a Lab-mode bridge script on the robot.

The user-facing code should look like the official SDK style:

```python
from robomaster import robot, blaster

ep_robot = robot.Robot(appid="b6359877", robot_ip="192.168.23.149")
ep_robot.initialize(conn_type="sta")

ep_robot.chassis.drive_speed(x=0.3, y=0, z=0)
ep_robot.gimbal.drive_speed(yaw_speed=30, pitch_speed=0)
ep_robot.blaster.fire(fire_type=blaster.INFRARED_FIRE)
ep_robot.chassis.stop()

ep_robot.close()
```

Internally, `initialize()` uses the S1 Wi-Fi/AppID connection, enters Lab mode, uploads a DSP bridge, starts it, and sends command packets to the robot-side bridge. Host commands are sent as single-shot SDK commands; the robot-side bridge holds the latest control state and runs the real Lab Python commands.

## Official SDK Compatibility

The official DJI RoboMaster Python SDK documents modules such as `robomaster.robot`, `chassis`, `gimbal`, `blaster`, `led`, `camera`, `battery`, `armor`, `sensor`, `vision`, and EP extension modules. This LAB-SDK intentionally targets RoboMaster S1 only. EP-only hardware modules are import-compatible placeholders, not supported features.

| Official SDK area | Official-style API | LAB-SDK status | Notes |
|---|---|---:|---|
| `robomaster.robot` | `Robot()` | Supported | Constructor accepts `robot_ip`, `local_ip`, `appid`, `debug`. |
| `robomaster.robot` | `initialize(conn_type="sta", proto_type="udp")` | Supported | Connects with S1 Wi-Fi/AppID and can auto-enter Lab mode. |
| `robomaster.robot` | `close()` | Supported | Stops command stream/bridge, stops Lab program, closes Wi-Fi connection. |
| `robomaster.robot` | `set_robot_mode()` | Partial | Supports `free`, `gimbal_follow`, `chassis_follow` names used by this SDK. |
| `robomaster.robot` | `chassis`, `gimbal`, `blaster`, `led`, `camera`, `battery`, `armor`, `sensor`, `vision`, `media` components | Supported/partial | Exposed as attributes on `Robot`, matching official component style where applicable to S1. |
| `robomaster.action` | `Action.wait_for_completed()` | Stub | `ImmediateAction` always completes immediately. Used by simple `move()`/`recenter()` compatibility. |
| `robomaster.chassis` | `drive_speed(x, y, z)` | Supported | Maps to robot-side `chassis_ctrl.move_with_speed()`. Command is single-shot; robot bridge holds latest state. |
| `robomaster.chassis` | `stop()` | Supported | Sends zero chassis command immediately. |
| `robomaster.chassis` | `move(x, y, z, xy_speed, z_speed)` | Partial | Maps distance/angle requests to S1 Lab distance/degree commands and returns an immediate action object. |
| `robomaster.chassis` | `drive_wheels(w1, w2, w3, w4)` | Supported | Maps to `chassis_ctrl.set_wheel_speed()`. |
| `robomaster.chassis` | `sub_position()` | Partial | Callback receives Lab telemetry values. Frequency argument is accepted but robot telemetry period controls actual rate. |
| `robomaster.chassis` | `sub_velocity()` | Partial | Callback receives Lab telemetry values. |
| `robomaster.chassis` | `sub_attitude()` | Partial | Callback receives yaw telemetry. |
| `robomaster.gimbal` | `drive_speed(pitch_speed, yaw_speed)` | Supported | Maps to robot-side `gimbal_ctrl.rotate_with_speed()`. |
| `robomaster.gimbal` | `rotate_with_speed(yaw_speed, pitch_speed)` | Supported | Compatibility wrapper for Lab-side command order. |
| `robomaster.gimbal` | `stop()` | Supported | Sends zero gimbal command immediately. |
| `robomaster.gimbal` | `recenter()` | Supported | Maps to `gimbal_ctrl.recenter()` and returns an immediate action object. |
| `robomaster.gimbal` | `move()`, `moveto()` | Partial | Maps to S1 Lab degree/angle commands and returns an immediate action object. |
| `robomaster.gimbal` | `sub_angle()` | Partial | Callback receives Lab telemetry gimbal yaw/pitch. |
| `robomaster.blaster` | `INFRARED_FIRE`, `WATER_FIRE` | Supported | Constants are exposed. |
| `robomaster.blaster` | `fire(fire_type=...)` | Supported | `INFRARED_FIRE` maps to LED GUN; `WATER_FIRE` maps to physical GUN. |
| `robomaster.led` | `set_led(comp, r, g, b, effect, freq)` | Supported/partial | Supports S1 top/bottom LEDs through Lab `led_ctrl`; effect mapping is backed by S1 Lab constants when present. |
| `robomaster.led` | `set_gimbal_led()` | Partial | Maps to top/gimbal LED target. |
| `robomaster.camera` | `start_video_stream()` | Supported by base Wi-Fi path | Uses the existing S1 H.264 reception path, not Lab Python. |
| `robomaster.camera` | `read_video_frame()` | Supported | Returns H.264 payload bytes from the queue. |
| `robomaster.camera` | `stop_video_stream()` | Stub | Returns success; current video reception is managed by the base connection. |
| `robomaster.battery` | `get_battery()` | Partial | Returns last parsed battery value when available from base telemetry. |
| `robomaster.armor` | `sub_hit_event()`, `sub_ir_event()`, `id2comp()`, `comp2id()` | API-compatible partial | Callback hooks are available. They emit only if the underlying S1 connection provides `armor_damage` events. |
| `robomaster.armor` | `set_hit_sensitivity()` | Supported | Maps to `armor_ctrl.set_hit_sensitivity()`. |
| `robomaster.sensor` | `DistanceSensor.sub_distance()` | Safe stub | Import/API compatible; returns `False` because S1 Lab bridge does not expose EP distance sensor hardware. |
| `robomaster.sensor` | `enable_measure()`, `disable_measure()` | Supported/partial | Maps to `ir_distance_sensor_ctrl`; distance callbacks are not forwarded yet. |
| `robomaster.vision` | `enable_detection()`, `disable_detection()`, `set_color()` | Supported/partial | Maps to S1 Lab `vision_ctrl`; detection callbacks are not forwarded yet. |
| `robomaster.media` | `play_sound()`, `capture()`, `record()`, `zoom_value_update()` | Supported/partial | Maps to S1 Lab `media_ctrl`; file/result retrieval is not implemented. |
| EP-only modules | `servo`, `robotic_arm`, `gripper`, `uart`, `ai_module`, `flight`, `sensor_adaptor` | Not supported | Import-compatible placeholders only. Stock S1 support is intentionally prioritized. |
| `robomaster.action` | `Action` / `ImmediateAction` | Supported stub | Immediate action object supports `wait_for_completed()`. |
| `robomaster.exceptions` | SDK exception classes | Supported stub | Provides `RoboMasterError`, `ConnectionError`, `TimeoutError`, `UnsupportedError`. |
| `robomaster.version` | `__version__` | Supported | Exposes LAB-SDK version. |

## LAB-SDK Extensions

These helpers are not official SDK APIs, but are provided to make the Lab-mode bridge usable:

| Extension | Purpose |
|---|---|
| `Robot.enter_lab()` | Sends the S1 Lab-mode transition sequence. |
| `Robot.upload_lab_bridge()` | Builds/uploads the robot-side DSP bridge. |
| `Robot.start_lab_bridge()` | Starts the uploaded Lab bridge and Host bridge. |
| `Robot.stop_lab_program()` | Stops the Lab program sequence. |
| `LabBridge` | Host UDP bridge for single-shot commands and telemetry callbacks. |
| `upload_program()` | Uploads a selected `lab/*.dsp` program from the GUI/tooling. |

## Current Design Rules

- GUI commands go through the SDK facade under `LAB-SDK/robomaster`.
- Host-to-robot commands are treated as single-shot SDK calls.
- The robot-side bridge stores the latest motion state and applies it on the robot side.
- Telemetry is the only intentional periodic UDP stream from the robot to the host.
- Lab-specific upload/start/stop helpers are extensions; normal robot operations should use official-style component APIs where possible.
- EP extension modules that are not available on a stock S1 are not part of the supported feature set. Some modules remain importable only to avoid import failures in official SDK-style samples.

## Backing By S1 Lab Python Commands

This section compares LAB-SDK official-style APIs with the S1 Lab command list in `Robomaster S1 Python Commands.py`.

The LAB-SDK must keep the official SDK surface. The S1 Lab command list is used only as the robot-side implementation source for APIs that can be backed by stock S1 Lab commands. It is not exposed as a second public API.

| LAB-SDK official-style API | Backing S1 Lab command | Covered by command list | Current implementation |
|---|---|---:|---|
| `robot.set_robot_mode("free")` | `robot_ctrl.set_mode(rm_define.robot_mode_free)` | Yes | Implemented |
| `robot.set_robot_mode("gimbal_follow")` | `robot_ctrl.set_mode(rm_define.robot_mode_gimbal_follow)` | Yes | Implemented |
| `robot.set_robot_mode("chassis_follow")` | `robot_ctrl.set_mode(rm_define.robot_mode_chassis_follow)` | Yes | Implemented |
| `chassis.drive_speed(x, y, z)` | `chassis_ctrl.move_with_speed(...)` | Yes | Implemented |
| `chassis.stop()` | `chassis_ctrl.stop()` and zero speed | Yes | Implemented |
| `chassis.move(...)` | `chassis_ctrl.move_with_distance`, `rotate_with_degree` | Yes | Partial official compatibility |
| `chassis.drive_wheels(...)` | `chassis_ctrl.set_wheel_speed(...)` | Yes | Implemented |
| chassis speed settings | `chassis_ctrl.set_trans_speed`, `set_rotate_speed` | Yes | Implemented as S1 extension helpers |
| chassis follow offset | `chassis_ctrl.set_follow_gimbal_offset(...)` | Yes | Implemented as S1 extension helper |
| `gimbal.drive_speed(...)` | `gimbal_ctrl.rotate_with_speed(...)` | Yes | Implemented |
| `gimbal.stop()` | `gimbal_ctrl.stop()` and zero speed | Yes | Implemented |
| `gimbal.recenter()` | `gimbal_ctrl.recenter()` | Yes | Implemented |
| gimbal absolute/degree controls | `rotate_with_degree`, `yaw_ctrl`, `pitch_ctrl`, `angle_ctrl` | Yes | Implemented as official-style `move()`/`moveto()` plus S1 helpers |
| `blaster.fire(INFRARED_FIRE)` | `led_ctrl.gun_led_on/off()` or `ir_blaster_ctrl.fire_once()` | Yes | Implemented as LED GUN pulse |
| `blaster.fire(WATER_FIRE)` | `gun_ctrl.fire_once()` | Yes | Implemented |
| `led.set_led(...)` | `led_ctrl.set_bottom_led`, `set_top_led`, `turn_off` | Yes | Implemented for top/bottom/all/gimbal targets |
| LED flash/single LED APIs | `led_ctrl.set_flash`, `set_single_led` | Yes | Implemented as S1 extension helpers |
| `camera.start_video_stream/read_video_frame` | S1 video stream, not Lab Python command | No | Implemented through Wi-Fi H.264 path |
| `battery.get_battery/sub_battery_info` | Telemetry, not this Lab command list | No | Partial through base Wi-Fi telemetry |
| `armor.sub_hit_event/sub_ir_event` | `armor_ctrl` conditions/events | Yes | API hook exists; Lab bridge does not yet forward armor events |
| `armor.set_hit_sensitivity` | `armor_ctrl.set_hit_sensitivity(...)` | Yes | Implemented |
| `sensor.sub_distance` | `ir_distance_sensor_ctrl.enable_measure/cond_wait` | Yes | Partial: enable/disable implemented; callback values not forwarded |
| `sensor_adaptor` APIs | `sensor_adapter_ctrl.cond_wait(...)` | Yes | Safe stub |
| `vision` detection APIs | `vision_ctrl.enable_detection`, `disable_detection`, color, aim, condition APIs | Yes | Partial: commands implemented; callback values not forwarded |
| `media` sound/capture/record/zoom | `media_ctrl.play_sound/capture/record/zoom_value_update` | Yes | Implemented/partial |
| `servo`, `robotic_arm`, `gripper`, `uart`, `ai_module`, `flight` | Not present in the S1 command list as stock S1 commands | No | Not supported for stock S1 |

Coverage summary:

- Covered and implemented from the command list: robot mode, chassis speed/stop/wheel speed/basic distance and rotate actions, gimbal speed/recenter/basic angle controls, blaster, LED color/effects helpers, armor sensitivity, vision command toggles, and media command toggles.
- Covered but still partial: action completion tracking, armor/vision/distance event forwarding, sensor adapter condition values, and media result retrieval.
- Not supported: EP extension modules such as servo, robotic arm, gripper, UART, AI module, and drone/flight APIs.
