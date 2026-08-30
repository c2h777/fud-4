import os
import struct
import hashlib
import zlib
import random


def _fix_dex_checksums(data: bytearray) -> bytearray:
    """
    DEX header mein 2 checksums hote hain — modify karne ke baad update ZAROORI hai.
    Offset  8:  Adler-32 checksum of bytes 12..end
    Offset 12:  SHA-1 hash of bytes 32..end
    """
    # SHA-1 of bytes[32:]
    sha1 = hashlib.sha1(bytes(data[32:])).digest()
    data[12:32] = sha1

    # Adler-32 of bytes[12:]
    adler = zlib.adler32(bytes(data[12:])) & 0xFFFFFFFF
    struct.pack_into('<I', data, 8, adler)

    return data


def _mutate_dex(data: bytearray) -> bytearray:
    if len(data) < 112:
        return data
    if data[:3] != b'dex':
        return data

    str_ids_size = struct.unpack_from('<I', data, 56)[0]
    str_ids_off  = struct.unpack_from('<I', data, 60)[0]

    modified = 0
    for i in range(min(str_ids_size, 2000)):  # max 2000 strings check karo
        pos = str_ids_off + i * 4
        if pos + 4 > len(data):
            break
        str_off = struct.unpack_from('<I', data, pos)[0]
        if str_off == 0 or str_off >= len(data):
            continue

        # ULEB128 decode
        idx, length, shift = str_off, 0, 0
        while idx < len(data):
            b = data[idx]; idx += 1
            length |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7

        if length < 5 or idx + length >= len(data):
            continue

        chunk = bytes(data[idx:idx+length])
        low   = chunk.lower()
        # Sirf debug/test strings touch karo — critical strings nahi
        if b'debug' in low or b'test' in low or b'log' in low:
            for j in range(length):
                c = data[idx+j]
                # Sirf A-Z, a-z flip karo — safe range
                if 0x41 <= c <= 0x5A:
                    data[idx+j] = c ^ 0x01  # A↔B, C↔D ...
                elif 0x61 <= c <= 0x7A:
                    data[idx+j] = c ^ 0x01
            modified += 1

    if modified:
        # Checksums update karo — MUST after any byte change
        data = _fix_dex_checksums(data)

    print(f"[✓] dex_mutator: {modified} strings mutated + checksums updated.")
    return data


def mutate_smali(decompiled_dir: str):
    for root, _, files in os.walk(decompiled_dir):
        for fname in files:
            if not fname.endswith(".dex"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath, "rb") as f:
                data = bytearray(f.read())
            data = _mutate_dex(data)
            with open(fpath, "wb") as f:
                f.write(bytes(data))
