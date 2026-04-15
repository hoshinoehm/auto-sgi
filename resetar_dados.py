"""
Apaga todos os arquivos de trabalho do auto-sgi:
  - /data/entradas/   (DOCX de entrada)
  - /data/extraidas/  (XLSX extraídos)
  - /data/controle/controle.xlsx

Use antes de um novo lote limpo.
"""
import os
import shutil
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))

DIRS_LIMPAR = [
    DATA_DIR / "entradas",
    DATA_DIR / "extraidas",
]

CONTROLE = DATA_DIR / "controle" / "controle.xlsx"


def resetar():
    for pasta in DIRS_LIMPAR:
        if pasta.exists():
            count = len(list(pasta.glob("*")))
            shutil.rmtree(pasta)
            pasta.mkdir(parents=True)
            print(f"[OK] {pasta} — {count} arquivo(s) removido(s)")
        else:
            pasta.mkdir(parents=True)
            print(f"[OK] {pasta} — criada (não existia)")

    if CONTROLE.exists():
        CONTROLE.unlink()
        print(f"[OK] {CONTROLE} — removido")
    else:
        print(f"[--] {CONTROLE} — não existia")

    print("\nAmbiente resetado. Pronto para novo lote.")


if __name__ == "__main__":
    resetar()
