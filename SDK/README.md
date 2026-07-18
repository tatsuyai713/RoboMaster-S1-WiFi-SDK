# RoboMaster S1 Wi-Fi SDK

Experimental Python SDK for RoboMaster S1 using the Windows App compatible Wi-Fi protocol.

これは、Windows App互換のWi-Fi通信を使う RoboMaster S1 向け実験的Python SDKです。

## English

### Status

This SDK is not the official DJI RoboMaster SDK. A stock RoboMaster S1 does not expose the same official EP SDK connection path, so this package uses the protocol reverse-engineered in this repository:

- QR/AppID pairing
- UDP/10607 outer envelope
- DUSS frame generation
- Solo mode setup
- chassis control
- gimbal control
- LED GUN trigger
- LED RGB
- video setting commands
- speed setting commands
- voice language / volume
- PC microphone transmit / robot microphone receive request
- robot discovery from S1 broadcast
- armor damage callback
- telemetry parsing
- H.264 payload callback

The implementation generates packets from the current connection state. It does not replay PCAP files.

### Official-Style Basic Usage

The preferred API shape follows DJI's official RoboMaster Python SDK where it
can be mapped safely:

```python
from robomaster import robot, blaster

ep_robot = robot.Robot(appid="b6359877")
ep_robot.initialize(conn_type="sta")

ep_robot.set_robot_mode(robot.FREE)
ep_robot.chassis.drive_speed(x=0.5, y=0.0, z=0.0)
ep_robot.gimbal.drive_speed(pitch_speed=0.0, yaw_speed=0.4)
ep_robot.blaster.fire(fire_type=blaster.INFRARED_FIRE, times=1)
ep_robot.chassis.stop()

ep_robot.close()
```

Official-style modules and methods now provided:

- `from robomaster import robot`
- `robot.Robot(...).initialize(conn_type="sta", proto_type="udp", sn=None)`
- `robot.Robot.close()`
- `robot.Robot.set_robot_mode(robot.FREE | robot.GIMBAL_LEAD | robot.CHASSIS_LEAD)`
- `robot.Robot.get_robot_mode()`
- `robot.Robot.chassis.drive_speed(x, y, z, timeout=None)`
- `robot.Robot.chassis.drive_wheels(w1, w2, w3, w4)`
- `robot.Robot.chassis.stop()`
- `robot.Robot.chassis.sub_position(...) / sub_velocity(...) / sub_attitude(...) / sub_status(...)`
- `robot.Robot.gimbal.drive_speed(pitch_speed, yaw_speed)`
- `robot.Robot.gimbal.recenter() / suspend() / resume()`
- `robot.Robot.gimbal.calibrate()`
- `robot.Robot.gimbal.sub_angle(...)`
- `robot.Robot.blaster.fire(fire_type="ir" | "water", times=1)`
- `robot.Robot.blaster.set_led(brightness=255, effect="on")`
- `robot.Robot.led.set_led(comp="all", r=..., g=..., b=..., effect="on", freq=1)`
- `robot.Robot.camera.start_video_stream(...) / read_video_frame(...) / stop_video_stream()`
- `robot.Robot.camera.format_sd_card()`
- `robot.Robot.camera.start_audio_stream() / read_audio_frame() / stop_audio_stream()`
- `robot.Robot.armor.sub_hit_event(...) / sub_ir_event(...)`
- `robot.Robot.battery.sub_battery_info(...) / get_battery()`

Unsupported EP-only or not-yet-mapped official methods intentionally raise
`NotImplementedError` instead of silently sending guessed packets.

`chassis.drive_speed()` follows the official SDK behavior: the robot keeps
moving at the requested speed until another speed command or `chassis.stop()`
is sent. The SDK default control timer is 50 Hz. Solo-mode Windows App captures
show roughly 20-21 ms control-frame intervals, with normal capture/scheduler
jitter.

### S1-Specific Usage

Run examples from the repository root with `SDK` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = ".;.\SDK"
python .\SDK\examples\basic_control.py
```

Generate a Wi-Fi QR code:

```python
from robomaster_s1_sdk import build_wifi_qr_data, save_qr

qr = build_wifi_qr_data("YOUR_WIFI_SSID", "YOUR_WIFI_PASSWORD", "b6359877")
save_qr(qr.qr_text, "robomaster_wifi.png")
print(qr.header8)
```

Or use the S1-specific robot API directly:

```python
from robomaster_s1_sdk import Robot, discover_robots

robots = discover_robots(timeout=4.0)
robot_ip = robots[0].ip if robots else ""

