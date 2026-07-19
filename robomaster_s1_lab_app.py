#!/usr/bin/env python3
from __future__ import annotations

import argparse
import multiprocessing as mp
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

APP_DIR = Path(__file__).resolve().parent

# Select the RoboMaster SDK implementation used by this app.
# Official SDK:
# SELECTED_SDK_DIR = Path(r"C:\path\to\dji-sdk\RoboMaster-SDK\src")
# This repository's Wi-Fi SDK:
# SELECTED_SDK_DIR = APP_DIR / "SDK"
# Lab-mode SDK:
SELECTED_SDK_DIR = APP_DIR / "LAB-SDK"

selected_sdk_path = str(SELECTED_SDK_DIR)
sys.path = [path for path in sys.path if path != selected_sdk_path]
sys.path.insert(0, selected_sdk_path)

from robomaster import blaster, robot  # noqa: E402
from robomaster_lab_sdk import gui as lab_gui  # noqa: E402

try:
    import av
except ImportError:  # pragma: no cover - optional video decoder
    av = None

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - optional GUI image display
    Image = None
    ImageTk = None

LAB_DIR = APP_DIR / "lab"
DEFAULT_DSP_NAME = lab_gui.DEFAULT_DSP_NAME


class VideoDecoder(threading.Thread):
    def __init__(self, input_queue: queue.Queue[bytes | None], output_queue: queue.Queue[object]) -> None:
        super().__init__(daemon=True)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.stop_event = threading.Event()

    def run(self) -> None:
        if av is None or Image is None:
            return
        codec = av.CodecContext.create("h264", "r")
        while not self.stop_event.is_set():
            try:
                chunk = self.input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if chunk is None:
                break
            try:
                packets = codec.parse(chunk)
                for packet in packets:
                    for frame in codec.decode(packet):
                        image = frame.to_image()
                        while True:
                            try:
                                self.output_queue.put_nowait(image)
                                break
                            except queue.Full:
                                try:
                                    self.output_queue.get_nowait()
                                except queue.Empty:
                                    break
            except Exception:
                continue


