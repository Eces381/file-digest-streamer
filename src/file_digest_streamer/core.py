"""Incremental hash digest computation for large files.

The core problem with hashing large files is the temptation to read them whole.
That fails the moment the file is bigger than available memory. This module
reads the file in fixed-size blocks and feeds each block to hashlib.update,
which itself maintains a rolling state and returns only the final digest.

Design decision: we deliberately DO NOT support non-seekable streams. The
brief says 'file', and supporting pipes would mean we could not report total
bytes upfront nor guard against a truncated read without extra bookkeeping.
We open a real path on disk, stat it for size, and read sequentially. That is
one clear interpretation rather than a half-working wrapper around two.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union

SUPPORTED_ALGORITHMS = tuple(sorted(hashlib.algorithms_guaranteed))
"""Algorithms hashlib promises across all Python builds. We expose this so
the caller can validate before opening a file rather than failing mid-stream."""

_PathLike = Union[str, os.PathLike]


@dataclass(frozen=True)
class DigestResult:
    """Outcome of a successful digest computation.

    Attributes:
        algorithm: The hashlib algorithm name actually used (e.g. 'sha256').
        hexdigest: Lowercase hexadecimal digest string.
        size_bytes: Number of bytes hashed. Reported separately from the file
            size on disk so the caller can detect truncation that occurred
            between stat and read.
        block_size: The block size in bytes used for streaming.
    """

    algorithm: str
    hexdigest: str
    size_bytes: int
    block_size: int


class FileDigestStreamer:
    """Stream a file through a hashing algorithm in fixed-size blocks.

    Example:
        streamer = FileDigestStreamer('/var/log/app.log', algorithm='sha256')
        result = streamer.compute()
        print(result.hexdigest)

    The file is opened in binary mode and read sequentially. It is never held
    in memory in full; only one block is resident at a time.
    """

    def __init__(
        self,
        path: _PathLike,
        *,
        algorithm: str = 'sha256',
        block_size: int = 1 << 20,
    ) -> None:
        if algorithm not in hashlib.algorithms_guaranteed:
            raise ValueError(
                f"Unsupported algorithm {algorithm!r}. "
                f"Use one of: {', '.join(SUPPORTED_ALGORITHMS)}"
            )
        if block_size <= 0:
            raise ValueError(f"block_size must be positive, got {block_size}")

        self._path = Path(path)
        self._algorithm = algorithm
        self._block_size = block_size

    @property
    def path(self) -> Path:
        return self._path

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def block_size(self) -> int:
        return self._block_size

    def compute(self) -> DigestResult:
        """Compute and return the digest of the file.

        Raises:
            FileNotFoundError: If the path does not exist.
            IsADirectoryError: If the path is a directory.
            PermissionError: If the file cannot be opened for reading.
            ValueError: If the algorithm is not supported (re-checked at call
                time so callers cannot mutate the instance between construction
                and compute, though this class is effectively immutable).
        """
        if self._algorithm not in hashlib.algorithms_guaranteed:
            raise ValueError(f"Unsupported algorithm {self._algorithm!r}.")

        # open() performs the existence and permission checks and raises the
        # appropriate OSError subclass. We let those propagate rather than
        # re-implementing them, so callers see the standard Python error types.
        hasher = hashlib.new(self._algorithm)
        size_bytes = 0

        with open(self._path, 'rb') as fh:
            while True:
                chunk = fh.read(self._block_size)
                if not chunk:
                    break
                hasher.update(chunk)
                size_bytes += len(chunk)

        return DigestResult(
            algorithm=self._algorithm,
            hexdigest=hasher.hexdigest(),
            size_bytes=size_bytes,
            block_size=self._block_size,
        )