robot = Robot(appid="b6359877", robot_ip=robot_ip)
robot.initialize()
robot.enter_solo()

robot.chassis.forward()
robot.blaster.fire()
robot.chassis.stop()

robot.exit_solo()
robot.close()
# robot.poweroff()  # Sends the robot poweroff sequence and closes the connection.
```

Lab mode has been moved out of this SDK.

Use the separate `LAB-SDK` folder for the Lab-mode implementation. That package
keeps the DJI RoboMaster SDK-style API shape but executes robot-side operations
through S1 Lab Python commands.

### API Overview

```python
robot = Robot(appid="b6359877")
robot.initialize()
robot.enter_solo()
robot.exit_solo()
robot.close()
```

### PCAP-Derived Additions

The following APIs were added from commands observed in the local PCAPNG logs:

| API | Command | Log evidence |
|---|---|---|
| `chassis.drive_wheels(w1, w2, w3, w4)` | `0x3f/20`, payload four little-endian signed wheel values | motor addressing capture |
| `chassis.start_calibration()` | `0x03/f9 e4a3997d03` | chassis/gimbal calibration capture |
| `chassis.enter_calibration_measurement()` | `0x03/f9 e4a3997d01` | chassis/gimbal calibration capture |
| `gimbal.calibrate()` | `0x04/08`, empty payload | chassis/gimbal calibration capture |
| `camera.format_sd_card()` | `0x02/72 00` | SD format capture |
| `settings.set_auto_sleep(enabled, seconds)` | `0x3f/4a`, payload `enabled + uint16_le seconds` | sleep/poweroff capture |
| `settings.query_auto_sleep()` | `0x3f/4b`, empty payload | sleep/poweroff capture |

Modules:

- `discover_robots(timeout=4.0)`
- `build_wifi_qr_data(ssid, password, appid)`
- `make_header8_from_appid(appid)`
- `make_payload(ssid, password, header8)`
- `make_qr_image(qr_text) / save_qr(qr_text, path)`
- `robot.chassis.forward() / backward() / left() / right() / stop()`
- `robot.chassis.move(x=0.0, y=0.0, z=0.0)`
- `robot.gimbal.up() / down() / left() / right() / stop()`
- `robot.gimbal.drive_speed(pitch=0.0, yaw=0.0)`
- `robot.gimbal.set_control_sensitivity(pitch=40, yaw=50)`
- `robot.blaster.set_type("led" | "physical")`
- `robot.blaster.fire()`
- `robot.led.set_color(r, g, b)`
- `robot.camera.set_resolution("720p" | "1080p")`
- `robot.camera.set_antiflicker(50 | 60)`
- `robot.camera.set_3d_quality("low" | "medium" | "high")`
- `robot.settings.set_speed_preset("slow" | "medium" | "fast" | "custom")`
- `robot.settings.set_custom_speed(...)`
- `robot.settings.set_max_speed(forward=1.5, backward=1.5, lateral=1.5)`
- `robot.settings.set_acceleration(starting=50, braking=50, lateral_starting=50, lateral_braking=50)`
- `robot.settings.set_voice_language("English" | "日本語" | ...)`
- `robot.settings.set_volume(0..80)`
- `robot.settings.set_auto_sleep(enabled=True, seconds=60)`
- `robot.settings.query_auto_sleep()`
- `robot.poweroff()` / `robot.settings.poweroff()`
- `robot.audio.request_rx()`
- `robot.audio.start_tx() / stop_tx()`
- `robot.audio.send_pcm_block(pcm_bytes)`
- Lab-mode APIs are provided by the separate `LAB-SDK` package.

Telemetry callbacks:

```python
robot.on("gimbal", lambda value: print(value))
robot.on("odometry", lambda value: print(value))
robot.on("stats", lambda value: print(value))
robot.on("armor_damage", lambda value: print(value))
robot.on("video", lambda h264: ...)
robot.on("duss", lambda frame: ...)
```

### Official SDK Feature Coverage

The comparison below is based on the `jeguzzi/RoboMaster-SDK` fork, which is a fork of DJI's RoboMaster Python SDK for EP with modern Python/media fixes. Its module layout includes `robot`, `chassis`, `gimbal`, `camera`, `vision`, `blaster`, `led`, `battery`, `armor`, `robotic_arm`, `gripper`, `servo`, `sensor`, `ai_module`, and Tello/drone modules. This S1 Wi-Fi SDK follows the same style where possible, but it talks through the S1 Windows App-compatible Wi-Fi protocol instead of the official EP SDK connection path.

Coverage legend:

- Full: implemented as a direct high-level SDK API.
- Partial: implemented, but with fewer parameters, no official task object, or S1-specific behavior.
- Raw: data is observable through callbacks/raw DUSS, but no official-style high-level API yet.
- None: not implemented.
- N/A: EP/Tello-specific hardware or official SDK path feature that does not apply to stock S1 Wi-Fi control.

| Official module | Official API / feature in `jeguzzi/RoboMaster-SDK` | This SDK API / behavior | Coverage | Notes |
|---|---|---|---|---|
| `robot` | `Robot()`, `initialize(conn_type, proto_type, sn)`, `close()` | `Robot(appid, robot_ip)`, `initialize()`, `close()` | Partial | Uses QR/AppID + Windows App UDP path, not EP SDK connection. |
| `robot` | `Drone()` / Tello initialization | none | N/A | Tello/Drone code is outside S1 ground robot scope. |
| `robot` | `scan`, connection wait, SN-targeted connection | `discover_robots(timeout)` | Partial | Discovers S1 broadcast IP/appid/state, not official EP discovery. |
| `robot` | `get_version()`, `get_sn()` | raw broadcast/DUSS info only | Raw | No official-style `get_version()` / `get_sn()` wrapper yet. |
| `robot` | `set_robot_mode(FREE, GIMBAL_LEAD, CHASSIS_LEAD)`, `get_robot_mode()` | `enter_solo()`, `exit_solo()`, mode keepalive | Partial | S1 Windows App Solo/Lab/Battle behavior differs from EP mode API. |
| `robot` | `reset()`, `reset_robot_mode()` | not implemented | None | |
| `robot` | `play_audio(filename)`, `play_sound(sound_id, times)` | sound-effect command notes only | None | Sound effects are documented separately; not exposed as API. |
| `chassis` | `stop()` | `chassis.stop()` | Full | Sends neutral control payload. |
| `chassis` | `drive_speed(x, y, z, timeout)` | `chassis.drive_speed(x, y, z, timeout)` and direction helpers | Partial | Official method name is implemented. The selected speed is transmitted continuously at 50 Hz until `stop()`. |
| `chassis` | `drive_wheels(w1, w2, w3, w4)` | `chassis.drive_wheels(w1, w2, w3, w4)` | Partial | Uses the `0x3f/20` wheel command observed in motor-addressing logs. |
| `chassis` | `move(x, y, z, xy_speed, z_speed)` action object | `chassis.move(...)` returns an immediate action after applying speed | Partial | True distance/angle task action is not mapped yet. |
| `chassis` | `set_pwm_value()`, `set_pwm_freq()` | not implemented | N/A | EP PWM expansion feature. |
| `chassis` | `stick_overlay()` | not implemented | None | |
| `chassis` | `sub_position()` | `chassis.sub_position(...)` backed by decoded odometry | Partial | Current odometry parser is S1-log-derived, not official position subject. |
| `chassis` | `sub_attitude()` | `chassis.sub_attitude(...)` backed by decoded odometry heading | Partial | |
| `chassis` | `sub_status()` | `chassis.sub_status(...)` backed by decoded stats | Partial | Stats include known distance/time/battery-like fields where decoded. |
| `chassis` | `sub_imu()` | raw DUSS only | Raw | |
| `chassis` | `sub_mode()` | raw DUSS only | Raw | |
| `chassis` | `sub_esc()` | not implemented | None | |
| `chassis` | `sub_velocity()` | `chassis.sub_velocity(...)` backed by decoded odometry | Partial | |
| `gimbal` | `drive_speed(pitch_speed, yaw_speed)` | `gimbal.drive_speed(pitch_speed, yaw_speed)` | Partial | Official method name is implemented with S1 command scale. |
| `gimbal` | `move()`, `moveto()` action objects | not implemented | None | |
| `gimbal` | `recenter()` | `gimbal.recenter()` | Partial | Stops gimbal; full recenter trajectory is not mapped yet. |
| `gimbal` | calibration-style functions | `gimbal.calibrate()` | Partial | Uses the `0x04/08` gimbal auto-calibration start command from calibration logs. |
| `gimbal` | `suspend()`, `resume()` | `gimbal.suspend()`, `gimbal.resume()` | Partial | Safe no-op/stop style mapping. |
| `gimbal` | `sub_angle()` | `gimbal.sub_angle(...)` backed by decoded S1 `0x48/08` telemetry | Partial | |
| `gimbal` | work mode APIs | control sensitivity and S1 mode-related commands | Partial | S1 Windows App has different mode/settings flow. |
| `camera` | `start_video_stream()`, `stop_video_stream()` | official-style names backed by H.264 payload queue | Partial | Decoded CV2 image output is not implemented in SDK core. |
| `camera` | `read_video_frame()`, `read_cv2_image()` | `read_video_frame()` implemented; `read_cv2_image()` not implemented | Partial | |
| `camera` | `start_audio_stream()`, `stop_audio_stream()`, `read_audio_frame()` | official-style names backed by audio payload queue | Partial | S1 audio is handled through known App commands. |
| `camera` | `record_audio()` | not implemented | None | |
| `camera` | `take_photo()` | not implemented | None | |
| `camera` | SD card format | `camera.format_sd_card()` | Partial | Uses the `0x02/72 00` command observed in format-SD logs. |
| `camera` | `_set_zoom()` | not implemented | None | |
| `camera` | `set_resolution()` | `camera.set_resolution("720p" / "1080p")` | Partial | S1 setting command implemented from logs. |
| `camera` | FPS/bitrate/down-vision settings | anti-flicker and 3D quality only | Partial | Official FPS/bitrate APIs are not mapped. |
| `media` | video/audio decoder/display pipeline | GUI-side PyAV decoder | Partial | SDK core keeps raw callbacks; app handles display/audio playback. |
| `vision` | marker/line/robot/person/gesture detection subscribe | not implemented | None | |
| `vision` | detection color/function control | not implemented | None | |
| `blaster` | `fire(fire_type=WATER/INFRARED, times)` | `blaster.fire(fire_type, times)` | Partial | Maps `ir` to LED GUN and `water` to physical GUN mode. |
| `blaster` | `set_led(brightness, effect)` | `blaster.set_led(brightness, effect)` | Partial | Maps to general S1 LED color because separate blaster LED effect is not fully mapped. |
| `led` | `set_led(comp, r, g, b, effect, freq)` | `led.set_led(comp, r, g, b, effect, freq)` | Partial | Component/effect/frequency are accepted but currently mapped to global RGB on/off. |
| `led` | `set_gimbal_led(...)` | `led.set_gimbal_led(...)` | Partial | Uses the same global RGB mapping. |
| `battery` | `sub_battery_info()` | `battery.sub_battery_info(...)`, `battery.get_battery()` | Partial | Battery value is emitted only when decoded from S1 telemetry. |
| `armor` | `sub_hit_event()` | `armor.sub_hit_event(...)` | Full | LED/physical armor damage events are decoded from S1 DUSS. |
| `armor` | `sub_ir_event()` | `armor.sub_ir_event(...)` | Partial | IR/LED hit is represented in unified damage callback. |
| `armor` | `set_hit_sensitivity(comp, sensitivity)` | not implemented | None | |
| `robotic_arm` | `reset()`, `recenter()`, `move()`, `moveto()`, `sub_position()` | not implemented | N/A | EP extension module, not stock S1. |
| `gripper` | `open()`, `close()`, `pause()`, `sub_status()` | not implemented | N/A | EP extension module, not stock S1. |
| `servo` | `moveto()`, `drive_speed()`, `pause()`, `get_angle()`, `sub_servo_info()` | not implemented | N/A | EP expansion feature. |
| `sensor` | distance sensor `sub_distance()` | not implemented | N/A | EP/Tello extension path. |
| `sensor_adaptor` | `get_adc()`, `get_io()`, `get_pulse_period()`, `sub_adapter()` | not implemented | N/A | EP extension module. |
| `ai_module` | `init_ai_module()`, `sub_ai_event()` | not implemented | N/A | EP AI module feature. |
| `flight` | takeoff/land/go/rc/mission pad | not implemented | N/A | Tello/drone-only feature. |
| S1 pairing | not part of EP SDK API | `build_wifi_qr_data()`, `make_header8_from_appid()`, `save_qr()` | Full | S1-specific Windows App pairing support. |
| S1 app settings | not part of EP SDK API | speed preset/custom speed, voice language, volume, auto sleep, poweroff | Partial | S1 Windows App settings reconstructed from logs. |

### Files

| File | Role |
|---|---|
| `robomaster_s1_sdk/robot.py` | High-level Robot facade and connection loop |
| `robomaster_s1_sdk/protocol.py` | DUSS, telemetry decode, payload helpers |
| `robomaster_s1_sdk/qr.py` | Wi-Fi QR/AppID payload generation |
| `robomaster_s1_sdk/chassis.py` | Chassis API |
| `robomaster_s1_sdk/gimbal.py` | Gimbal API |
| `robomaster_s1_sdk/blaster.py` | GUN API |
| `robomaster_s1_sdk/led.py` | RGB LED API |
| `robomaster_s1_sdk/camera.py` | Video setting API |
| `robomaster_s1_sdk/audio.py` | Audio request/session API |
| `robomaster_s1_sdk/settings.py` | Speed, voice language, volume API |

## 日本語

### 状態

このSDKはDJI公式 RoboMaster SDKではありません。通常状態のRoboMaster S1ではEPと同じ公式SDK接続経路が使えないため、このパッケージは本リポジトリで解析したWindows App互換プロトコルを使います。

対応している主な要素:

- QR/AppIDペアリング
- UDP/10607 outer envelope
- DUSSフレーム生成
- Soloモード初期化
- シャシー操作
- ジンバル操作
- LED GUN発射
- LED RGB設定
- 映像設定コマンド
- 速度設定コマンド
- 音声言語 / 音量
- PCマイク送信 / 機体マイク受信要求
- S1ブロードキャストからの機体検索
- アーマーダメージcallback
- テレメトリ解析
- H.264 payload callback

通常動作ではPCAPファイルを再生しません。現在の接続状態からパケットを生成します。

### 公式SDK風の基本的な使い方

基本のAPI形状は、可能な範囲でDJI公式 RoboMaster Python SDKに合わせます。

```python
from robomaster import robot, blaster

