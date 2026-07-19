import time


def rm_import(module):
    builtins = rm_log.__dict__.get("__builtins__")
    if isinstance(builtins, dict):
        real_import = builtins["__import__"]
    else:
        real_import = builtins.__import__
    return real_import(module, globals(), locals(), [], 0)


def _start_udp_echo():
    socket = rm_import("socket")
    select = rm_import("select")
    json = rm_import("json")

    command_port = 40923
    telemetry_port = 40924

    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.bind(("0.0.0.0", command_port))
    rx.setblocking(False)

    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    last_source = None
    sequence = 0
    print("udp echo ready", command_port, telemetry_port)

    try:
        while True:
            readable, _, _ = select.select([rx], [], [], 0.02)
            if rx in readable:
                data, source = rx.recvfrom(2048)
                last_source = source
                print("udp rx", len(data), source)
                try:
                    message = json.loads(data.decode("utf-8"))
                except Exception:
                    message = {"raw_len": len(data)}
                reply = {
                    "type": "udp_echo",
                    "sequence": sequence,
                    "time_ms": int(time.time() * 1000),
                    "source_port": source[1],
                    "message": message,
                }
                tx.sendto(json.dumps(reply, separators=(",", ":")).encode("utf-8"), (source[0], telemetry_port))
                sequence += 1
            elif last_source is not None:
                reply = {
                    "type": "udp_alive",
                    "sequence": sequence,
                    "time_ms": int(time.time() * 1000),
                }
                tx.sendto(json.dumps(reply, separators=(",", ":")).encode("utf-8"), (last_source[0], telemetry_port))
                sequence += 1
            time.sleep(0.02)
    finally:
        rx.close()
        tx.close()


def start():
    try:
        _start_udp_echo()
    except Exception as exc:
        print("udp echo fatal:", str(exc))
        while True:
            time.sleep(1.0)
