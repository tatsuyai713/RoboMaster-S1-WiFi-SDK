# RoboMaster S1 Wi-Fi SDK

DJI公式RoboMaster Python SDKのAPI形状を、RoboMaster S1のWindows App互換Wi-Fi通信へマッピングする実験的SDKです。PCからS1へ直接パケットを生成・送信します。機体内Lab Pythonは使いません。

> [!IMPORTANT]
> DJI公式SDKではなく、EP SDK transportとのwire compatibilityもありません。互換対象は主に`from robomaster import robot`から始まるPython APIの形です。

## 特徴

- S1用QR/AppID pairing
- S1 broadcastによる機体検索
- UDP `10607`のApp互換outer envelope
- DUSS frame、CRC、session、tick、sequenceの動的生成
- Solo modeのenter/keepalive/exit
- chassis、gimbal、GUN、LED制御
- H.264 raw payload、Opus音声、48 kHz mono PCM decode・WAV録音
- S1→Host音声受信とHost microphone/audio file→S1音声送信
- gimbal、odometry、status、armor telemetry callback
- S1 App固有のvideo、speed、voice、volume、auto-sleep、poweroff設定
- 公式SDK風の`robomaster` facadeとS1固有の`robomaster_s1_sdk`
- `robomaster_ros`用SOLO backend、private import互換層、公式callback tuple形状

PCAPをそのまま再生する実装ではありません。解析済みのframe/payloadを現在の接続状態に合わせて組み立てます。

## インストール

Python 3.10以降が必要です。

リポジトリから直接実行:

```bash
python -m pip install "qrcode[pil]>=7.4"
PYTHONPATH=.:SDK python SDK/examples/basic_control.py
```

Windows PowerShell:

```powershell
python -m pip install "qrcode[pil]>=7.4"
$env:PYTHONPATH = ".;.\SDK"
python .\SDK\examples\basic_control.py
```

packageとしてインストール:

```bash
python -m pip install ./SDK
```

映像表示とHost microphone送信を行うGUIのoptional dependency:

```bash
python -m pip install "./SDK[app]"
```

`LAB-SDK`も同名の`robomaster`互換packageを持つため、両SDKをinstallする場合は仮想環境を分けることを推奨します。

## ROS 2

SOLOモード直接通信では、LAB-SDKを同じ環境へinstallせず、`SDK/`を選択してbuildします。

```bash
python3 -m pip uninstall -y robomaster robomaster-s1-lab-sdk
python3 -m pip install ./SDK
colcon build --packages-select robomaster_msgs robomaster_description robomaster_ros
source install/setup.bash
RM_ROBOT_IP=192.168.23.149 RM_APPID=b6359877 \
  ros2 launch robomaster_ros s1_solo.launch
```

`s1_solo.launch`は`SDK/`のAppID claimとSOLO enter sequenceを実行します。ROSの対応対象は
chassis速度/wheel、gimbal速度、odometry/gimbal telemetry、battery、armor hit、camera、
Opus/PCM audio・音量topic、
LED、blasterです。公式private heartbeatには接続せず、直接SDK自身の受信loopとSOLO keepaliveを使用します。

未解析のchassis距離Action、gimbal角度/recenter Action、IMU、ESC、chassis status、speaker、
EP拡張hardwareは無効または明示的な失敗となります。

## 最小例

```python
from robomaster import blaster, robot

s1_robot = robot.Robot(
    appid="b6359877",
    robot_ip="",       # 空ならbroadcast/claimから解決
    local_ip="0.0.0.0",
)
s1_robot.initialize(conn_type="sta", proto_type="udp", enter_solo=True)

try:
    s1_robot.chassis.drive_speed(x=0.3, y=0.0, z=0.0)
    s1_robot.gimbal.drive_speed(pitch_speed=0.0, yaw_speed=20.0)
    s1_robot.blaster.fire(fire_type=blaster.INFRARED_FIRE, times=1)
finally:
    s1_robot.chassis.stop()
    s1_robot.gimbal.stop()
    s1_robot.close()
```

`initialize()`の`conn_type`、`proto_type`、`sn`は公式SDK風のsignature互換用です。transportはS1 App互換UDPに固定され、SN指定接続は実装されていません。

`enter_solo=False`がdefaultです。制御を始める前に`enter_solo()`を呼ぶか、上の例のように`initialize(..., enter_solo=True)`を指定してください。

