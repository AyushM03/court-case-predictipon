import io
import os
import zipfile

import pytest

from court_delay.ziptail import iter_zip


class _NoSeek(io.RawIOBase):
    """Unseekable sink, so zipfile writes data descriptors like Dropbox does."""
    def __init__(self):
        self.data = bytearray()

    def writable(self):
        return True

    def write(self, b):
        self.data += b
        return len(b)


@pytest.mark.parametrize("method", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
@pytest.mark.parametrize("zip64", [False, True])
def test_iter_zip_roundtrip(method, zip64):
    files = {
        "csv/": b"",
        "csv/keys/a.csv": b"x,y\n1,2\n" * 1000,
        # a fake descriptor signature inside the data must not end the member early
        "csv/cases/c.tar.gz": os.urandom(300_000) + b"PK\x07\x08junk" + os.urandom(1000),
        "license.txt": b"lic",
    }
    sink = _NoSeek()
    with zipfile.ZipFile(sink, "w", method) as z:
        for name, data in files.items():
            with z.open(zipfile.ZipInfo(name), "w", force_zip64=zip64) as f:
                f.write(data)
    raw = bytes(sink.data)
    chunks = (raw[i:i + 4096] for i in range(0, len(raw), 4096))
    assert {n: b"".join(d) for n, d in iter_zip(chunks)} == files
