"""Protocol helper functions compatible with :mod:`robomaster.algo`."""


def crc8_calc(data, crc=0x77):
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc >> 1) ^ 0x8C) if crc & 1 else crc >> 1
    return crc & 0xFF


def crc16_calc(data, crc=0x3692):
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc >> 1) ^ 0x8408) if crc & 1 else crc >> 1
    return crc & 0xFFFF


def simple_encrypt(data):
    buf = bytearray(len(data))
    key = 0x07
    for index, value in enumerate(data):
        buf[index] = (value ^ key) & 0xFF
        key = (key + 7) ^ 178
    return buf