## S1固有API

### 機体検索

```python
from robomaster_s1_sdk import discover_robots

for item in discover_robots(timeout=4.0):
    print(item.ip, item.appid, item.state)
```

これは公式EP SDKのscan/SN discoveryではなく、S1 App用broadcastを監視します。

### Wi-Fi QR

```python
from robomaster_s1_sdk import build_wifi_qr_data, save_qr

qr = build_wifi_qr_data("YOUR_SSID", "YOUR_PASSWORD", "b6359877")
save_qr(qr.qr_text, "robomaster_wifi.png")
print(qr.header8)
```

### context manager

```python
from robomaster_s1_sdk import Robot

with Robot(appid="b6359877") as s1:
    s1.enter_solo()
    try:
        s1.chassis.forward()
    finally:
        s1.chassis.stop()
```

## APIリファレンス

### `Robot`

| API | 状態 | 実際の挙動 |
|---|---:|---|
| `initialize(conn_type, proto_type, sn, enter_solo, timeout)` | 部分対応 | AppID claim、control session、receive loop開始 |
| `close()` | 対応 | Solo退出、thread/socket終了 |
| `enter_solo()` / `exit_solo()` | S1固有 | App互換state sequenceを送信 |
| `set_robot_mode(mode)` | 部分対応 | free/lead系はSolo、idle/off系はSolo退出へ集約 |
| `get_robot_mode()` | 部分対応 | `free`または`idle`のみ |
| `get_battery()` | 部分対応 | 最後にdecodeした値。未取得時`None` |
| `get_version()` | 未対応 | `NotImplementedError` |
| `get_sn()` | 未対応 | 現在は空文字 |
| `play_sound()` | 未対応 | Unifiedに対応する実機commandがないため`NotImplementedError` |
| `play_audio(filename)` | 対応 | Hostでdecodeし、Unifiedと同じ48 kHz mono PCM経路でS1へ実時間送信するAction |
| `poweroff()` | S1固有 | Appで観測したpoweroff sequence後に接続を閉じる |
| `on(event, callback)` | S1固有 | raw/decoded event callback登録 |

### Chassis

| API | 状態 | 備考 |
|---|---:|---|
| `drive_speed(x, y, z, timeout=None)` | 対応 | 50 Hz control state。`z`をS1 scaleへ変換 |
| `drive_wheels(w1, w2, w3, w4)` | 部分対応 | `0x3f/0x20`、各値を`-1000..1000`へclamp |
| `move(x, y, z, xy_speed, z_speed)` | 未対応 | 距離を速度として誤適用せず`NotImplementedError` |
| `stop()` | 対応 | neutral control payload |
| `forward/backward/left/right()` | S1 helper | 定義済みcontrol actionを保持 |
| `sub_position/velocity/attitude/status()` | 部分対応 | S1由来telemetry parser。`freq`は送信周期を変更しない |
| `start_calibration()` | S1固有 | capture由来`0x03/0xf9 ...03` |
| `enter_calibration_measurement()` | S1固有 | capture由来`0x03/0xf9 ...01` |

`drive_speed()`は新しい速度指令、timeout、または`stop()`まで継続し得ます。公式SDKのdistance actionと混同しないでください。

### Gimbal

| API | 状態 | 備考 |
|---|---:|---|
| `drive_speed(pitch_speed, yaw_speed)` | 対応 | 公式SDKのdegree/s入力をS1正規化値へ変換し、50 Hzで継続送信 |
| `move()` / `moveto()` | 未対応 | `NotImplementedError` |
| `recenter()` | 未対応 | `NotImplementedError` |
| `suspend()` / `resume()` | 未対応 | 成功を装わず`NotImplementedError` |
| `calibrate()` | S1固有 | capture由来`0x04/0x08` |
| `sub_angle()` | 部分対応 | `0x48/0x08` payloadのraw-like tuple |
| `set_control_sensitivity()` | S1固有 | direction helperのscale設定 |

### Blaster / LED

| API | 状態 | 備考 |
|---|---:|---|
| `blaster.fire("ir", times)` | 対応 | LED GUN pulse |
| `blaster.fire("water", times)` | 部分対応 | 物理GUN mode。実機安全を確認 |
| `blaster.set_type("led"/"physical")` | S1固有 | 次回発射type |
| `blaster.set_led(brightness, effect)` | 部分対応 | 専用blaster LEDではなくglobal RGBへmapping |
| `led.set_led(comp, r, g, b, effect, freq)` | 部分対応 | comp/effect/freqはglobal RGB/on-offへ縮退 |
| `led.set_gimbal_led(...)` | 部分対応 | 同じglobal RGB mapping |