ep_robot = robot.Robot(appid="b6359877")
ep_robot.initialize(conn_type="sta")

ep_robot.set_robot_mode(robot.FREE)
ep_robot.chassis.drive_speed(x=0.5, y=0.0, z=0.0)
ep_robot.gimbal.drive_speed(pitch_speed=0.0, yaw_speed=0.4)
ep_robot.blaster.fire(fire_type=blaster.INFRARED_FIRE, times=1)
ep_robot.chassis.stop()

ep_robot.close()
```

対応済みの公式風API:

- `from robomaster import robot`
- `robot.Robot(...).initialize(conn_type="sta", proto_type="udp", sn=None)`
- `robot.Robot.close()`
- `robot.Robot.set_robot_mode(robot.FREE | robot.GIMBAL_LEAD | robot.CHASSIS_LEAD)`
- `robot.Robot.chassis.drive_speed(x, y, z, timeout=None)`
- `robot.Robot.chassis.drive_wheels(w1, w2, w3, w4)`
- `robot.Robot.gimbal.drive_speed(pitch_speed, yaw_speed)`
- `robot.Robot.gimbal.calibrate()`
- `robot.Robot.blaster.fire(fire_type="ir" | "water", times=1)`
- `robot.Robot.led.set_led(...)`
- `robot.Robot.camera.start_video_stream() / read_video_frame()`
- `robot.Robot.camera.format_sd_card()`
- `robot.Robot.camera.start_audio_stream() / read_audio_frame()`
- `robot.Robot.armor.sub_hit_event()`
- `robot.Robot.battery.sub_battery_info()`

EP専用、またはS1 Wi-Fiで未解析の公式APIは、推測送信せず
`NotImplementedError` にしています。

QR/AppID、速度プリセット、音声言語、音量、PoweroffなどはS1独自拡張APIとして
`robomaster_s1_sdk` 側に残しています。

`chassis.drive_speed()` は公式SDKと同じく、指定速度で走り続け、
別の速度指示または `chassis.stop()` まで継続します。SDKの既定control timerは
50Hzです。SoloモードのWindows Appログでは20-21ms前後のcontrol frame間隔が見えており、
PCAP取得やWindows側スケジューラの揺れを含むものとして扱います。

### S1独自APIの基本的な使い方

リポジトリルートから、`SDK` を `PYTHONPATH` に入れて実行します。

```powershell
$env:PYTHONPATH = ".;.\SDK"
python .\SDK\examples\basic_control.py
```

Wi-Fi QRコード生成:

```python
from robomaster_s1_sdk import build_wifi_qr_data, save_qr

