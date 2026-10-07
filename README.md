# File Digest Streamer

Computes an incremental hash digest of a file by reading it in fixed-size blocks, so files larger than available memory can be hashed without loading them whole.

## Usage

```python
import tempfile
from pathlib import Path

from file_digest_streamer import FileDigestStreamer

with tempfile.NamedTemporaryFile() as f:
    f.write(b'hello world')
    f.flush()
    streamer = FileDigestStreamer(Path(f.name), algorithm='sha256', block_size=1048576)
    result = streamer.compute()

    print(result.algorithm)   # 'sha256'
    print(result.hexdigest)   # lowercase hex digest
    print(result.size_bytes)  # bytes actually read and hashed
    print(result.block_size)  # block size used
```

The exported names are `FileDigestStreamer`, `DigestResult`, and `SUPPORTED_ALGORITHMS`.

## Why this exists

`hashlib.file_digest` exists in Python 3.11+, but earlier versions and many production environments do not have it. The straightforward alternative — `hashlib.sha256(open(path, 'rb').read())` — reads the entire file into memory and falls over on multi-gigabyte logs. This library wraps the one pattern that actually scales: open in binary, read a block, call `update`, repeat.

The trade-off is that we only support real files on disk (paths that `open()` accepts). We do not support pipes, sockets, or non-seekable streams. Supporting those would require either buffering the whole stream or giving up the ability to report total bytes upfront; both are worse than asking the caller to materialise a file.

## Edge you will hit

`DigestResult.size_bytes` is the number of bytes actually read and hashed, not the file size returned by `os.stat`. If the file is truncated between the `stat` call and the read (or written concurrently and shrunk), these will differ. Compare them yourself if that matters to you. The library does not retry or lock.
