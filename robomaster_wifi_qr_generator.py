#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboMaster S1系と思われる独自Wi-Fi QR Generator（解析ベース・簡略版）

確認済み構造:
  payload = length_header(2)
          + header8(8)              # AppID ASCII 8byte XOR HEADER8_APPID_MASK
          + magic(2)                # ca 6c
          + xor((SSID + PASSWORD).encode("utf-8"), keystream)

確認済み:
  - AppID は header8 に固定XORマスクで含まれる
  - SSID=WirelessLAN の長さヘッダは本スクリプトの auto で一致
  - SSID/Password本文は固定XORキーストリームで難読化
  - header8 はQRサンプルの header[2:10] に入る8byte値
  - Tatsuya’s iPhone / tatsuya713 -> len-header = 95be

重要:
  iPhoneのテザリングSSIDは、見た目が apostrophe でも
    Tatsuya's iPhone   ASCII apostrophe U+0027
    Tatsuya’s iPhone   right single quote U+2019
  の2種類があり得ます。これは別SSIDです。

依存:
  pip install qrcode[pil]

例:
  python robomaster_wifi_qr_generator.py \
      --ssid WirelessLAN \
      --password tatsuya713 \
      --header8 10f35abc0ea04800 \
      --out qr.png
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path
import secrets
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import qrcode
except ImportError:
    qrcode = None

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None


# これまでのサンプルから逆算できているキーストリーム。
# 先頭 11byte: "WirelessLAN" 用
# その後: password/長いSSID用として確認済み範囲
KEYSTREAM = bytes.fromhex(
    "9b 10 a5 1e 97 2c 81 3a f3 48 fd "
    "b6 0f a4 19 92 2b 80 35 8e 27 "
    "9c 11 aa 03 b8 0d a6"
)

MAGIC = bytes.fromhex("ca6c")
HEADER8_APPID_MASK = bytes.fromhex("71ca63d86dc67f34")
DEFAULT_BOX_SIZE = 12
DEFAULT_BORDER = 4


def utf8_continuation_count(data: bytes) -> int:
    """UTF-8 continuation byte: 10xxxxxx, i.e. 0x80..0xbf."""
    return sum(1 for byte in data if (byte & 0xC0) == 0x80)


def calc_ssid_length_field(ssid_bytes: bytes) -> int:
    """
    HeaderのSSID長フィールド相当を推定。

    ASCIIのみなら len(ssid_bytes) + 1。
    U+2019 を含む既知QRでは UTF-8 continuation byte 数も加算すると一致する。
    """
    return len(ssid_bytes) + utf8_continuation_count(ssid_bytes) + 1


def calc_length_header_auto(ssid_bytes: bytes, password_bytes: bytes) -> bytes:
    """
    解析で確認できた長さヘッダの推定式。

    WirelessLAN では以下と一致:
      pass len 1  -> 4c bc
      pass len 2  -> 8c bc
      pass len 5  -> 4c bd
      pass len 10 -> 8c be

    Tatsuya’s iPhone では以下と一致:
      pass len 10 -> 95 be

    little-endian 16bit:
      value = 0xbc00 + ssid_length_field + 0x40 * Password長
    """
    value = 0xBC00 + calc_ssid_length_field(ssid_bytes) + (len(password_bytes) << 6)
    return value.to_bytes(2, "little")


def xor_body(ssid: str, password: str) -> bytes:
    plain = (ssid + password).encode("utf-8")
    if len(plain) > len(KEYSTREAM):
        raise ValueError(
            f"SSID+Password が {len(plain)} bytes ありますが、"
            f"現在確認済みのキーストリームは {len(KEYSTREAM)} bytes までです。"
            "長いSSID/Password用のサンプルを追加して KEYSTREAM を拡張してください。"
        )
    return bytes(p ^ k for p, k in zip(plain, KEYSTREAM))


def normalize_header8_hex(header8_hex: str) -> str:
    value = header8_hex.strip().lower().replace(" ", "").replace("-", "")
    if value.startswith("0x"):
        value = value[2:]
    if len(value) != 16:
        raise ValueError("header8 は 8 bytes = 16桁hex で入力してください。例: 10f35abc0ea04800")
    bytes.fromhex(value)
    return value


def make_header8_from_appid(appid: str) -> str:
    value = appid.strip().lower()
    if len(value) != 8 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("AppID は8桁hex文字で指定してください。例: a2be7ce8")
    appid_bytes = value.encode("ascii")
    return bytes(a ^ b for a, b in zip(appid_bytes, HEADER8_APPID_MASK)).hex()


def decode_appid_from_header8(header8_hex: str) -> str:
    header8 = bytes.fromhex(normalize_header8_hex(header8_hex))
    appid_bytes = bytes(a ^ b for a, b in zip(header8, HEADER8_APPID_MASK))
    if len(appid_bytes) == 8 and all(byte in b"0123456789abcdef" for byte in appid_bytes):
        return appid_bytes.decode("ascii")
    return f"non-hex:{appid_bytes.hex()}"


