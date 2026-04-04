"""
Autenticação por API Key via header X-API-Key.
A chave esperada vem da variável de ambiente API_KEY.
"""
import os

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verificar_api_key(key: str = Security(_api_key_header)):
    expected = os.environ.get("API_KEY", "")
    if not expected:
        raise HTTPException(status_code=500, detail="API_KEY não configurada no servidor")
    if key != expected:
        raise HTTPException(status_code=403, detail="Acesso negado: X-API-Key inválida")
