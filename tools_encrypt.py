"""Payload encrypt helper. Bot internally use karta hai — manually chalao mat."""
from config import PAYLOAD_KEY1, PAYLOAD_KEY2, PAYLOAD_ROT


def encrypt_bytes(data: bytes) -> bytes:
    pad = 16 - (len(data) % 16)
    data = data + bytes([pad] * pad)
    out = bytearray(len(data))
    for i, b in enumerate(data):
        b ^= PAYLOAD_KEY1[i % len(PAYLOAD_KEY1)]
        b ^= PAYLOAD_KEY2[(i * 3) % len(PAYLOAD_KEY2)]
        b = ((b >> PAYLOAD_ROT) | (b << (8 - PAYLOAD_ROT))) & 0xFF
        out[i] = b
    return bytes(out)