### Camera / Audio

| API | 状態 | 備考 |
|---|---:|---|
| `camera.start_video_stream(resolution=...)` | 部分対応 | 解像度設定。受信loop自体はbase connectionが管理 |
| `camera.read_video_frame()` | 対応 | decode前のH.264 payload bytes |
| `camera.stop_video_stream()` | placeholder | `True`を返すのみ |
| `camera.read_cv2_image()` | 未対応 | app側decodeを使用 |
| `camera.start_audio_stream()` | 対応 | robot audio RX request、Opus受信開始 |
| `camera.read_audio_opus()` | S1固有 | decode前のOpus packet |
| `camera.read_audio_frame()` | 対応 | 48 kHz mono signed-16 PCM |
| `camera.stop_audio_stream()` | 部分対応 | Host側stream停止。実機の独立したRX停止commandはUnifiedにも存在しない |
| `camera.record_audio()` | 対応 | decodeしたPCMをmono WAVへ保存 |
| `camera.take_photo()` | 未対応 | Unifiedにも実機撮影commandがない |
| `camera.format_sd_card()` | S1固有 | capture由来command。データ消去に注意 |
| `set_resolution/antiflicker/3d_quality()` | S1固有 | App captureから判明した設定 |
| `audio.start_tx/stop_tx/send_pcm_block()` | S1固有 | Unifiedと同じPC→S1 PCM transport |
| `audio.start_microphone()/stop_microphone()` | S1固有 | callbackをblockしない有界queueでHost microphoneを送信 |
| `audio.play_file()` | S1固有 | PyAVで48 kHz mono PCMへ変換し実時間送信 |

### Battery / Armor / Telemetry

| API | 状態 | 備考 |
|---|---:|---|
| `battery.get_battery()` | 部分対応 | 最後のstats値または`None` |
| `battery.sub_battery_info()` | 部分対応 | decodeできた場合のみcallback |
| `armor.sub_hit_event()` | 対応 | S1 armor damage event |
| `armor.sub_ir_event()` | 部分対応 | unified damage eventからIRを抽出 |
| `armor.set_hit_sensitivity()` | 未対応 | `NotImplementedError` |
| `unsub_*()` | 対応 | 対応する登録済みcallbackを削除 |

## Unified経路との再監査

`robomaster_s1_unified_app.py`で実機処理が存在する機能を、SOLO SDK経路と再比較しています。

| Unifiedの実機経路 | SOLO SDK | 状態 |
|---|---|---:|
| AppID claim、SOLO enter/exit/keepalive | `Robot.initialize/enter_solo/exit_solo` | 対応 |
| chassis/gimbal保持制御 | component速度API、50 Hz state送信 | 対応 |
| GUN、LED | `blaster`、`led` | 対応/部分対応 |
| video resolution/anti-flicker/3D | `camera`/`settings` | 対応 |
| voice language、volume、speed、auto sleep、poweroff | `settings` | 対応 |
| gimbal/chassis calibration | componentのS1固有API | 対応 |
| odometry/gimbal/stats/armor decode | subscription callback | 対応/部分対応 |
| S1→Host Opus、decode、PCM再生元 | `camera.read_audio_opus/read_audio_frame` | 対応 |
| Host microphone→S1 | `audio.start_microphone/stop_microphone` | 対応 |
| Host audio file→S1 | `Robot.play_audio` / `audio.play_file` | 対応 |

現在「未対応」としているdistance Action、gimbal角度/recenter、armor感度、実機写真撮影、
firmware/SN queryには、Unified側にも対応する検証済み実機処理がありません。
単独アプリに実装済みなのにSDK経路だけ欠落している項目を未対応表へ混在させないことを、
audio command、media queue、API、独立package importの回帰テストで検査します。

low-level event:

```python
s1_robot.on("gimbal", print)
s1_robot.on("odometry", print)
s1_robot.on("stats", print)
s1_robot.on("armor_damage", print)
s1_robot.on("video", lambda payload: print(len(payload)))
s1_robot.on("audio_rx", lambda payload: print(len(payload)))
s1_robot.on("duss", print)
```

### Settings

