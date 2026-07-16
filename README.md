# RoboMaster S1 Wireless Tools

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
python .\robomaster_s1_unified_app.py --appid b6359877 --ssid WirelessLAN --password your_password
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

## 日本語

### メインスクリプト

通常利用ではこのスクリプトを使います。

```powershell
python .\robomaster_s1_unified_app.py
```

オプション指定例:

```powershell
python .\robomaster_s1_unified_app.py --appid b6359877 --ssid WirelessLAN --password your_password
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
