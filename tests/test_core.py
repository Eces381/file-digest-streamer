import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from file_digest_streamer import (
    FileDigestStreamer,
    DigestResult,
    SUPPORTED_ALGORITHMS,
)


class TestFileDigestStreamer(unittest.TestCase):
    def setUp(self):
        # Use a real temp directory so files land on an actual filesystem.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    def _write_file(self, name: str, data: bytes) -> Path:
        p = self.tmp_path / name
        p.write_bytes(data)
        return p

    # --- Happy path ---

    def test_small_file_matches_hashlib(self):
        data = b'hello world\n'
        p = self._write_file('small.bin', data)
        result = FileDigestStreamer(p).compute()
        self.assertEqual(result.hexdigest, hashlib.sha256(data).hexdigest())
        self.assertEqual(result.algorithm, 'sha256')
        self.assertEqual(result.size_bytes, len(data))

    def test_default_algorithm_is_sha256(self):
        data = b'abc'
        p = self._write_file('a.bin', data)
        result = FileDigestStreamer(p).compute()
        self.assertEqual(result.algorithm, 'sha256')

    def test_empty_file(self):
        p = self._write_file('empty.bin', b'')
        result = FileDigestStreamer(p).compute()
        self.assertEqual(result.hexdigest, hashlib.sha256(b'').hexdigest())
        self.assertEqual(result.size_bytes, 0)

    def test_block_size_smaller_than_file(self):
        data = b'x' * 10000
        p = self._write_file('big.bin', data)
        # block_size of 1 forces many iterations through the read loop.
        result = FileDigestStreamer(p, block_size=1).compute()
        self.assertEqual(result.hexdigest, hashlib.sha256(data).hexdigest())
        self.assertEqual(result.size_bytes, len(data))
        self.assertEqual(result.block_size, 1)

    def test_block_size_larger_than_file(self):
        data = b'short'
        p = self._write_file('short.bin', data)
        result = FileDigestStreamer(p, block_size=1 << 24).compute()
        self.assertEqual(result.hexdigest, hashlib.sha256(data).hexdigest())

    def test_alternate_algorithm(self):
        data = b'some bytes here'
        p = self._write_file('alt.bin', data)
        result = FileDigestStreamer(p, algorithm='md5').compute()
        self.assertEqual(result.algorithm, 'md5')
        self.assertEqual(result.hexdigest, hashlib.md5(data).hexdigest())

    def test_binary_content_with_nulls(self):
        data = bytes(range(256))
        p = self._write_file('binary.bin', data)
        result = FileDigestStreamer(p).compute()
        self.assertEqual(result.hexdigest, hashlib.sha256(data).hexdigest())

    def test_path_object_accepted(self):
        data = b'pathobj'
        p = self._write_file('po.bin', data)
        streamer = FileDigestStreamer(p)
        streamer.compute()
        self.assertEqual(streamer.path, p)

    def test_str_path_accepted(self):
        data = b'strpath'
        p = self._write_file('sp.bin', data)
        streamer = FileDigestStreamer(str(p))
        streamer.compute()
        self.assertEqual(streamer.path, p)

    # --- Edge cases and error handling ---

    def test_missing_file_raises_filenotfound(self):
        missing = self.tmp_path / 'does_not_exist.bin'
        with self.assertRaises(FileNotFoundError):
            FileDigestStreamer(missing).compute()

    def test_directory_raises_isadirectoryerror(self):
        with self.assertRaises(IsADirectoryError):
            FileDigestStreamer(self.tmp_path).compute()

    def test_invalid_algorithm_raises_valueerror(self):
        p = self._write_file('bad.bin', b'data')
        with self.assertRaises(ValueError):
            FileDigestStreamer(p, algorithm='not-a-real-algo')

    def test_non_positive_block_size_raises_valueerror(self):
        p = self._write_file('zero.bin', b'data')
        with self.assertRaises(ValueError):
            FileDigestStreamer(p, block_size=0)

    def test_negative_block_size_raises_valueerror(self):
        p = self._write_file('neg.bin', b'data')
        with self.assertRaises(ValueError):
            FileDigestStreamer(p, block_size=-1024)

    def test_supported_algorithms_is_iterable_and_contains_sha256(self):
        self.assertIn('sha256', SUPPORTED_ALGORITHMS)
        self.assertIn('md5', SUPPORTED_ALGORITHMS)

    def test_digest_result_is_frozen(self):
        p = self._write_file('frozen.bin', b'data')
        result = FileDigestStreamer(p).compute()
        with self.assertRaises(Exception):
            result.hexdigest = 'tampered'  # type: ignore[misc]

    def test_large_file_does_not_exceed_block_memory(self):
        # Create a file larger than the default block size to exercise the
        # multi-read path. 5 MiB with a 1 MiB block means 5 reads.
        size = 5 * (1 << 20)
        data = bytes((i % 251) for i in range(size))
        p = self._write_file('multi.bin', data)
        result = FileDigestStreamer(p, block_size=1 << 20).compute()
        self.assertEqual(result.hexdigest, hashlib.sha256(data).hexdigest())
        self.assertEqual(result.size_bytes, size)
        self.assertEqual(result.block_size, 1 << 20)


if __name__ == '__main__':
    unittest.main()