S1固有の`robot.settings`:

- `set_speed_preset("slow" | "medium" | "fast" | "custom")`
- `set_custom_speed(**values)`
- `set_max_speed(forward, backward, lateral)`
- `set_acceleration(starting, braking, lateral_starting, lateral_braking)`
- `set_voice_language(...)` / `set_voice_language_id(...)`
- `set_volume(0..80)`
- `set_auto_sleep(enabled, seconds)` / `query_auto_sleep()`
- `poweroff()`

これらは公式EP SDK APIではなく、S1 App trafficから復元したcommandです。query系のresponseをhigh-level objectとして返す実装はありません。

## DJI公式SDKとの比較

比較元はDJI公式[`dji-sdk/RoboMaster-SDK`](https://github.com/dji-sdk/RoboMaster-SDK)です。

| 公式module/feature | 本SDK | 判定 |
|---|---|---:|
| `robot.Robot`, lifecycle, mode | App互換connectionとして実装 | 部分対応 |
| chassis speed/wheels | 実装 | 対応/部分対応 |
| chassis distance action | 真のdistance/action trackingなし | 未対応 |
| chassis PWM、IMU、ESC、mode subject | high-level APIなし | 未対応 |
| gimbal speed | 実装 | 対応 |
| gimbal angle action | 未実装 | 未対応 |
| camera video/audio | H.264、Opus、48 kHz PCM、WAV録音 | 対応/部分対応 |
| vision detection | なし | 未対応 |
| blaster / LED | S1 commandへ縮退mapping | 部分対応 |
| battery / armor | decodeできるS1 telemetryのみ | 部分対応 |
| robotic arm / gripper / servo / sensor adaptor / UART | stock S1対象外 | 対象外 |
| AI module | stock S1対象外 | 対象外 |
| `Drone`, flight, Tello LED | 地上機S1の対象外 | 対象外 |
| Action state object | 即時command向けstate/wait/abort形状 | 部分対応 |
| Action dispatcher / async completion | 実機progress pushなし | 未対応 |

`NotImplementedError`、`False`、`None`、即時完了Actionは意味が異なります。移植時は「methodがimportできる」ことを「実機機能が対応している」ことと見なさないでください。

## 内部構成

| ファイル | 役割 |
|---|---|
| `robomaster/` | DJI公式風のimport facade、定数 |
| `robomaster_s1_sdk/robot.py` | AppID claim、session、thread、component集約 |
| `protocol.py` | 公開するUDP/DUSS helperとtelemetry decode |
| `transport.py`, `probe.py` | SDK内部のouter envelope、CRC、DUSS、SOLO payload実装 |
| `discovery.py` | S1 broadcast discovery |
| `qr.py` | QR/AppID/Header8 |
| `chassis.py`, `gimbal.py`, `blaster.py`, `led.py` | motion/actuator API |
| `camera.py`, `audio.py` | bounded media queue、Opus/PCM、録音、双方向audio session |
| `armor.py`, `battery.py` | event/telemetry facade |
| `settings.py` | S1 App固有settings |
| `examples/basic_control.py` | 最小操作例 |

## 既知の制約

- 対応firmwareを固定・自動判定していません。
- `conn_type`/`proto_type`は公式signature互換であり、TCP/AP/RNDISを実装するものではありません。
- H.264 image decodeはGUI/ROS側です。Opus audioはSDK coreで48 kHz mono signed-16 PCMへdecodeします。
- Action objectは公式形状のstate/wait/abortを持ちますが、実機progress/result pushは取得しません。
- callback exceptionは捕捉してdebug logへ記録します。callback自体の再試行はしません。
- 実機検証なしのpacket推測は送信しない方針ですが、capture由来commandにもfirmware差の可能性があります。

## English summary

This package provides an official-SDK-shaped Python facade over the stock S1 Windows App-compatible Wi-Fi path. It dynamically builds App/DUSS traffic; it does not use the official EP transport or replay complete captures. S1 audio includes Opus reception, 48 kHz mono PCM decoding, WAV recording, Host microphone transmission, and real-time audio-file streaming. Install with `python -m pip install ./SDK`, call `initialize(..., enter_solo=True)`, and always stop motion in `finally`.

The compatibility baseline is DJI's official `dji-sdk/RoboMaster-SDK` at commit `ff6646e115ab125af3207a4ed3df42cc76c795b2`, inspected on 2026-07-19.