def make_payload(
    ssid: str,
    password: str,
    header8_hex: str,
) -> bytes:
    ssid_bytes = ssid.encode("utf-8")
    password_bytes = password.encode("utf-8")

    header8 = bytes.fromhex(normalize_header8_hex(header8_hex))
    len_header = calc_length_header_auto(ssid_bytes, password_bytes)

    return len_header + header8 + MAGIC + xor_body(ssid, password)


def payload_to_qr_text(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def make_qr_image(text: str, box_size: int = 16, border: int = 4):
    if qrcode is None:
        raise RuntimeError("qrcode がありません。PNG生成には `pip install qrcode[pil]` が必要です。")
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def save_qr(text: str, out: Path, box_size: int = 16, border: int = 4) -> None:
    img = make_qr_image(text, box_size=box_size, border=border)
    img.save(out)


def build_debug_text(ssid: str, password: str, payload: bytes) -> str:
    ssid_bytes = ssid.encode("utf-8")
    password_bytes = password.encode("utf-8")
    plain = (ssid + password).encode("utf-8")
    warnings = []

    if "'" in ssid:
        warnings.append("SSIDに ASCII apostrophe U+0027 が入っています。iPhone名が Tatsuya’s iPhone の場合は U+2019 にしてください。")
    if "’" in ssid:
        warnings.append("SSIDに right single quote U+2019 が入っています。UTF-8: e2 80 99")

    lines = [
        f"SSID chars        : {len(ssid)}",
        f"SSID utf8 bytes   : {len(ssid_bytes)}",
        f"SSID utf8 hex     : {ssid_bytes.hex()}",
        f"SSID cont bytes   : {utf8_continuation_count(ssid_bytes)}",
        f"SSID length field : {calc_ssid_length_field(ssid_bytes)}",
        f"PASS utf8 bytes   : {len(password_bytes)}",
        f"len-header        : {payload[:2].hex()}",
        f"Header8           : {payload[2:10].hex()}",
        f"Magic             : {payload[10:12].hex()}",
        f"Plain hex         : {plain.hex()}",
    ]
    lines.extend(f"WARNING           : {warning}" for warning in warnings)
    return "\n".join(lines)


class WifiQrGeneratorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("RoboMaster S1 Wi-Fi QR Generator")
        self.geometry("1040x760")
        self.minsize(920, 680)

        self.qr_text = ""
        self.qr_image = None
        self.qr_photo = None

        self.ssid_var = tk.StringVar(value="WirelessLAN")
        self.password_var = tk.StringVar()
        self.header8_var = tk.StringVar(value=make_header8_from_appid("a2be7ce8"))
        self.appid_display_var = tk.StringVar(value=decode_appid_from_header8(self.header8_var.get()))
        self.len_header_display_var = tk.StringVar()
        self.status_var = tk.StringVar(value="SSID、Password、Header8 を入力して生成してください。")

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        form = ttk.LabelFrame(root, text="Wi-Fi QR Parameters", padding=12)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        preview = ttk.LabelFrame(root, text="QR Preview", padding=12)
        preview.grid(row=0, column=1, sticky="nsew")
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(0, weight=1)

        self._entry(form, 0, "SSID", self.ssid_var)
        self._entry(form, 1, "Password", self.password_var, show="*")
        self._header8_entry(form, 2)

        ttk.Label(form, text="QR AppID").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(
            form,
            textvariable=self.appid_display_var,
            width=34,
            state="readonly",
        ).grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="len-header").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(
            form,
            textvariable=self.len_header_display_var,
            width=34,
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="len-header は自動計算されます。").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        buttons = ttk.Frame(form)
        buttons.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(14, 8))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Generate", command=self.generate).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(buttons, text="Save PNG", command=self.save_png).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

        ttk.Button(form, text="Copy QR Text", command=self.copy_qr_text).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(0, 12)
        )

        ttk.Label(form, text="Debug").grid(row=8, column=0, columnspan=2, sticky="w")
        self.debug_text = tk.Text(form, height=10, width=48, wrap="word")
        self.debug_text.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        ttk.Label(form, text="Payload hex").grid(row=10, column=0, columnspan=2, sticky="w")
        self.payload_text = tk.Text(form, height=4, width=48, wrap="word")
        self.payload_text.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        ttk.Label(form, text="QR text").grid(row=12, column=0, columnspan=2, sticky="w")
        self.qr_text_box = tk.Text(form, height=4, width=48, wrap="word")
        self.qr_text_box.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(2, 0))

        self.preview_label = ttk.Label(preview, anchor="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew")

        status = ttk.Label(root, textvariable=self.status_var, anchor="w")
        status.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def _entry(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        show: str | None = None,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable, show=show, width=34).grid(
            row=row, column=1, sticky="ew", pady=4
        )

    def _header8_entry(self, parent: ttk.Frame, row: int) -> None:
        ttk.Label(parent, text="Header8 hex").grid(row=row, column=0, sticky="w", pady=4)

        header8_frame = ttk.Frame(parent)
        header8_frame.grid(row=row, column=1, sticky="ew", pady=4)
        header8_frame.columnconfigure(0, weight=1)

        ttk.Entry(
            header8_frame,
            textvariable=self.header8_var,
            width=22,
            state="readonly",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            header8_frame,
            text="Generate",
            command=self.generate_header8,
        ).grid(row=0, column=1)

    def generate_header8(self) -> None:
        appid = secrets.token_hex(4)
        self.header8_var.set(make_header8_from_appid(appid))
        self.appid_display_var.set(appid)
        self.status_var.set(f"Header8 を AppID {appid} 用に生成しました。")

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def generate(self) -> None:
        try:
            ssid = self.ssid_var.get()
            password = self.password_var.get()
            payload = make_payload(
                ssid=ssid,
                password=password,
                header8_hex=self.header8_var.get(),
            )
            self.appid_display_var.set(decode_appid_from_header8(self.header8_var.get()))
            self.qr_text = payload_to_qr_text(payload)
            self.qr_image = make_qr_image(
                self.qr_text,
                box_size=DEFAULT_BOX_SIZE,
                border=DEFAULT_BORDER,
            )
        except Exception as exc:
            self.status_var.set("生成に失敗しました。入力値を確認してください。")
            messagebox.showerror("Generate failed", str(exc))
            return

        self.len_header_display_var.set(payload[:2].hex())
        self._set_text(self.debug_text, build_debug_text(ssid, password, payload))
        self._set_text(self.payload_text, payload.hex())
        self._set_text(self.qr_text_box, self.qr_text)

        if ImageTk is None:
            self.preview_label.configure(text="Pillow ImageTk がないためプレビューできません。PNG保存は可能です。")
        else:
            preview_image = self.qr_image.copy()
            preview_image.thumbnail((560, 560))
            self.qr_photo = ImageTk.PhotoImage(preview_image)
            self.preview_label.configure(image=self.qr_photo, text="")

        length_header = payload[:2].hex()
        self.status_var.set(
            f"生成完了: payload={len(payload)} bytes, len-header={length_header}, QR text={len(self.qr_text)} chars"
        )

    def save_png(self) -> None:
        if not self.qr_text:
            self.generate()
            if not self.qr_text:
                return

        filename = filedialog.asksaveasfilename(
            title="Save QR PNG",
            defaultextension=".png",
            initialfile="wifi_qr.png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")],
        )
        if not filename:
            return

        try:
            save_qr(
                self.qr_text,
                Path(filename),
                box_size=DEFAULT_BOX_SIZE,
                border=DEFAULT_BORDER,
            )
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return

        self.status_var.set(f"保存しました: {filename}")

    def copy_qr_text(self) -> None:
        if not self.qr_text:
            self.generate()
            if not self.qr_text:
                return
        self.clipboard_clear()
        self.clipboard_append(self.qr_text)
        self.status_var.set("QR text をクリップボードへコピーしました。")


