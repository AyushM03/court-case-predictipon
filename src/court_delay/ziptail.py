"""Minimal streaming zip reader that also handles Dropbox's zips.

Dropbox writes *stored* (uncompressed) members with a data descriptor and a zero size in the
local header, so the member length is unknown until its end. Off-the-shelf stream readers refuse
these. Here we find the end by scanning for the descriptor signature and accepting it only when
the CRC-32 and size of the bytes read so far match the descriptor.
"""
import struct
import zlib
from collections.abc import Iterable, Iterator

LOCAL = b"PK\x03\x04"
CENTRAL = b"PK\x01\x02"
DESC = b"PK\x07\x08"


class _Buf:
    def __init__(self, chunks: Iterable[bytes]):
        self.it = iter(chunks)
        self.buf = bytearray()

    def fill(self, n: int) -> bool:
        while len(self.buf) < n:
            try:
                self.buf += next(self.it)
            except StopIteration:
                return False
        return True

    def take(self, n: int) -> bytes:
        if not self.fill(n):
            raise EOFError("truncated zip stream")
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    def more(self) -> bool:
        try:
            self.buf += next(self.it)
            return True
        except StopIteration:
            return False


def _zip64_sizes(extra: bytes) -> tuple[int, int] | None:
    i = 0
    while i + 4 <= len(extra):
        hid, size = struct.unpack("<HH", extra[i:i + 4])
        if hid == 1 and size >= 16:
            return struct.unpack("<QQ", extra[i + 4:i + 20])
        i += 4 + size
    return None


def _stored_with_descriptor(b: _Buf, zip64: bool) -> Iterator[bytes]:
    crc, count, start = 0, 0, 0
    while True:
        p = b.buf.find(DESC, start)
        if p < 0:
            # Emit all but the last 3 bytes (a signature may straddle chunks).
            keep = 3
            if len(b.buf) > keep:
                data = bytes(b.buf[:-keep])
                del b.buf[:-keep]
                crc, count = zlib.crc32(data, crc), count + len(data)
                yield data
            start = 0
            if not b.more():
                raise EOFError("no data descriptor found for stored member")
            continue
        b.fill(p + 24)
        cand_crc = zlib.crc32(b.buf[:p], crc)
        n = count + p
        d_crc, s32 = struct.unpack("<II", b.buf[p + 4:p + 12])
        if d_crc == cand_crc:
            # Descriptor sizes are 8 bytes when the local header carried a zip64 extra field.
            if zip64:
                ok = len(b.buf) >= p + 16 and struct.unpack("<Q", b.buf[p + 8:p + 16])[0] == n
            else:
                ok = s32 == (n & 0xFFFFFFFF)
            desc_len = 24 if zip64 else 16
            if ok:
                data = bytes(b.buf[:p])
                del b.buf[:p + desc_len]
                if data:
                    yield data
                return
        start = p + 1


def _deflated(b: _Buf, has_desc: bool, csize: int, zip64: bool) -> Iterator[bytes]:
    d = zlib.decompressobj(-15)
    remaining = None if has_desc else csize
    while not d.eof:
        if not b.buf and not b.more():
            raise EOFError("truncated deflate member")
        n = len(b.buf) if remaining is None else min(len(b.buf), remaining)
        chunk = bytes(b.buf[:n])
        del b.buf[:n]
        if remaining is not None:
            remaining -= n
        out = d.decompress(chunk)
        if out:
            yield out
    b.buf[:0] = d.unused_data
    if has_desc:
        b.fill(4)
        if b.buf[:4] == DESC:
            b.take(4)
        b.take(4 + (16 if zip64 else 8))


def iter_zip(chunks: Iterable[bytes]) -> Iterator[tuple[str, Iterator[bytes]]]:
    """Yield (name, data_iterator). Each data iterator must be fully consumed before the next."""
    b = _Buf(chunks)
    while b.fill(4):
        sig = bytes(b.buf[:4])
        if sig == CENTRAL or sig == b"PK\x05\x06" or sig == b"PK\x06\x06":
            return
        if sig != LOCAL:
            raise ValueError(f"unexpected zip signature {sig!r}")
        hdr = b.take(30)
        _, _, flags, method, _, _, _, csize, usize, nlen, xlen = struct.unpack("<IHHHHHIIIHH", hdr)
        name = b.take(nlen).decode("utf-8", "replace")
        extra = b.take(xlen)
        z64 = _zip64_sizes(extra)
        if z64 and csize == 0xFFFFFFFF:
            usize, csize = z64
        has_desc = bool(flags & 0x08)
        if method == 8:
            data = _deflated(b, has_desc, csize, z64 is not None)
        elif method == 0 and has_desc and csize == 0:
            data = _stored_with_descriptor(b, z64 is not None)
        elif method == 0:
            def _stored(n=csize, d=has_desc, z=z64 is not None):
                left = n
                while left:
                    if not b.buf and not b.more():
                        raise EOFError("truncated stored member")
                    k = min(left, len(b.buf))
                    out = bytes(b.buf[:k])
                    del b.buf[:k]
                    left -= k
                    yield out
                if d:
                    b.fill(4)
                    if b.buf[:4] == DESC:
                        b.take(4)
                    b.take(4 + (16 if z else 8))
            data = _stored()
        else:
            raise ValueError(f"{name}: unsupported compression method {method}")
        yield name, data
