from __future__ import annotations


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
        return self.make_dict_key(
            self._proto_data._cmdset,
            self._proto_data._cmdid,
        )
