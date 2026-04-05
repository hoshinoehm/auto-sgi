"""
AUTO SGI — API FastAPI

Endpoints:
  GET  /health
  POST /extrair-escala     recebe DOCX, gera XLSX em /data/extraidas/
  POST /criar-notas        cria notas no SGI, atualiza controle
  POST /montar-controle    adiciona linhas ao controle após extração
  POST /anexar-lote        anexa registros das notas pendentes no SGI

Todas as rotas (exceto /health) exigem header:
  X-API-Key: <valor de API_KEY no .env>

Variáveis de ambiente necessárias:
  SGI_USUARIO, SGI_SENHA, API_KEY, DATA_DIR (padrão /data)
"""
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.auth import verificar_api_key
import api.controle as controle_db
from core.extrair_escala import extrair_arquivo
from core.criar_nota import criar_notas
from core.anexos import anexar_lote
from core.montar_controle import montar_controle_a_partir_da_pasta

# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AUTO SGI API",
    description="Automação de escalas SGI — orquestrada pelo n8n",
    version="1.0.0",
)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
ENTRADAS_DIR = DATA_DIR / "entradas"
EXTRAIDAS_DIR = DATA_DIR / "extraidas"


def _sgi_creds():
    usuario = os.environ.get("SGI_USUARIO", "")
    senha = os.environ.get("SGI_SENHA", "")
    if not usuario or not senha:
        raise HTTPException(
            status_code=500,
            detail="Credenciais SGI_USUARIO/SGI_SENHA não configuradas no servidor",
        )
    return usuario, senha


def _erro(etapa: str, mensagem: str, detalhe: str = "", retry_safe: bool = True):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": etapa,
            "message": mensagem,
            "detalhe": detalhe,
            "retry_safe": retry_safe,
            "timestamp": datetime.now().isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class ItemNota(BaseModel):
    modo: str
    data: str
    data_fim: Optional[str] = None


class CriarNotasPayload(BaseModel):
    itens: Optional[List[ItemNota]] = None  # se omitido, lê PENDENTE do controle.xlsx
    data: Optional[str] = None              # filtro opcional por data (dd/mm/yyyy)


class MontarControlePayload(BaseModel):
    pasta: Optional[str] = None          # padrão: DATA_DIR/extraidas
    arquivo_saida: Optional[str] = None  # padrão: DATA_DIR/controle/controle.xlsx


class AnexarLotePayload(BaseModel):
    data: Optional[str] = None
    status_filtro: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["sistema"])
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "data_dir": str(DATA_DIR),
    }


