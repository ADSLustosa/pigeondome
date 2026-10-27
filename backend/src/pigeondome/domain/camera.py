"""Quadro (snapshot) de uma câmera: o que a API repassa ao painel.

Puro: sem rede e sem relógio. Só aceita JPEG de tamanho razoável, para que a API nunca repasse
ao navegador outra coisa (uma página HTML, por exemplo) com cara de imagem.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

MAX_SNAPSHOT_BYTES = 2_000_000
JPEG_SIGNATURE = b"\xff\xd8\xff"
HTTP_DEFAULT_PORT = 80


class InvalidSnapshotError(ValueError):
    """O conteúdo recebido da câmera não é um quadro JPEG aceitável."""


@dataclass(frozen=True)
class Snapshot:
    """O quadro mais recente de uma câmera, já conferido (assinatura JPEG e tamanho)."""

    content: bytes

    def __post_init__(self) -> None:
        if not self.content.startswith(JPEG_SIGNATURE):
            raise InvalidSnapshotError("o conteúdo não é um JPEG")
        if len(self.content) > MAX_SNAPSHOT_BYTES:
            raise InvalidSnapshotError("o quadro excede o tamanho máximo")


@dataclass(frozen=True)
class CameraTarget:
    """Para onde a API vai buscar o quadro: endereço, porta e caminho (com a query)."""

    host: str
    port: int
    path: str


def parse_camera_url(url: str) -> CameraTarget:
    """Valida a URL do quadro de uma câmera.

    As mensagens de erro nunca repetem a URL, que pode carregar um token.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ValueError("URL inválida") from exc
    if parts.scheme != "http":
        raise ValueError("só http é aceito (a câmera fica na rede local)")
    if not parts.hostname:
        raise ValueError("falta o endereço da câmera")
    if parts.username or parts.password:
        raise ValueError("usuário e senha na URL não são aceitos")
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    return CameraTarget(parts.hostname, port or HTTP_DEFAULT_PORT, path)
