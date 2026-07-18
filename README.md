# RoboMaster S1 Wireless Tools

This project exists to provide a practical and legitimate control path for RoboMaster S1 where official DJI RoboMaster SDK support is unavailable. It enables S1 control through the Windows App-compatible Wi-Fi protocol without obtaining root privileges and without unauthorized reuse of EP files.

本プロジェクトは、DJI公式 RoboMaster SDK の正式対応がない RoboMaster S1 に対して、実用的かつ正当な制御手段を提供するために存在します。Windows App互換のWi-Fiプロトコルを用い、root取得やEP由来ファイルの非合法な流用を行わずにS1を制御できます。

This repository contains an experimental Python application for controlling a DJI RoboMaster S1 over the same Wi-Fi/App communication path used by the Windows App. It is not the official DJI RoboMaster SDK path.

このリポジトリは、DJI RoboMaster S1 を Windows App と同系統の Wi-Fi/App 通信で操作するための実験的な Python アプリです。DJI公式 RoboMaster SDK 経路ではありません。

## English

### Main Script

Use this script for normal operation:

```powershell
python .\robomaster_s1_unified_app.py
```

Useful options:

```powershell
python .\robomaster_s1_unified_app.py --appid b6359877 --ssid YOUR_WIFI_SSID --password YOUR_WIFI_PASSWORD
```

`robomaster_s1_unified_app.py` provides:

- QR code generation for S1 Wi-Fi pairing
- AppID claim and reconnect handling
- Connect / Disconnect
- Solo mode toggle
- H.264 camera display
- telemetry, gimbal, odometry, and status display
- chassis and gimbal controls
- GUN control
- LED color setting
- video settings
- speed settings
- voice language / volume
- microphone TX and robot audio RX
- debug communication log toggle

### Lab Mode App

Use this script when you want to run a Lab Python bridge on the robot and
control it from the host through UDP:

```powershell
python .\robomaster_s1_lab_app.py
```

Workflow:

1. Press `Search` or enter the robot IP.
2. Press `Connect`.
3. Press `Enter Lab`.
4. Press `Upload`.
5. Check that the file status shows `uploaded`, size, and MD5.
6. Press `Start`.
7. Press `Start Bridge`.
8. Use the Lab control buttons. Commands are sent while the button is held.
9. Press `Stop` to stop/leave the Lab running state.

The Lab app uploads `/python/python_raw.dsp` using the FTP path observed in Lab
captures. It also sends the observed Lab state command and the Lab start
command `0x3f/0xa2` with `md5(python_raw.dsp)`, then communicates with the
running Lab program on UDP `40923` and receives best-effort telemetry on UDP
`40924`.

### Supporting Files

These files are kept because the unified app imports them:

| File | Purpose |
|---|---|
| `robomaster_s1_unified_app.py` | Main GUI application |
| `robomaster_s1_designed_motion.py` | DUSS frame generation, outer UDP envelope, AppID broadcast parsing, command constants |
| `robomaster_s1_probe.py` | CRC and DUSS frame parsing helpers |
| `robomaster_wifi_qr_generator.py` | QR payload generation and Header8/AppID conversion |

Documentation:

| File | Purpose |
|---|---|
| `robomaster_s1_wifi_communication_spec.md` | Current communication specification |
| `robomaster_s1_all_in_one.md` | Historical analysis notes and consolidated investigation log |
| `robomaster_s1_sound_effects.md` | Notes about sound-effect related commands |
| `SDK/` | Experimental official-SDK-like Python facade built from the known S1 Wi-Fi protocol |

### Requirements

Python 3.10 or newer is recommended.

Common packages:

```powershell
pip install pillow qrcode av sounddevice
```

Notes:

- `pillow` and `qrcode` are used for QR display/generation.
- `av` is used for H.264 and Opus decoding.
- `sounddevice` is used for microphone capture and audio playback.
- Some audio/video features may be unavailable if optional packages are missing.

### Typical Workflow

1. Start the app:

   ```powershell
   python .\robomaster_s1_unified_app.py
   ```

2. Enter SSID, password, and AppID.
3. Generate and scan the QR code with the S1.
4. Press `Connect`.
5. Turn `Solo` on when operation mode is needed.
6. Use the controller, video, telemetry, audio, LED, and settings panels.

### Important Notes

- Outer UDP session, tick, DUSS sequence number, and CRC values are generated at runtime.
- The official DJI RoboMaster SDK is mainly for EP. A stock S1 does not expose the same official SDK connection path, so this project uses the Windows App compatible path.
- For an official-SDK-style coverage table based on `jeguzzi/RoboMaster-SDK`, see `SDK/README.md`.

### Official SDK Compatibility Summary

| Official SDK area | This project / SDK coverage |
|---|---|
| connection lifecycle | supported through the S1 Windows App-compatible Wi-Fi path |
| robot discovery | supported from S1 broadcast |
| chassis speed control | partially supported |
| chassis distance action | not supported |
| gimbal speed control | supported |
| gimbal angle action | not supported |
| blaster / GUN | partially supported |
| armor hit callback | supported |
| LED | partially supported |
| camera stream | partially supported with H.264 payload/display |
| camera settings | supported for known S1 settings |
| audio | partially supported |
| telemetry push | partially supported |
| vision / AI | not supported |
| EP extension modules | not applicable to stock S1 Wi-Fi path |
| QR Wi-Fi pairing | S1-specific supported |
| power off | S1-specific supported |

