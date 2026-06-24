"""Shared download helpers — stall-detection streaming reader for curl.

Instead of a fixed total timeout (--max-time), we read curl stdout in
chunks with a stall timeout: if no bytes arrive for N seconds the
process is killed, but slow-but-steady downloads complete normally.

A separate, longer connect timeout is used for the first byte (waiting
for the connection to establish), after which the shorter stall timeout
applies to subsequent chunks.
"""

import asyncio

STALL_TIMEOUT = 45
CONNECT_TIMEOUT = 90
CHUNK_SIZE = 65536


async def stream_download(proc, on_chunk=None):
    """Read a subprocess stdout with stall-detection.

    Calls ``on_chunk(downloaded_bytes)`` after each chunk if provided.
    Returns the full decoded text on success, or raises TimeoutError
    with a descriptive message if stalled at connect or transfer phase.
    The caller is responsible for launching the curl process (without
    --max-time) and checking proc.returncode after this returns.
    """
    chunks = []
    downloaded = 0
    first_byte = True
    while True:
        to = CONNECT_TIMEOUT if first_byte else STALL_TIMEOUT
        try:
            chunk = await asyncio.wait_for(
                proc.stdout.read(CHUNK_SIZE), timeout=to)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            label = "connect" if first_byte else "stall"
            raise TimeoutError(f"{label}: no data for {to}s")
        if not chunk:
            break
        first_byte = False
        chunks.append(chunk)
        downloaded += len(chunk)
        if on_chunk:
            on_chunk(downloaded)
    await proc.wait()
    return b"".join(chunks).decode(errors="replace")