class LabApp(tk.Tk):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__()
        self.title("RoboMaster S1 Lab Bridge")
        self.geometry("1120x760")
        self.args = args
        self.robot: lab_gui.Robot | None = None
        self.bridge: lab_gui.LabBridge | None = None
        self.control_job: str | None = None
        self.current_action = None
        self.current_action_group: str | None = None
        self.last_dsp_md5: str | None = None
        self.last_lab_guid: str | None = None
        self.last_lab_sign: str | None = None
        self.last_lab_guid_marker: int | None = None
        # Keep raw H.264 buffering bounded and use the same decoded-frame
        # capacity as DJI's LiveView implementation.  _poll_video drains this
        # queue to the newest frame so a stalled UI does not replay old video.
        self.video_in: queue.Queue[bytes | None] = queue.Queue(maxsize=256)
        self.video_out: queue.Queue[object] = queue.Queue(maxsize=64)
        self.telemetry_queue: queue.Queue[object] = queue.Queue(maxsize=1)
        self.video_decoder = VideoDecoder(self.video_in, self.video_out)
        self.video_decoder.start()
        self.video_photo = None

        self.robot_ip_var = tk.StringVar(value=args.robot_ip)
        self.appid_var = tk.StringVar(value=args.appid)
        self.local_ip_var = tk.StringVar(value=args.local_ip)
        self.control_port_var = tk.IntVar(value=args.control_port)
        self.telemetry_port_var = tk.IntVar(value=args.telemetry_port)
        self.status_var = tk.StringVar(value="Idle")
        self.upload_status_var = tk.StringVar(value="File: not uploaded")
        self.video_size_var = tk.StringVar(value="Stream -")
        self.debug_var = tk.BooleanVar(value=args.debug)
        self.speed_var = tk.DoubleVar(value=0.35)
        self.yaw_var = tk.DoubleVar(value=0.35)
        self.gimbal_var = tk.DoubleVar(value=0.40)
        self.robot_mode_var = tk.StringVar(value="free")
        self.program_var = tk.StringVar(value="")

        self.telemetry_vars = {
            "seq": tk.StringVar(value="-"),
            "time_ms": tk.StringVar(value="-"),
            "x": tk.StringVar(value="-"),
            "y": tk.StringVar(value="-"),
            "yaw": tk.StringVar(value="-"),
            "vx": tk.StringVar(value="-"),
            "vy": tk.StringVar(value="-"),
            "gimbal_pitch": tk.StringVar(value="-"),
            "gimbal_yaw": tk.StringVar(value="-"),
        }

        self._build_ui()
        self.bind_all("<ButtonRelease-1>", self._end_current_command, add="+")
        self.after(15, self._poll_video)
        self.after(20, self._poll_telemetry)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.LabelFrame(self, text="Lab Bridge", padding=8)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Robot IP").grid(row=0, column=0, sticky="w")
        self.robot_ip_combo = ttk.Combobox(top, textvariable=self.robot_ip_var, width=18, values=(), state="normal")
        self.robot_ip_combo.grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(top, text="Search", command=self.search_robot).grid(row=0, column=2, padx=3)
        ttk.Label(top, text="AppID").grid(row=0, column=3, sticky="e")
        ttk.Entry(top, textvariable=self.appid_var, width=10).grid(row=0, column=4, sticky="w", padx=4)

        ttk.Label(top, text="Control UDP").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(top, from_=1024, to=65535, textvariable=self.control_port_var, width=8).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(top, text="Telemetry UDP").grid(row=1, column=2, sticky="e")
        ttk.Spinbox(top, from_=1024, to=65535, textvariable=self.telemetry_port_var, width=8).grid(row=1, column=3, sticky="w", padx=4)
        ttk.Label(top, text="Local IP").grid(row=1, column=4, sticky="e")
        ttk.Entry(top, textvariable=self.local_ip_var, width=10).grid(row=1, column=5, sticky="w", padx=4)
        ttk.Checkbutton(top, text="Debug", variable=self.debug_var).grid(row=1, column=6, padx=4)

        ttk.Label(top, text="Program").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.program_combo = ttk.Combobox(
            top,
            textvariable=self.program_var,
            values=(),
            state="readonly",
            width=22,
        )
        self.program_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=4, pady=(6, 0))
        self.program_combo.bind("<<ComboboxSelected>>", self.on_program_selected)
        ttk.Button(top, text="Refresh", command=self.refresh_programs).grid(row=2, column=3, sticky="ew", padx=3, pady=(6, 0))

        ttk.Button(top, text="Connect", command=self.connect).grid(row=3, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(top, text="Disconnect", command=self.disconnect).grid(row=3, column=1, sticky="ew", padx=3, pady=(6, 0))
        ttk.Button(top, text="Enter Lab", command=self.enter_lab).grid(row=3, column=2, sticky="ew", padx=3, pady=(6, 0))
        ttk.Button(top, text="Upload", command=self.upload_program).grid(row=3, column=3, sticky="ew", padx=3, pady=(6, 0))
        ttk.Button(top, text="Start", command=self.start_lab_program).grid(row=3, column=4, sticky="ew", padx=3, pady=(6, 0))
        ttk.Button(top, text="Stop", command=self.stop_lab_program).grid(row=3, column=5, sticky="ew", padx=3, pady=(6, 0))
        ttk.Button(top, text="Start Bridge", command=self.start_bridge).grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(top, text="Stop Bridge", command=self.stop_bridge).grid(row=4, column=1, sticky="ew", padx=3, pady=(6, 0))
        ttk.Label(top, textvariable=self.upload_status_var).grid(row=4, column=2, columnspan=5, sticky="ew", padx=6, pady=(6, 0))

        ttk.Label(top, textvariable=self.status_var).grid(row=5, column=0, columnspan=7, sticky="ew", pady=(6, 0))

        hint = ttk.Label(
            self,
            text=(
                "Steps: 1) Search or enter Robot IP  2) Connect  "
                "3) Enter Lab  4) select lab/*.dsp  5) Upload  6) Start  7) Start Bridge."
            ),
            foreground="#555555",
        )
        hint.grid(row=1, column=0, sticky="ew", padx=10)

        main = ttk.Frame(self, padding=8)
        main.grid(row=2, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=2)
        main.rowconfigure(0, weight=1)

        controls = self._build_control_panel(main)
        controls.grid(row=0, column=0, sticky="nsw", padx=(0, 8))

        telemetry = self._build_telemetry_panel(main)
        telemetry.grid(row=0, column=1, sticky="nsew")

        video = self._build_video_panel(main)
        video.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        log_panel = ttk.LabelFrame(self, text="Log", padding=8)
        log_panel.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 8))
        log_panel.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_panel, height=8)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.refresh_programs()

    def refresh_programs(self) -> None:
        LAB_DIR.mkdir(exist_ok=True)
        dsp_names = sorted(path.name for path in LAB_DIR.glob("*.dsp"))
        values = tuple(dsp_names)
        self.program_combo.configure(values=values)
        current = self.program_var.get()
        if current in values:
            return
        if DEFAULT_DSP_NAME in dsp_names:
            self.program_var.set(DEFAULT_DSP_NAME)
        elif dsp_names:
            self.program_var.set(dsp_names[0])
        else:
            self.program_var.set("")

    def on_program_selected(self, _event=None) -> None:  # noqa: ANN001
        self.last_dsp_md5 = None
        self.last_lab_guid = None
        self.last_lab_sign = None
        self.last_lab_guid_marker = None
        self.upload_status_var.set(f"File: {self.program_var.get()} not uploaded")
        self.status_var.set("Program changed. Upload before Start.")

    def _selected_is_udp_bridge(self) -> bool:
        return lab_gui.is_bridge_capable(self.program_var.get())

    def _build_control_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Operation", padding=8)
        for col in range(3):
            panel.columnconfigure(col, minsize=90)

        ttk.Label(panel, text="Move speed").grid(row=0, column=0, sticky="w")
        ttk.Scale(panel, from_=0.05, to=1.0, variable=self.speed_var, orient="horizontal").grid(row=0, column=1, columnspan=2, sticky="ew")
        ttk.Label(panel, text="Yaw speed").grid(row=1, column=0, sticky="w")
        ttk.Scale(panel, from_=0.05, to=1.0, variable=self.yaw_var, orient="horizontal").grid(row=1, column=1, columnspan=2, sticky="ew")
        ttk.Label(panel, text="Gimbal speed").grid(row=2, column=0, sticky="w")
        ttk.Scale(panel, from_=0.05, to=1.0, variable=self.gimbal_var, orient="horizontal").grid(row=2, column=1, columnspan=2, sticky="ew")

        ttk.Label(panel, text="Mode").grid(row=3, column=0, sticky="w")
        mode_frame = ttk.Frame(panel)
        mode_frame.grid(row=3, column=1, columnspan=2, sticky="ew", pady=3)
        ttk.Radiobutton(mode_frame, text="Free", variable=self.robot_mode_var, value="free", command=self.set_robot_mode).pack(side="left")
        ttk.Radiobutton(mode_frame, text="Follow", variable=self.robot_mode_var, value="gimbal_follow", command=self.set_robot_mode).pack(side="left", padx=(8, 0))

        self._command_button(panel, "Forward", 4, 1, "chassis", lambda: self.robot.chassis.drive_speed(x=self.speed_var.get()))
        self._command_button(panel, "Left", 5, 0, "chassis", lambda: self.robot.chassis.drive_speed(y=-self.speed_var.get()))
        ttk.Button(panel, text="Stop", command=self.send_stop).grid(row=5, column=1, sticky="ew", padx=3, pady=3)
        self._command_button(panel, "Right", 5, 2, "chassis", lambda: self.robot.chassis.drive_speed(y=self.speed_var.get()))
        self._command_button(panel, "Back", 6, 1, "chassis", lambda: self.robot.chassis.drive_speed(x=-self.speed_var.get()))

        self._command_button(panel, "Turn L", 7, 0, "chassis", lambda: self.robot.chassis.drive_speed(z=-self.yaw_var.get() * self.robot.config.max_chassis_yaw_speed))
        self._command_button(panel, "Turn R", 7, 2, "chassis", lambda: self.robot.chassis.drive_speed(z=self.yaw_var.get() * self.robot.config.max_chassis_yaw_speed))

        self._command_button(panel, "Gimbal Up", 8, 1, "gimbal", lambda: self.robot.gimbal.drive_speed(pitch_speed=self.gimbal_var.get() * self.robot.config.max_gimbal_speed))
        self._command_button(panel, "Gimbal Left", 9, 0, "gimbal", lambda: self.robot.gimbal.drive_speed(yaw_speed=-self.gimbal_var.get() * self.robot.config.max_gimbal_speed))
        ttk.Button(panel, text="Gimbal Stop", command=self.send_gimbal_stop).grid(row=9, column=1, sticky="ew", padx=3, pady=3)
        self._command_button(panel, "Gimbal Right", 9, 2, "gimbal", lambda: self.robot.gimbal.drive_speed(yaw_speed=self.gimbal_var.get() * self.robot.config.max_gimbal_speed))
        self._command_button(panel, "Gimbal Down", 10, 1, "gimbal", lambda: self.robot.gimbal.drive_speed(pitch_speed=-self.gimbal_var.get() * self.robot.config.max_gimbal_speed))

        ttk.Button(panel, text="LED GUN", command=lambda: self.fire("led")).grid(row=11, column=0, columnspan=1, sticky="ew", padx=3, pady=(10, 3))
        ttk.Button(panel, text="Physical GUN", command=lambda: self.fire("physical")).grid(row=11, column=1, columnspan=2, sticky="ew", padx=3, pady=(10, 3))
        return panel

    def _command_button(self, parent: ttk.Frame, text: str, row: int, column: int, group: str, command_factory) -> None:  # noqa: ANN001
        button = ttk.Button(parent, text=text)
        button.grid(row=row, column=column, sticky="ew", padx=3, pady=3)
        button.bind("<ButtonPress-1>", lambda _event: self.begin_command(group, command_factory))
        button.bind("<ButtonRelease-1>", self._end_current_command)

    def _build_telemetry_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Lab Telemetry", padding=8)
        panel.columnconfigure(1, weight=1)
        for row, (key, var) in enumerate(self.telemetry_vars.items()):
            ttk.Label(panel, text=key).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
            ttk.Label(panel, textvariable=var, anchor="e").grid(row=row, column=1, sticky="ew", pady=2)
        return panel

    def _build_video_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="H.264 Camera", padding=8)
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)
        self.video_label = ttk.Label(panel, text="No video frame decoded", anchor="center")
        self.video_label.grid(row=0, column=0, sticky="nsew")
        ttk.Label(panel, textvariable=self.video_size_var, anchor="e").grid(row=1, column=0, sticky="ew", pady=(4, 0))
        if av is None or Image is None or ImageTk is None:
            self.video_size_var.set("Install pyav and pillow to display H.264")
        return panel

    def log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def search_robot(self) -> None:
        self.status_var.set("Searching...")
        threading.Thread(target=self._search_worker, daemon=True).start()

    def _search_worker(self) -> None:
        try:
            robots = lab_gui.discover_robots(timeout=4.0)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Search", str(exc)))
            self.after(0, lambda: self.status_var.set("Search failed"))
            return
        self.after(0, lambda: self._apply_search(robots))

    def _apply_search(self, robots: list[robot.DiscoveredRobot]) -> None:
        values = tuple(robot.ip for robot in robots)
        self.robot_ip_combo.configure(values=values)
        for robot in robots:
            self.log(f"[search] {robot.ip} state={robot.state} mac={robot.mac or '-'} appid={robot.appid or '-'}")
        if values and self.robot_ip_var.get().strip() not in values:
            self.robot_ip_var.set(values[0])
        self.status_var.set(f"Found {len(values)} robot(s)" if values else "No robot found")

    def _make_bridge(self) -> lab_gui.LabBridge:
        ip = self.robot_ip_var.get().strip()
        if not ip:
            raise RuntimeError("Robot IP is empty")
        return lab_gui.LabBridge(
            robot_ip=ip,
            control_port=self.control_port_var.get(),
            telemetry_port=self.telemetry_port_var.get(),
            listen_ip=self.local_ip_var.get().strip() or "0.0.0.0",
            debug=self.debug_var.get(),
            require_session_id=self.program_var.get().strip().lower() == "robomaster_s1_lab_control_bridge.dsp",
        )

    def upload_program(self) -> None:
        if self.robot is None or not self.robot.connected:
            messagebox.showerror("Upload", "Connect to the robot before uploading the Lab program")
            return
        self.status_var.set("Uploading Lab program...")
        threading.Thread(target=self._upload_worker, daemon=True).start()

    def enter_lab(self) -> None:
        if self.robot is None or not self.robot.connected:
            messagebox.showerror("Enter Lab", "Connect to the robot before entering Lab mode")
            return
        try:
            self.robot.enter_lab()
        except Exception as exc:
            messagebox.showerror("Enter Lab", str(exc))
            self.status_var.set("Enter Lab failed")
            return
        self.status_var.set("Lab state command sent")
        self.log("[lab] enter command sent: cmd=0x3f/0x04 payload=020302")

    def _upload_worker(self) -> None:
        try:
            if self.robot is None or not self.robot.connected:
                raise RuntimeError("Connect to the robot before uploading the Lab program")
            selected_program = self.program_var.get().strip()
            result = lab_gui.upload_program(self.robot, LAB_DIR, selected_program)
            self.last_dsp_md5 = result.digest
            self.last_lab_guid = result.guid
            self.last_lab_sign = result.sign
            self.last_lab_guid_marker = result.guid_marker
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Upload", str(exc)))
            self.after(0, lambda: self.status_var.set("Upload failed"))
            return
        self.after(0, lambda: self.status_var.set("Lab program uploaded. Press Start."))
        self.after(0, lambda: self.upload_status_var.set(f"File: python_raw.dsp ({result.title}), {result.byte_count} bytes, md5={result.digest}, {result.upload_time}"))
        self.after(0, lambda: self.log(f"[upload] selected={result.selected_program} /python/python_raw.dsp title={result.title} bytes={result.byte_count} md5={result.digest} guid={result.guid} sign={result.sign} guid_marker=0x{result.guid_marker:02x}"))

    def start_lab_program(self) -> None:
        if self.robot is None or not self.robot.connected:
            messagebox.showerror("Start", "Connect to the robot before starting the Lab program")
            return
        if not self.last_dsp_md5:
            messagebox.showerror("Start", "Upload the Lab program before pressing Start")
            return
        try:
            self.robot.start_lab_program(self.last_dsp_md5)
            if self.last_lab_guid and self.last_lab_sign:
                time.sleep(0.02)
                self.robot.send_lab_metadata(self.last_lab_guid, self.last_lab_sign, 0x52)
                time.sleep(0.02)
                self.robot.send_lab_runtime_notify()
        except Exception as exc:
            messagebox.showerror("Start", str(exc))
            self.status_var.set("Start failed")
            return
        if self._selected_is_udp_bridge():
            self.status_var.set("Lab program started. Press Start Bridge.")
        else:
            self.status_var.set(f"Lab program started: {self.program_var.get()}")
        self.log(f"[lab] start command sent: selected={self.program_var.get()} cmd=0x3f/0xa2 payload=0100{self.last_dsp_md5}")

    def stop_lab_program(self) -> None:
        if self.robot is None or not self.robot.connected:
            messagebox.showerror("Stop", "Connect to the robot before stopping the Lab program")
            return
        try:
            if self.last_lab_guid and self.last_lab_sign:
                self.robot.send_lab_metadata(self.last_lab_guid, self.last_lab_sign, 0x05)
                time.sleep(0.02)
                self.robot.send_lab_runtime_notify()
                time.sleep(0.02)
            self.robot.stop_lab_program()
        except Exception as exc:
            messagebox.showerror("Stop", str(exc))
            self.status_var.set("Stop failed")
            return
        self.status_var.set("Lab program stopped")
        self.log("[lab] stop command sent: cmd=0x3f/0x04 payload=000300, cmd=0x3f/0x77 payload=010300")

    def connect(self) -> None:
        if self.robot is not None and self.robot.connected:
            return
        self.status_var.set("Connecting...")
        threading.Thread(target=self._connect_worker, daemon=True).start()

    def _connect_worker(self) -> None:
        try:
            lab_robot = lab_gui.Robot(
                appid=self.appid_var.get(),
                robot_ip=self.robot_ip_var.get().strip(),
                local_ip=self.local_ip_var.get(),
                debug=self.debug_var.get(),
            )
            lab_robot.on("video", self.on_h264)
            lab_robot.initialize(auto_lab=False)
            self.robot = lab_robot
            if lab_robot.robot_ip:
                self.robot_ip_var.set(lab_robot.robot_ip)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Connect", str(exc)))
            self.after(0, lambda: self.status_var.set("Disconnected"))
            return
        self.after(0, lambda: self.status_var.set("Connected. Open Lab in the RoboMaster App, then upload/start the Lab program."))
        self.after(0, lambda: self.log("[connect] robot connection established"))

    def disconnect(self) -> None:
        if self.robot is not None:
            try:
                self.robot.close()
            except Exception as exc:
                self.log(f"[disconnect] {exc}")
        self.robot = None
        self.status_var.set("Disconnected")

    def start_bridge(self) -> None:
        try:
            if self.robot is not None:
                try:
                    self.robot.stop_command_stream()
                except Exception as exc:
                    self.log(f"[bridge] previous command stream stop error: {exc}")
            if self.bridge is not None:
                self.bridge.close()
            self.bridge = self._make_bridge()
            self.current_action = None
            self.current_action_group = None
            if self.control_job is not None:
                self.after_cancel(self.control_job)
                self.control_job = None
            self.bridge.on_telemetry(self.queue_telemetry)
            self.bridge.start()
            if self.robot is not None:
                self.robot.bridge = self.bridge
                self.robot.chassis.stop()
                self.robot.gimbal.stop()
                self.robot.start_command_stream()
        except Exception as exc:
            messagebox.showerror("Start Bridge", str(exc))
            self.status_var.set("Bridge stopped")
            return
        self.status_var.set("Host bridge running")
        self.log(
            f"[bridge] host UDP tx -> {self.robot_ip_var.get().strip()}:{self.control_port_var.get()} "
            f"rx=0.0.0.0:{self.telemetry_port_var.get()}"
        )

    def stop_bridge(self) -> None:
        self.current_action = None
        self.current_action_group = None
        if self.control_job is not None:
            self.after_cancel(self.control_job)
            self.control_job = None
        if self.robot is not None:
            try:
                self.robot.stop_command_stream()
            except Exception as exc:
                self.log(f"[bridge] command stream stop error: {exc}")
        if self.bridge is not None:
            try:
                self.bridge.close()
            except Exception as exc:
                self.log(f"[bridge] stop error: {exc}")
        self.bridge = None
        self.status_var.set("Bridge stopped")

    def begin_command(self, group: str, action) -> None:  # noqa: ANN001
        if self.robot is None or self.bridge is None:
            return
        previous_group = self.current_action_group
        if self.control_job is not None:
            self.after_cancel(self.control_job)
            self.control_job = None
        if previous_group is not None and previous_group != group:
            self._stop_action_group(previous_group)
        self.current_action_group = group
        self.current_action = action
        self._send_current_command()

    def _send_current_command(self) -> None:
        self.control_job = None
        if self.robot is not None and self.bridge is not None and self.current_action is not None:
            try:
                self.current_action()
            except Exception as exc:
                self.log(f"[tx] {exc}")

    def _end_current_command(self, _event=None) -> None:  # noqa: ANN001
        group = self.current_action_group
        self.current_action = None
        self.current_action_group = None
        if self.control_job is not None:
            self.after_cancel(self.control_job)
            self.control_job = None
        if group is not None:
            self._stop_action_group(group)

    def _stop_action_group(self, group: str) -> None:
        if self.robot is None or self.bridge is None:
            return
        try:
            if group == "chassis":
                self.robot.chassis.stop()
            elif group == "gimbal":
                self.robot.gimbal.stop()
        except Exception as exc:
            self.log(f"[{group}-stop] {exc}")

    def send_stop(self) -> None:
        if self.current_action_group == "chassis":
            self.current_action = None
            self.current_action_group = None
            if self.control_job is not None:
                self.after_cancel(self.control_job)
                self.control_job = None
        if self.robot is not None and self.bridge is not None:
            try:
                self.robot.chassis.stop()
            except Exception as exc:
                self.log(f"[chassis-stop] {exc}")

    def send_gimbal_stop(self) -> None:
        if self.current_action_group == "gimbal":
            self.current_action = None
            self.current_action_group = None
            if self.control_job is not None:
                self.after_cancel(self.control_job)
                self.control_job = None
        if self.robot is not None and self.bridge is not None:
            try:
                self.robot.gimbal.stop()
            except Exception as exc:
                self.log(f"[gimbal-stop] {exc}")

    def set_robot_mode(self) -> None:
        if self.robot is None or self.bridge is None:
            return
        try:
            self.robot.set_robot_mode(self.robot_mode_var.get())
            self.log(f"[mode] {self.robot_mode_var.get()}")
        except Exception as exc:
            self.log(f"[mode] {exc}")

    def fire(self, gun_type: str = "physical") -> None:
        if self.robot is None or self.bridge is None:
            return
        threading.Thread(target=self._fire_worker, args=(gun_type,), daemon=True).start()

    def _fire_worker(self, gun_type: str = "physical") -> None:
        try:
            fire_type = blaster.INFRARED_FIRE if gun_type == "led" else blaster.WATER_FIRE
            self.robot.blaster.fire(fire_type=fire_type)
        except Exception as exc:
            self.after(0, lambda: self.log(f"[fire] {exc}"))

    def queue_telemetry(self, value) -> None:  # noqa: ANN001
        try:
            self.telemetry_queue.put_nowait(value)
        except queue.Full:
            try:
                self.telemetry_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.telemetry_queue.put_nowait(value)
            except queue.Full:
                pass

    def _poll_telemetry(self) -> None:
        latest = None
        while True:
            try:
                latest = self.telemetry_queue.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            self.on_telemetry(latest)
        self.after(20, self._poll_telemetry)

    def on_telemetry(self, value) -> None:  # noqa: ANN001
        values = value.values
        self.status_var.set(f"Telemetry received: seq={value.sequence}")
        for key, var in self.telemetry_vars.items():
            if key == "seq":
                var.set(str(value.sequence))
            elif key == "time_ms":
                var.set(str(value.timestamp_ms))
            else:
                item = values.get(key)
                if isinstance(item, float):
                    var.set(f"{item:.3f}")
                elif item is None:
                    var.set("-")
                else:
                    var.set(str(item))

    def on_h264(self, payload: bytes) -> None:
        try:
            self.video_in.put_nowait(payload)
        except queue.Full:
            try:
                self.video_in.get_nowait()
            except queue.Empty:
                pass
            try:
                self.video_in.put_nowait(payload)
            except queue.Full:
                pass

    def _poll_video(self) -> None:
        frame = None
        while True:
            try:
                frame = self.video_out.get_nowait()
            except queue.Empty:
                break
        if frame is not None and ImageTk is not None:
            width, height = frame.size
            self.video_size_var.set(f"Stream {width}x{height}")
            max_width = max(1, self.video_label.winfo_width() - 8)
            max_height = max(1, self.video_label.winfo_height() - 8)
            image = frame.copy()
            image.thumbnail((max_width, max_height))
            self.video_photo = ImageTk.PhotoImage(image)
            self.video_label.configure(image=self.video_photo, text="")
        self.after(15, self._poll_video)

    def on_close(self) -> None:
        self.disconnect()
        self.video_decoder.stop_event.set()
        try:
            self.video_in.put_nowait(None)
        except queue.Full:
            pass
        self.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description="RoboMaster S1 Lab-mode UDP bridge app.")
    parser.add_argument("--robot-ip", default="")
    parser.add_argument("--appid", default="b6359877")
    parser.add_argument("--local-ip", default="0.0.0.0")
    parser.add_argument("--control-port", type=int, default=lab_gui.DEFAULT_CONTROL_PORT)
    parser.add_argument("--telemetry-port", type=int, default=lab_gui.DEFAULT_TELEMETRY_PORT)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    app = LabApp(args)
    app.mainloop()
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
