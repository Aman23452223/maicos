"""Dual-port bridge for container deployments.

Binds to alternative ports (e.g. 8000 and 8080) and forwards all
incoming TCP connections to the active uvicorn application port.
This guarantees that Railway/cloud edge routers never get 502 Bad Gateway
due to a port mismatch between EXPOSE and the runtime $PORT.
"""
from __future__ import annotations

import asyncio
import os
import sys


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    target_port: int,
) -> None:
    try:
        t_reader, t_writer = await asyncio.open_connection("127.0.0.1", target_port)
    except Exception:
        try:
            writer.close()
        except Exception:
            pass
        return

    asyncio.create_task(_pipe(reader, t_writer))
    asyncio.create_task(_pipe(t_reader, writer))


async def main() -> None:
    target_port = (
        int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8000"))
    )
    # Common ports used by cloud proxies (Railway, Render, Fly)
    alt_ports = [8000, 8080, 3000]
    servers: list[asyncio.Server] = []

    # Wait briefly for uvicorn to begin listening
    await asyncio.sleep(0.5)

    for port in alt_ports:
        if port != target_port:
            try:
                server = await asyncio.start_server(
                    lambda r, w, tp=target_port: _handle_client(r, w, tp),
                    "0.0.0.0",
                    port,
                )
                servers.append(server)
                print(
                    f"[bridge] listening on 0.0.0.0:{port} -> 127.0.0.1:{target_port}",
                    flush=True,
                )
            except Exception as exc:
                # Port already bound or not permitted; safe to continue
                print(f"[bridge] port {port} skipped ({exc})", flush=True)

    if servers:
        await asyncio.gather(*(s.serve_forever() for s in servers))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