@app.post("/extrair-escala", tags=["extração"], dependencies=[Depends(verificar_api_key)])
async def endpoint_extrair_escala(arquivo: UploadFile = File(...)):
    """
    Recebe um arquivo DOCX (multipart/form-data), salva em /data/entradas/,
    extrai a escala e gera os XLSX em /data/extraidas/.

    O n8n deve enviar o binário do arquivo via campo 'arquivo'.
    """
    if not arquivo.filename.lower().endswith((".docx", ".xlsx")):
        raise HTTPException(status_code=422, detail="Envie um arquivo .docx ou .xlsx")

    ENTRADAS_DIR.mkdir(parents=True, exist_ok=True)
    EXTRAIDAS_DIR.mkdir(parents=True, exist_ok=True)

    destino = ENTRADAS_DIR / arquivo.filename
    conteudo = await arquivo.read()
    destino.write_bytes(conteudo)
    print(f"[ENTRADA] Arquivo salvo: {destino}")

    try:
        resultado = extrair_arquivo(destino, EXTRAIDAS_DIR)
    except Exception as e:
        return _erro(
            etapa="extrair_escala",
            mensagem="Falha ao extrair a escala do arquivo",
            detalhe=str(e),
            retry_safe=False,
        )

    return {
        "success": True,
        "arquivo_origem": arquivo.filename,
        "arquivos_gerados": {
            "operacional": resultado["operacional"],
            "administrativo": resultado["administrativo"],
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/criar-notas", tags=["SGI"], dependencies=[Depends(verificar_api_key)])
async def endpoint_criar_notas(payload: CriarNotasPayload = CriarNotasPayload()):
    """
    Cria notas no SGI.

    Sem payload: lê automaticamente todas as linhas PENDENTE do controle.xlsx.
    Com payload.itens: usa a lista fornecida (modo legado).
    Com payload.data: filtra pelo campo data (dd/mm/yyyy).

    Após criar cada nota, atualiza o controle.xlsx com numero_nota e status NOTA_CRIADA.
    Idempotente: pula linhas que já estão em NOTA_CRIADA ou CONCLUIDO.
    """
    usuario, senha = _sgi_creds()

    if payload.itens:
        # Modo legado: itens passados manualmente
        itens = [item.model_dump() for item in payload.itens]
    else:
        # Modo automático: lê PENDENTE do controle.xlsx
        pendentes = controle_db.buscar(data=payload.data, status_list=["PENDENTE"])
        if not pendentes:
            return {
                "success": True,
                "message": "Nenhuma linha PENDENTE no controle",
                "total": 0,
                "criadas": 0,
                "notas": [],
                "timestamp": datetime.now().isoformat(),
            }
        itens = [
            {"modo": l["tipo_nota"], "data": l["data"]}
            for l in pendentes
        ]

    # Filtra itens já processados (idempotência)
    itens_a_criar = []
    notas_ja_existentes = []

    for item in itens:
        existentes = controle_db.buscar(
            data=item["data"],
            status_list=["NOTA_CRIADA", "CONCLUIDO"],
        )
        ja_existe = next(
            (l for l in existentes if l.get("tipo_nota") == item["modo"]), None
        )
        if ja_existe:
            print(f"[IDEMPOTÊNCIA] Nota já existe para {item['data']} / {item['modo']}: {ja_existe['numero_nota']}")
            notas_ja_existentes.append({
                "modo": item["modo"],
                "data": item["data"],
                "numero_nota": ja_existe["numero_nota"],
                "status": "JA_EXISTIA",
            })
        else:
            itens_a_criar.append(item)

    resultados = notas_ja_existentes

    if itens_a_criar:
        try:
            novos = criar_notas(itens_a_criar, usuario, senha)
            resultados.extend(novos)

            for r in novos:
                if r.get("numero_nota") and r.get("status") == "OK":
                    controle_db.marcar_status(
                        data=r["data"],
                        tipo_nota=r["modo"],
                        status="NOTA_CRIADA",
                        numero_nota=r["numero_nota"],
                    )
                else:
                    controle_db.marcar_status(
                        data=r["data"],
                        tipo_nota=r["modo"],
                        status="ERRO",
                        observacao=r.get("status", ""),
                    )
        except Exception as e:
            return _erro(
                etapa="criar_notas",
                mensagem="Falha ao criar notas no SGI",
                detalhe=traceback.format_exc(),
                retry_safe=True,
            )

    ok = sum(1 for r in resultados if r.get("status") in ("OK", "JA_EXISTIA"))
    return {
        "success": True,
        "total": len(resultados),
        "criadas": ok,
        "notas": resultados,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/montar-controle", tags=["controle"], dependencies=[Depends(verificar_api_key)])
async def endpoint_montar_controle(payload: MontarControlePayload = MontarControlePayload()):
    """
    Varre a pasta de escalas extraídas, identifica os XLSX pelo padrão de nome
    e popula o controle.xlsx com as linhas encontradas.

    Padrões de nome reconhecidos:
      ESCALA - DD.MM.YYYY - DIA_ADM_EXTRAIDA.xlsx  → administrativo
      ESCALA - DD.MM.YYYY - DIA_EXTRAIDA.xlsx       → operacional

    Idempotente: não duplica linhas com mesma (data, tipo_nota).

    Payload opcional:
      { "pasta": "/data/extraidas", "arquivo_saida": "/data/controle/controle.xlsx" }
    """
    pasta = Path(payload.pasta) if payload.pasta else EXTRAIDAS_DIR

    try:
        novas = montar_controle_a_partir_da_pasta(pasta)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        return _erro(
            etapa="montar_controle",
            mensagem="Falha ao varrer a pasta de escalas",
            detalhe=str(e),
        )

    if not novas:
        return {
            "success": True,
            "message": "Nenhum arquivo com padrão reconhecido encontrado na pasta",
            "pasta": str(pasta),
            "linhas_adicionadas": 0,
            "linhas_ignoradas": 0,
            "timestamp": datetime.now().isoformat(),
        }

    adicionadas = controle_db.adicionar_linhas(novas)

    return {
        "success": True,
        "pasta": str(pasta),
        "arquivos_encontrados": len(novas),
        "linhas_adicionadas": adicionadas,
        "linhas_ignoradas": len(novas) - adicionadas,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/anexar-lote", tags=["SGI"], dependencies=[Depends(verificar_api_key)])
async def endpoint_anexar_lote(payload: AnexarLotePayload):
    """
    Lê o controle.xlsx e para cada linha com status NOTA_CRIADA (ou ERRO, para retry),
    faz a anexação dos registros da escala na nota correspondente no SGI.

    Filtra por 'data' se fornecido. Retomada segura: pula CONCLUIDO.
    """
    usuario, senha = _sgi_creds()

    status_busca = payload.status_filtro or ["NOTA_CRIADA", "ERRO"]
    linhas = controle_db.buscar(data=payload.data, status_list=status_busca)

    if not linhas:
        return {
            "success": True,
            "message": "Nenhuma linha pendente encontrada no controle",
            "processadas": 0,
            "timestamp": datetime.now().isoformat(),
        }

    resultados = []
    total_sucesso = 0
    total_falhas = 0

    for linha in linhas:
        nota_id = linha.get("numero_nota", "").strip()
        arquivo = linha.get("arquivo_escala", "").strip()
        data = linha.get("data", "")
        tipo = linha.get("tipo_nota", "")

        if not nota_id:
            resultados.append({
                "data": data,
                "tipo_nota": tipo,
                "status": "ERRO",
                "erro": "numero_nota vazio no controle",
            })
            controle_db.marcar_status(data, tipo, "ERRO", observacao="numero_nota vazio")
            continue

        xlsx_path = EXTRAIDAS_DIR / arquivo
        if not xlsx_path.exists():
            resultados.append({
                "data": data,
                "tipo_nota": tipo,
                "nota_id": nota_id,
                "status": "ERRO",
                "erro": f"Arquivo não encontrado: {arquivo}",
            })
            controle_db.marcar_status(data, tipo, "ERRO", observacao=f"Arquivo não encontrado: {arquivo}")
            continue

        controle_db.marcar_status(data, tipo, "ANEXANDO")

        try:
            resultado = anexar_lote(nota_id, str(xlsx_path), usuario, senha)

            if resultado["falhas"]:
                status_final = "ERRO"
                obs = f"{resultado['sucesso']}/{resultado['total']} ok. Falhas: {len(resultado['falhas'])}"
                total_falhas += len(resultado["falhas"])
            else:
                status_final = "CONCLUIDO"
                obs = ""
                total_sucesso += resultado["sucesso"]

            controle_db.marcar_status(data, tipo, status_final, observacao=obs)

            resultados.append({
                "data": data,
                "tipo_nota": tipo,
                "nota_id": nota_id,
                "total": resultado["total"],
                "sucesso": resultado["sucesso"],
                "falhas": resultado["falhas"],
                "status": status_final,
            })

        except Exception as e:
            controle_db.marcar_status(data, tipo, "ERRO", observacao=str(e))
            resultados.append({
                "data": data,
                "tipo_nota": tipo,
                "nota_id": nota_id,
                "status": "ERRO",
                "erro": str(e),
            })

    return {
        "success": True,
        "processadas": len(resultados),
        "total_registros_sucesso": total_sucesso,
        "total_falhas_registro": total_falhas,
        "resultado": resultados,
        "timestamp": datetime.now().isoformat(),
    }