qr = build_wifi_qr_data("YOUR_WIFI_SSID", "YOUR_WIFI_PASSWORD", "b6359877")
save_qr(qr.qr_text, "robomaster_wifi.png")
print(qr.header8)
```

ロボットAPIを直接使う例:

```python
from robomaster_s1_sdk import Robot, discover_robots

robots = discover_robots(timeout=4.0)
robot_ip = robots[0].ip if robots else ""

robot = Robot(appid="b6359877", robot_ip=robot_ip)
robot.initialize()
robot.enter_solo()

robot.chassis.forward()
robot.blaster.fire()
robot.chassis.stop()

robot.exit_solo()
robot.close()
# robot.poweroff()  # 本体Poweroff列を送信して接続を閉じます。
```

LabモードはこのSDKから分離しました。

Labモード実装は別フォルダの `LAB-SDK` を使用してください。`LAB-SDK`
はDJI RoboMaster SDK風のAPI形状を保ちつつ、実機側の処理をS1 Lab Python
Commandsで実行します。

### API概要

```python
robot = Robot(appid="b6359877")
robot.initialize()
robot.enter_solo()
robot.exit_solo()
robot.close()
```

### PCAPNG由来の追加API

ローカルPCAPNGで確認できたPC送信コマンドから、以下を追加しています。

| API | Command | 根拠 |
|---|---|---|
| `chassis.drive_wheels(w1, w2, w3, w4)` | `0x3f/20`, payloadは4個のlittle-endian signed wheel値 | motor addressingログ |
| `chassis.start_calibration()` | `0x03/f9 e4a3997d03` | chassis/gimbal calibrationログ |
| `chassis.enter_calibration_measurement()` | `0x03/f9 e4a3997d01` | chassis/gimbal calibrationログ |
| `gimbal.calibrate()` | `0x04/08`, empty payload | chassis/gimbal calibrationログ |
| `camera.format_sd_card()` | `0x02/72 00` | SD formatログ |
| `settings.set_auto_sleep(enabled, seconds)` | `0x3f/4a`, payloadは `enabled + uint16_le seconds` | sleep/poweroffログ |
| `settings.query_auto_sleep()` | `0x3f/4b`, empty payload | sleep/poweroffログ |

モジュール:

- `discover_robots(timeout=4.0)`
- `build_wifi_qr_data(ssid, password, appid)`
- `make_header8_from_appid(appid)`
- `make_payload(ssid, password, header8)`
- `make_qr_image(qr_text) / save_qr(qr_text, path)`
- `robot.chassis.forward() / backward() / left() / right() / stop()`
- `robot.chassis.move(x=0.0, y=0.0, z=0.0)`
- `robot.gimbal.up() / down() / left() / right() / stop()`
- `robot.gimbal.drive_speed(pitch=0.0, yaw=0.0)`
- `robot.gimbal.set_control_sensitivity(pitch=40, yaw=50)`
- `robot.blaster.set_type("led" | "physical")`
- `robot.blaster.fire()`
- `robot.led.set_color(r, g, b)`
- `robot.camera.set_resolution("720p" | "1080p")`
- `robot.camera.set_antiflicker(50 | 60)`
- `robot.camera.set_3d_quality("low" | "medium" | "high")`
- `robot.settings.set_speed_preset("slow" | "medium" | "fast" | "custom")`
- `robot.settings.set_custom_speed(...)`
- `robot.settings.set_max_speed(forward=1.5, backward=1.5, lateral=1.5)`
- `robot.settings.set_acceleration(starting=50, braking=50, lateral_starting=50, lateral_braking=50)`
- `robot.settings.set_voice_language("English" | "日本語" | ...)`
- `robot.settings.set_volume(0..80)`
- `robot.settings.set_auto_sleep(enabled=True, seconds=60)`
- `robot.settings.query_auto_sleep()`
- `robot.poweroff()` / `robot.settings.poweroff()`
- `robot.audio.request_rx()`
- `robot.audio.start_tx() / stop_tx()`
- `robot.audio.send_pcm_block(pcm_bytes)`

テレメトリcallback:

```python
robot.on("gimbal", lambda value: print(value))
robot.on("odometry", lambda value: print(value))
robot.on("stats", lambda value: print(value))
robot.on("armor_damage", lambda value: print(value))
robot.on("video", lambda h264: ...)
robot.on("duss", lambda frame: ...)
```

### 公式SDK機能との対応状況

下表は `jeguzzi/RoboMaster-SDK` forkを確認して作成しています。このforkはDJI公式RoboMaster Python SDKのforkで、EP向けSDKに近い構成を持ち、`robot`, `chassis`, `gimbal`, `camera`, `vision`, `blaster`, `led`, `battery`, `armor`, `robotic_arm`, `gripper`, `servo`, `sensor`, `ai_module` と Tello/drone系moduleを含みます。このS1 Wi-Fi SDKは可能な範囲でAPIの雰囲気を合わせていますが、接続経路は公式EP SDKではなく、S1 Windows App互換Wi-Fiプロトコルです。

対応状況の意味:

- 対応: 高レベルSDK APIとして実装済み。
- 一部対応: 実装済みだが、公式SDKより引数が少ない、task objectがない、またはS1固有挙動。
- Raw: callback/raw DUSSとして観測可能だが、公式風APIには未整理。
- 未対応: 未実装。
- 対象外: stock S1 Wi-Fi制御では対象外のEP/Tello固有ハードウェアまたは公式SDK経路機能。

| 公式module | `jeguzzi/RoboMaster-SDK` のAPI/機能 | このSDKのAPI/挙動 | 対応状況 | 備考 |
|---|---|---|---|---|
| `robot` | `Robot()`, `initialize(conn_type, proto_type, sn)`, `close()` | `Robot(appid, robot_ip)`, `initialize()`, `close()` | 一部対応 | QR/AppID + Windows App UDP経路を使う。 |
| `robot` | `Drone()` / Tello初期化 | なし | 対象外 | Tello/DroneはS1地上機の対象外。 |
| `robot` | scan、接続待ち、SN指定接続 | `discover_robots(timeout)` | 一部対応 | S1 broadcastのIP/appid/stateを検索。 |
| `robot` | `get_version()`, `get_sn()` | broadcast情報とraw DUSSのみ | Raw | 公式風wrapperは未実装。 |
| `robot` | `set_robot_mode(FREE, GIMBAL_LEAD, CHASSIS_LEAD)`, `get_robot_mode()` | `enter_solo()`, `exit_solo()`, mode keepalive | 一部対応 | S1 AppのSolo/Lab/Battle状態はEP mode APIと異なる。 |
| `robot` | `reset()`, `reset_robot_mode()` | 未実装 | 未対応 | |
| `robot` | `play_audio(filename)`, `play_sound(sound_id, times)` | 効果音コマンドは文書化のみ | 未対応 | APIとしては出していない。 |
| `chassis` | `stop()` | `chassis.stop()` | 対応 | neutral control payloadを送信。 |
| `chassis` | `drive_speed(x, y, z, timeout)` | `chassis.drive_speed(x, y, z, timeout)` / 方向helper | 一部対応 | 公式名で実装。`stop()`まで50Hzで継続送信。 |
| `chassis` | `drive_wheels(w1, w2, w3, w4)` | `chassis.drive_wheels(w1, w2, w3, w4)` | 一部対応 | motor-addressingログの `0x3f/20` wheel commandを使用。 |
| `chassis` | `move(x, y, z, xy_speed, z_speed)` action object | `chassis.move(...)` は速度適用後に即時完了Actionを返す | 一部対応 | 真の距離/角度task actionは未対応。 |
| `chassis` | `set_pwm_value()`, `set_pwm_freq()` | 未実装 | 対象外 | EP PWM拡張。 |
| `chassis` | `stick_overlay()` | 未実装 | 未対応 | |
| `chassis` | `sub_position()` | `chassis.sub_position(...)` | 一部対応 | S1ログ由来odometry parser。公式position subjectとは別。 |
| `chassis` | `sub_attitude()` | `chassis.sub_attitude(...)` | 一部対応 | decoded odometryのheadingを利用。 |
| `chassis` | `sub_status()` | `chassis.sub_status(...)` | 一部対応 | 距離/時間/バッテリー候補など、判明済み範囲。 |
| `chassis` | `sub_imu()` | raw DUSSのみ | Raw | |
| `chassis` | `sub_mode()` | raw DUSSのみ | Raw | |
| `chassis` | `sub_esc()` | 未実装 | 未対応 | |
| `chassis` | `sub_velocity()` | `chassis.sub_velocity(...)` | 一部対応 | decoded odometryを利用。 |
| `gimbal` | `drive_speed(pitch_speed, yaw_speed)` | `gimbal.drive_speed(pitch_speed, yaw_speed)` | 一部対応 | 公式名で実装。S1 command scaleを使用。 |
| `gimbal` | `move()`, `moveto()` action object | 未実装 | 未対応 | |
| `gimbal` | `recenter()` | `gimbal.recenter()` | 一部対応 | 現状はgimbal停止。完全な回中軌道は未対応。 |
| `gimbal` | calibration系 | `gimbal.calibrate()` | 一部対応 | calibrationログの `0x04/08` gimbal auto-calibration開始コマンドを使用。 |
| `gimbal` | `suspend()`, `resume()` | `gimbal.suspend()`, `gimbal.resume()` | 一部対応 | 安全な停止/no-op。 |
| `gimbal` | `sub_angle()` | `gimbal.sub_angle(...)` | 一部対応 | S1 `0x48/08` telemetryをdecode。 |
| `gimbal` | work mode API | control sensitivityとS1 mode関連コマンド | 一部対応 | S1 App側の設定flowはEPと異なる。 |
| `camera` | `start_video_stream()`, `stop_video_stream()` | 公式名をH.264 payload queueへ接続 | 一部対応 | CV2画像decodeはSDK core未対応。 |
| `camera` | `read_video_frame()`, `read_cv2_image()` | `read_video_frame()` 実装、`read_cv2_image()` 未実装 | 一部対応 | |
| `camera` | `start_audio_stream()`, `stop_audio_stream()`, `read_audio_frame()` | 公式名をaudio payload queueへ接続 | 一部対応 | S1 Appコマンドで処理。 |
| `camera` | `record_audio()` | 未実装 | 未対応 | |
| `camera` | `take_photo()` | 未実装 | 未対応 | |
| `camera` | SD card format | `camera.format_sd_card()` | 一部対応 | format-SDログの `0x02/72 00` を使用。 |
| `camera` | `_set_zoom()` | 未実装 | 未対応 | |
| `camera` | `set_resolution()` | `camera.set_resolution("720p" / "1080p")` | 一部対応 | S1設定コマンドをログから実装。 |
| `camera` | FPS/bitrate/down-vision設定 | anti-flickerと3D qualityのみ | 一部対応 | 公式FPS/bitrate APIとは未対応。 |
| `media` | video/audio decoder/display pipeline | GUI側PyAV decoder | 一部対応 | SDK coreはraw callback、App側で表示/再生。 |
| `vision` | marker/line/robot/person/gesture detection subscribe | 未実装 | 未対応 | |
| `vision` | detection color/function control | 未実装 | 未対応 | |
| `blaster` | `fire(fire_type=WATER/INFRARED, times)` | `blaster.fire(fire_type, times)` | 一部対応 | `ir`はLED GUN、`water`は物理GUN modeに対応。 |
| `blaster` | `set_led(brightness, effect)` | `blaster.set_led(brightness, effect)` | 一部対応 | 専用blaster LED effectは未完全解析のため全体RGBへmapping。 |
| `led` | `set_led(comp, r, g, b, effect, freq)` | `led.set_led(comp, r, g, b, effect, freq)` | 一部対応 | component/effect/frequencyは受けるが全体RGB/on-offへmapping。 |
| `led` | `set_gimbal_led(...)` | `led.set_gimbal_led(...)` | 一部対応 | 全体RGB mapping。 |
| `battery` | `sub_battery_info()` | `battery.sub_battery_info(...)`, `battery.get_battery()` | 一部対応 | S1 telemetryからdecodeできた場合のみ値を出す。 |
| `armor` | `sub_hit_event()` | `armor.sub_hit_event(...)` | 対応 | LED/物理アーマーダメージをdecode。 |
| `armor` | `sub_ir_event()` | `armor.sub_ir_event(...)` | 一部対応 | IR/LED hitをdamage callbackから分離。 |
| `armor` | `set_hit_sensitivity(comp, sensitivity)` | 未実装 | 未対応 | |
| `robotic_arm` | `reset()`, `recenter()`, `move()`, `moveto()`, `sub_position()` | 未実装 | 対象外 | EP拡張モジュール。 |
| `gripper` | `open()`, `close()`, `pause()`, `sub_status()` | 未実装 | 対象外 | EP拡張モジュール。 |
| `servo` | `moveto()`, `drive_speed()`, `pause()`, `get_angle()`, `sub_servo_info()` | 未実装 | 対象外 | EP拡張機能。 |
| `sensor` | distance sensor `sub_distance()` | 未実装 | 対象外 | EP/Tello拡張経路。 |
| `sensor_adaptor` | `get_adc()`, `get_io()`, `get_pulse_period()`, `sub_adapter()` | 未実装 | 対象外 | EP拡張モジュール。 |
| `ai_module` | `init_ai_module()`, `sub_ai_event()` | 未実装 | 対象外 | EP AI module。 |
| `flight` | takeoff/land/go/rc/mission pad | 未実装 | 対象外 | Tello/drone専用。 |
| S1 pairing | EP SDK APIには含まれない | `build_wifi_qr_data()`, `make_header8_from_appid()`, `save_qr()` | 対応 | S1 Windows App pairing固有。 |
| S1 App設定 | EP SDK APIには含まれない | speed preset/custom speed、voice language、volume、auto sleep、poweroff | 一部対応 | S1 Windows Appログから復元。 |

### 注意

- `enter_solo()` を呼ぶまで操作コマンドはneutral送信中心です。
- `close()` はSolo中であれば `exit_solo()` を送ってからソケットを閉じます。
- H.264のデコード表示はSDKでは行わず、`video` callbackでH.264 payloadを渡します。
- PCマイク音声は `start_tx()` 後に `send_pcm_block()` でPCMブロックを送信します。
