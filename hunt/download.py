"""Shared download helpers — stall-detection streaming reader for curl.

Instead of a fixed total timeout (--max-time), we read curl stdout in
chunks with a stall timeout: if no bytes arrive for N seconds the
process is killed, but slow-but-steady downloads complete normally.

A separate, longer connect timeout is used for the first byte (waiting
for the connection to establish), after which the shorter stall timeout
applies to subsequent chunks.

``--connect-timeout`` is passed to curl itself so that unreachable hosts
are abandoned quickly at the TCP level rather than waiting for the
operating-system connect timeout (which can exceed 2 minutes).
"""

import asyncio

# TCP connect timeout passed to curl via --connect-timeout.
CURL_CONNECT_TIMEOUT = 15

# Python-side timeout for the first byte after curl has connected.
CONNECT_TIMEOUT = 30

# Python-side timeout for subsequent chunks (transfer stall).
STALL_TIMEOUT = 45

CHUNK_SIZE = 65536


def curl_args(url: str, *, proxy: str = "", fail_on_error: bool = True,
              user_agent: str = "huntproxy/1.0") -> list[str]:
    """Build a curl argument list with fast-fail connect timeout.

    The caller is responsible for launching the subprocess (without
    ``--max-time``) and feeding the resulting process to
    :func:`stream_download`.
    """
    args = ["curl", "-sS", "-L", "--connect-timeout", str(CURL_CONNECT_TIMEOUT)]
    if fail_on_error:
        args.append("-f")
    if user_agent:
        args += ["-A", user_agent]
    if proxy:
        args += ["--proxy", proxy]
    args.append(url)
    return args


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