def run_cli() -> None:
    parser = argparse.ArgumentParser(
        description="独自Wi-Fi設定QR Generator（解析ベース・簡略版）"
    )
    parser.add_argument("--ssid", required=True, help="SSID。例: WirelessLAN / Tatsuya’s iPhone")
    parser.add_argument("--password", required=True, help="Wi-Fi password。例: tatsuya713")
    parser.add_argument(
        "--header8",
        required=True,
        help=(
            "QRの header[2:10] に入る8byte値をhexで指定。"
            "例: 10f35abc0ea04800。AppIDではない。"
        ),
    )
    parser.add_argument("--out", default="wifi_qr.png", help="出力PNGファイル")
    parser.add_argument("--print-only", action="store_true", help="PNGを作らずQR文字列だけ表示")

    args = parser.parse_args()

    payload = make_payload(
        ssid=args.ssid,
        password=args.password,
        header8_hex=args.header8,
    )
    qr_text = payload_to_qr_text(payload)

    print(build_debug_text(args.ssid, args.password, payload))
    print("payload hex :", payload.hex())
    print("QR text     :", qr_text)

    if not args.print_only:
        if qrcode is None:
            raise SystemExit("qrcode がありません。先に `pip install qrcode[pil]` を実行してください。")
        out = Path(args.out)
        save_qr(qr_text, out, box_size=DEFAULT_BOX_SIZE, border=DEFAULT_BORDER)
        print("saved       :", out)


def main() -> None:
    if len(sys.argv) == 1:
        app = WifiQrGeneratorApp()
        app.mainloop()
    else:
        run_cli()


if __name__ == "__main__":
    main()
