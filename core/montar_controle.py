"""
Varre uma pasta de arquivos XLSX extraídos e monta as linhas do controle.

Padrão de nome esperado:
  ESCALA - DD.MM.YYYY - DIA-DA-SEMANA_ADM_EXTRAIDA.xlsx  → administrativo
  ESCALA - DD.MM.YYYY - DIA-DA-SEMANA_EXTRAIDA.xlsx       → operacional
"""
import re
from pathlib import Path
from typing import List, Dict

_PADRAO = re.compile(
    r"^ESCALA\s*-\s*(\d{2}\.\d{2}\.\d{4})\s*-\s*(.+?)(_ADM_EXTRAIDA|_EXTRAIDA)\.xlsx$",
    re.IGNORECASE,
)


def _parse_arquivo(nome: str) -> Dict | None:
    m = _PADRAO.match(nome)
    if not m:
        return None
    data_raw = m.group(1)
    dia = m.group(2).strip()
    sufixo = m.group(3).upper()
    data = data_raw.replace(".", "/")  # DD/MM/YYYY
    tipo_nota = "administrativo" if "_ADM_EXTRAIDA" in sufixo else "operacional"
    return {
        "data": data,
        "dia": dia,
        "tipo_nota": tipo_nota,
        "numero_nota": "",
        "arquivo_escala": nome,
        "status": "PENDENTE",
        "observacao": "",
        "processado_em": "",
    }


def montar_controle_a_partir_da_pasta(pasta: Path) -> List[Dict]:
    """
    Varre *pasta* por arquivos XLSX que batem com o padrão de escala extraída.
    Retorna lista de dicts prontos para ser passados a adicionar_linhas().
    Ordenados por data (crescente) e tipo_nota.
    """
    pasta = Path(pasta)
    if not pasta.exists():
        raise FileNotFoundError(f"Pasta não encontrada: {pasta}")

    linhas = []
    for f in sorted(pasta.glob("*.xlsx")):
        row = _parse_arquivo(f.name)
        if row:
            linhas.append(row)
        else:
            print(f"[MONTAR_CONTROLE] Arquivo ignorado (não bate com padrão): {f.name}")

    def _sort_key(r: Dict):
        d, mo, a = r["data"].split("/")
        return (int(a), int(mo), int(d), r["tipo_nota"])

    linhas.sort(key=_sort_key)
    print(f"[MONTAR_CONTROLE] {len(linhas)} arquivo(s) identificado(s) em '{pasta}'")
    return linhas
