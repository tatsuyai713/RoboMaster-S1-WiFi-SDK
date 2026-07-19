from __future__ import annotations

from robomaster_lab_sdk.unsupported import unsupported


class MsgHandler:
    def __init__(self, proto_data=None, req_cb=None, ack_cb=None):
        self._proto_data = proto_data
        self._req_cb = req_cb
        self._ack_cb = ack_cb

    @property
    def proto_data(self):
        return self._proto_data

    @staticmethod
    def make_dict_key(cmd_set, cmd_id):
        return int(cmd_set) * 256 + int(cmd_id)

    def dict_key(self):
        if self._proto_data is None:
            return None
        return self.make_dict_key(self._proto_data._cmdset, self._proto_data._cmdid)


class Client:
    def __init__(self, host=0, index=0, connect=None):
        self._host = host
        self._index = index
        self._connection = connect

    @property
    def remote_addr(self):
        return getattr(self._connection, "target_addr", None)

    def add_handler(self, obj, name, f):
        unsupported("official EP transport client")

    def remove_handler(self, name):
        unsupported("official EP transport client")

    def initialize(self):
        unsupported("official EP transport client")

    @property
    def hostbyte(self):
        return (int(self._host) << 5) | int(self._index)

    def start(self):
        unsupported("official EP transport client")

    def stop(self):
        unsupported("official EP transport client")

    def send_msg(self, msg):
        unsupported("official EP transport client")

    def send_sync_msg(self, msg, callback=None, timeout=3.0):
        unsupported("official EP transport client")

    def resp_msg(self, msg):
        unsupported("official EP transport client")

    def send(self, data):
        unsupported("official EP transport client")

    def send_async_msg(self, msg):
        unsupported("official EP transport client")

    @property
    def is_ready(self):
        return False

    def add_msg_handler(self, handler):
        unsupported("official EP transport client")


class TextClient(Client):
    def __init__(self, conf):
        self.conf = conf
        super().__init__()

    def check_is_dds_msg(self, msg):
        unsupported("Tello text client")

    def send(self, text):
        unsupported("Tello text client")

    def send_sync_msg(self, msg, callback=None, timeout=10):
        unsupported("Tello text client")

    def send_async_msg(self, msg):
        unsupported("Tello text client")

    def send_msg(self, msg):
        unsupported("Tello text client")
