"""Erros da API no formato Problem Details (RFC 9457, application/problem+json)."""

import http
from collections.abc import Sequence

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from pigeondome.application.ports import StorageError

PROBLEM_MEDIA_TYPE = "application/problem+json"
URN = "urn:pigeondome:erro:"


class FieldError(BaseModel):
    field: str = Field(description="parâmetro com problema")
    message: str = Field(description="explicação para humanos")
    code: str = Field(description="código estável do problema (não muda com o texto)")


class ProblemDetails(BaseModel):
    type: str = Field(description="URI que identifica o tipo de problema")
    title: str = Field(description="resumo curto e estável do tipo de problema")
    status: int = Field(description="código de status HTTP")
    detail: str = Field(description="explicação desta ocorrência")
    instance: str | None = Field(default=None, description="caminho da requisição que falhou")
    errors: list[FieldError] | None = Field(default=None, description="problemas por campo")


class ApiError(Exception):
    """Erro de negócio da API: vira uma resposta Problem Details com o status indicado."""

    def __init__(
        self,
        status: int,
        slug: str,
        title: str,
        detail: str,
        errors: Sequence[FieldError] = (),
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.type = URN + slug
        self.title = title
        self.detail = detail
        self.errors = list(errors)


def problem_response(
    request: Request,
    *,
    status: int,
    type_: str,
    title: str,
    detail: str,
    errors: Sequence[FieldError] = (),
) -> JSONResponse:
    body = ProblemDetails(
        type=type_,
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        errors=list(errors) or None,
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return problem_response(
            request,
            status=exc.status,
            type_=exc.type,
            title=exc.title,
            detail=exc.detail,
            errors=exc.errors,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # o valor enviado pelo cliente (campo "input" do Pydantic) NUNCA volta na resposta
        errors = [
            FieldError(
                field=".".join(str(part) for part in error["loc"][1:]) or "request",
                message=str(error["msg"]),
                code=str(error["type"]),
            )
            for error in exc.errors()
        ]
        return problem_response(
            request,
            status=422,
            type_=URN + "parametros-invalidos",
            title="Parâmetros inválidos",
            detail="um ou mais parâmetros da requisição são inválidos",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        try:
            title = http.HTTPStatus(exc.status_code).phrase
        except ValueError:
            title = "Erro"
        return problem_response(
            request,
            status=exc.status_code,
            type_="about:blank",
            title=title,
            detail=str(exc.detail),
        )

    @app.exception_handler(StorageError)
    async def storage_error(request: Request, exc: StorageError) -> JSONResponse:
        # nunca devolver detalhes internos (host, tabela, erro do driver) ao cliente
        return problem_response(
            request,
            status=503,
            type_=URN + "armazenamento-indisponivel",
            title="Armazenamento indisponível",
            detail="o armazenamento de dados está temporariamente indisponível",
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # o servidor registra o traceback; o cliente recebe só uma mensagem genérica
        return problem_response(
            request,
            status=500,
            type_=URN + "erro-interno",
            title="Erro interno",
            detail="ocorreu um erro inesperado",
        )
