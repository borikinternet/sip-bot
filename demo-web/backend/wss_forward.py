"""Small conference-only TCP forwarder for exposing WSL WSS on the host LAN IP."""

from __future__ import annotations

import asyncio
import logging
import os


LISTEN_HOST = os.environ.get("DEMO_WSS_FORWARD_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("DEMO_WSS_FORWARD_PORT", "7443"))
TARGET_HOST = os.environ.get("DEMO_WSS_TARGET_HOST", "172.22.89.126")
TARGET_PORT = int(os.environ.get("DEMO_WSS_TARGET_PORT", "7443"))


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(64 * 1024):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        if not writer.is_closing():
            writer.close()
            await writer.wait_closed()


async def _forward(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
) -> None:
    try:
        target_reader, target_writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
    except OSError:
        client_writer.close()
        await client_writer.wait_closed()
        return
    await asyncio.gather(
        _pipe(client_reader, target_writer),
        _pipe(target_reader, client_writer),
    )


async def main() -> None:
    server = await asyncio.start_server(_forward, LISTEN_HOST, LISTEN_PORT)
    addresses = ", ".join(str(sock.getsockname()) for sock in server.sockets or ())
    logging.info("listening on %s; forwarding to %s:%s", addresses, TARGET_HOST, TARGET_PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(main())
