"""Servidor HTTP do quadro simulado: só neste computador, como a câmera de uma rede local."""

import contextlib
import logging
import sys
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("pigeondome_sim")

HOST = "127.0.0.1"  # nunca outro endereço: a imagem não sai deste computador


class _Server(ThreadingHTTPServer):
    # No Windows, SO_REUSEADDR deixaria OUTRO processo abrir a mesma porta; nos demais sistemas
    # ele só evita esperar o fim do TIME_WAIT ao reiniciar.
    allow_reuse_address = sys.platform != "win32"


def _handler_for(frame: Callable[[], bytes]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def version_string(self) -> str:
            return "pigeondome-sim"

        def log_message(self, format: str, *args: object) -> None:
            log.debug(format, *args)

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.wfile.write(body)

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/snapshot":
                try:
                    body = frame()
                except Exception:
                    log.exception("falha ao desenhar o quadro")
                    self._send(500, "text/plain; charset=utf-8", b"erro interno")
                    return
                self._send(200, "image/jpeg", body)
            elif path == "/health":
                self._send(200, "text/plain; charset=utf-8", b"ok")
            else:
                self._send(404, "text/plain; charset=utf-8", b"nao encontrado")

    return Handler


class SnapshotServer:
    """Serve GET /snapshot (JPEG) e GET /health. `port=0` escolhe uma porta livre (testes)."""

    def __init__(self, port: int, frame: Callable[[], bytes]) -> None:
        self._server = _Server((HOST, port), _handler_for(frame))
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="snapshot-server", daemon=True
        )

    @property
    def host(self) -> str:
        return str(self._server.server_address[0])

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        if self._thread.is_alive():  # shutdown() sem serve_forever() em execução trava
            self._server.shutdown()
            self._thread.join(timeout=5)
        self._server.server_close()


def start_snapshot_server(port: int, frame: Callable[[], bytes]) -> SnapshotServer | None:
    """Sobe o servidor. Porta ocupada: segue sem imagem (as contagens não dependem dela)."""
    try:
        server = SnapshotServer(port, frame)
    except OSError as exc:
        log.warning("imagem simulada desligada: não foi possível abrir a porta %d (%s)", port, exc)
        return None
    server.start()
    log.info("imagem simulada em http://%s:%d/snapshot", server.host, server.port)
    return server