## 日本語

### メインスクリプト

通常利用ではこのスクリプトを使います。

```powershell
python .\robomaster_s1_unified_app.py
```

オプション指定例:

```powershell
python .\robomaster_s1_unified_app.py --appid b6359877 --ssid YOUR_WIFI_SSID --password YOUR_WIFI_PASSWORD
```

`robomaster_s1_unified_app.py` の主な機能:

- S1 Wi-Fi接続用QRコード生成
- AppID claim と再接続処理
- Connect / Disconnect
- Soloモード切替
- H.264カメラ映像表示
- telemetry / gimbal / odometry / status 表示
- シャシー操作、ジンバル操作
- GUN操作
- LED色設定
- 映像設定
- 速度設定
- 音声言語 / 音量設定
- PCマイク送信、機体音声受信
- Debug用通信ログON/OFF

### Labモード専用App

Lab Pythonブリッジを機体側で実行し、HOST側からUDPで操作する場合はこのスクリプトを使います。

```powershell
python .\robomaster_s1_lab_app.py
```

手順:

1. `Search` を押すか、Robot IPを入力します。
2. `Connect` を押します。
3. `Enter Lab` を押します。
4. `Upload` を押します。
5. ファイル状態欄に `uploaded`、サイズ、MD5が出ていることを確認します。
6. `Start` を押します。
7. `Start Bridge` を押します。
8. Lab操作ボタンを使います。ボタン押下中だけ指令を送信します。
9. `Stop` でLab実行状態を停止/退出します。

Lab専用Appは、Labログで確認したFTP経路で `/python/python_raw.dsp` をアップロードし、
Lab状態遷移コマンドと `md5(python_raw.dsp)` を含む `0x3f/0xa2` のStartコマンドも送ります。
その後、実行中のLabプログラムへUDP `40923` で操作指令を送り、UDP `40924` で
best-effort telemetryを受信します。

### 補助ファイル

以下は統合Appが import しているため残しています。

| ファイル | 役割 |
|---|---|
| `robomaster_s1_unified_app.py` | メインGUIアプリ |
| `robomaster_s1_designed_motion.py` | DUSS生成、外側UDP envelope、AppID broadcast解析、コマンド定義 |
| `robomaster_s1_probe.py` | CRCとDUSSフレーム解析の補助 |
| `robomaster_wifi_qr_generator.py` | QR payload生成、Header8/AppID変換 |

ドキュメント:

| ファイル | 役割 |
|---|---|
| `robomaster_s1_wifi_communication_spec.md` | 現行の通信仕様書 |
| `robomaster_s1_all_in_one.md` | 過去の解析履歴と統合メモ |
| `robomaster_s1_sound_effects.md` | 効果音関連コマンドのメモ |
| `SDK/` | 判明済みS1 Wi-Fiプロトコルを公式SDK風APIにまとめた実験的SDK |

### 必要ライブラリ

Python 3.10以降を推奨します。

よく使うパッケージ:

```powershell
pip install pillow qrcode av sounddevice
```

補足:

- `pillow` と `qrcode` はQR表示/生成に使います。
- `av` はH.264とOpusのデコードに使います。
- `sounddevice` はマイク入力と音声再生に使います。
- 任意ライブラリがない場合、一部の映像/音声機能は使えません。

### 基本的な使い方

1. アプリを起動します。

   ```powershell
   python .\robomaster_s1_unified_app.py
   ```

2. SSID、Password、AppIDを入力します。
3. QRコードを生成し、S1に読み取らせます。
4. `Connect` を押します。
5. 操作が必要な場合は `Solo` をONにします。
6. コントローラ、映像、テレメトリ、音声、LED、各種設定を操作します。

### 注意

- 現在の接続状態から、outer UDP session、tick、DUSS seq、CRCを生成して送信します。
- DJI公式 RoboMaster SDK は主にEP向けです。通常状態のS1では同じ公式SDK接続経路が使えないため、このプロジェクトではWindows App互換通信を使っています。
- `jeguzzi/RoboMaster-SDK` を元にした公式SDK風APIとの詳細な対応表は `SDK/README.md` を参照してください。

### 公式SDK互換性の概要

| 公式SDKの領域 | 本プロジェクト / SDKの対応 |
|---|---|
| 接続ライフサイクル | S1 Windows App互換Wi-Fi経路で対応 |
| 機体検索 | S1 broadcastから対応 |
| シャシー速度制御 | 一部対応 |
| シャシー距離移動 | 未対応 |
| ジンバル速度制御 | 対応 |
| ジンバル角度移動 | 未対応 |
| Blaster / GUN | 一部対応 |
| アーマー被弾callback | 対応 |
| LED | 一部対応 |
| カメラストリーム | H.264 payload/displayとして一部対応 |
| カメラ設定 | 判明済みS1設定に対応 |
| Audio | 一部対応 |
| Telemetry push | 一部対応 |
| Vision / AI | 未対応 |
| EP拡張モジュール | stock S1 Wi-Fi経路では対象外 |
| QR Wi-Fi pairing | S1固有機能として対応 |
| Power off | S1固有機能として対応 |
