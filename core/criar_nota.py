"""
Lógica de criação de notas no SGI.
Extraída de sgi_criar_nota.py — sem input(), sem getpass().
Credenciais vêm por parâmetro (vindos de variáveis de ambiente no contexto da API).

Função pública principal:
  criar_notas(itens, usuario, senha) -> List[Dict]
"""
import os
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    UnexpectedAlertPresentException,
    NoAlertPresentException,
)

from core.driver import criar_driver
from core.sgi_auth import login_completo, aceitar_alertas_se_existirem

SGI_URL_CRIAR_NOTA = "https://sgi.pm.ma.gov.br/boletim_eletronico_notas_dp_inicio.php"
DEFAULT_TIMEOUT = int(os.environ.get("SELENIUM_TIMEOUT", "30"))


# ---------------------------------------------------------------------------
# Helpers internos (mesma lógica de sgi_criar_nota.py)
# ---------------------------------------------------------------------------

def _parse_data(texto: str) -> datetime:
    texto = (texto or "").strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            pass
    raise ValueError(f"Data inválida: '{texto}'. Use dd/mm/aaaa.")


def _normalizar_modo(valor: str) -> str:
    v = (valor or "").strip().lower()
    if v in ("a", "adm", "administrativo"):
        return "administrativo"
    if v in ("o", "op", "operacional"):
        return "operacional"
    raise ValueError(f"Tipo inválido: '{valor}'. Use 'administrativo' ou 'operacional'.")


def _esperar_opcao_em_select(driver, select_id, texto_procurado, timeout=DEFAULT_TIMEOUT):
    wait = WebDriverWait(driver, timeout)

    def cond(d):
        try:
            el = d.find_element(By.ID, select_id)
            options = el.find_elements(By.TAG_NAME, "option")
            return any(texto_procurado.lower() in (o.text or "").strip().lower() for o in options)
        except Exception:
            return False

    wait.until(cond)


def _safe_select(select_el, target_text: str) -> bool:
    sel = Select(select_el)
    try:
        sel.select_by_visible_text(target_text)
        return True
    except Exception:
        pass
    for opt in sel.options:
        if (opt.text or "").strip().lower() == target_text.strip().lower():
            sel.select_by_visible_text(opt.text)
            return True
    return False


def _aguardar_numero_nota(driver, timeout=DEFAULT_TIMEOUT) -> str:
    fim = time.time() + timeout
    while time.time() < fim:
        try:
            alert = driver.switch_to.alert
            texto = (alert.text or "").strip()
            alert.accept()
            print(f"[ALERTA] Aceito: {texto}")
            time.sleep(0.6)
            continue
        except NoAlertPresentException:
            pass

        try:
            els = driver.find_elements(
                By.XPATH, "//h4/b[contains(translate(.,'nota','NOTA'),'NOTA')]"
            )
            if els:
                texto = (els[0].text or "").strip()
                m = re.search(r"NOTA\s*N[ºo]?\s*([0-9]{8,20})", texto, flags=re.IGNORECASE)
                if m:
                    return m.group(1)
                m2 = re.search(r"([0-9]{8,20})", texto)
                if m2:
                    return m2.group(1)
        except UnexpectedAlertPresentException:
            continue
        except Exception:
            pass

        try:
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='?ID=']")
            for a in links:
                href = a.get_attribute("href") or ""
                m = re.search(r"[?&]ID=([0-9]{8,20})", href)
                if m:
                    return m.group(1)
        except UnexpectedAlertPresentException:
            continue
        except Exception:
            pass

        time.sleep(0.3)

    return "nao_identificado"


def _selecionar_boletim_e_gravar(driver):
    wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
    print("[7] Selecionando 'Boletim Interno'...")

    select_el = wait.until(EC.presence_of_element_located((By.NAME, "tipo_bg")))
    Select(select_el).select_by_visible_text("Boletim Interno")

    url_atual = driver.current_url
    botao = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.btn-success")))
    botao.click()

    aceitar_alertas_se_existirem(driver, timeout_total=3)

    try:
        wait.until(lambda d: d.current_url != url_atual)
    except TimeoutException:
        print("[7] A URL não mudou no tempo esperado.")


def _preencher_formulario(driver, modo: str, data_inicio: datetime, data_fim: datetime) -> str:
    wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
    modo = modo.strip().lower()

    config = {
        "administrativo": {
            "parte": "1.1 SERVICOS INTERNOS",
            "sub_finalidade": "Administrativo",
            "funcao": "ATO DO COMANDANTE DO 31º BPM",
        },
        "operacional": {
            "parte": "1.2 SERVICOS EXTERNOS",
            "sub_finalidade": "Operacional",
            "funcao": "ATO DO COMANDANTE DO 31º BPM",
        },
    }[modo]

    print(f"[8] Preenchendo formulário ({modo.upper()})...")

    parte_el = wait.until(EC.presence_of_element_located((By.ID, "parte_bg")))
    if not _safe_select(parte_el, config["parte"]):
        raise RuntimeError(f"Não encontrei PARTE BOLETIM: '{config['parte']}'")

    _esperar_opcao_em_select(driver, "finalidade", "Serviço")
    finalidade_el = wait.until(EC.presence_of_element_located((By.ID, "finalidade")))
    if not _safe_select(finalidade_el, "Serviço"):
        raise RuntimeError("Não consegui selecionar 'Serviço' em FINALIDADE")

    _esperar_opcao_em_select(driver, "finalidade_2", config["sub_finalidade"])
    sub_el = wait.until(EC.presence_of_element_located((By.ID, "finalidade_2")))
    if not _safe_select(sub_el, config["sub_finalidade"]):
        raise RuntimeError(f"Não consegui selecionar SUB FINALIDADE: '{config['sub_finalidade']}'")

    class_el = wait.until(EC.presence_of_element_located((By.NAME, "classificacao")))
    if not _safe_select(class_el, "ALTERAÇÃO DE OFICIAL E PRAÇA"):
        raise RuntimeError("Não encontrei CLASSIFICAÇÃO: 'ALTERAÇÃO DE OFICIAL E PRAÇA'")

    func_el = wait.until(EC.presence_of_element_located((By.NAME, "funcao_bg")))
    if not _safe_select(func_el, config["funcao"]):
        raise RuntimeError(f"Não encontrei FUNÇÃO: '{config['funcao']}'")

    data_inicio_str = data_inicio.strftime("%d/%m/%Y")
    data_fim_str = data_fim.strftime("%d/%m/%Y")
    print(f"[8.6] DATA INÍCIO: {data_inicio_str} | DATA FIM: {data_fim_str}")

    di_input = wait.until(EC.presence_of_element_located((By.NAME, "data_inicio")))
    df_input = wait.until(EC.presence_of_element_located((By.NAME, "data_fim")))

    di_input.clear()
    di_input.send_keys(data_inicio_str)
    df_input.clear()
    df_input.send_keys(data_fim_str)

    botao = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "form button.btn.btn-success")))
    botao.click()

    aceitar_alertas_se_existirem(driver, timeout_total=8)
    numero_nota = _aguardar_numero_nota(driver)
    print(f"[9] Nota criada: {numero_nota}")
    return numero_nota


def _criar_uma_nota(driver, modo: str, data: str, data_fim: str = None) -> Dict:
    wait = WebDriverWait(driver, DEFAULT_TIMEOUT)

    data_inicio_dt = _parse_data(data)
    if data_fim:
        data_fim_dt = _parse_data(data_fim)
    else:
        data_fim_dt = data_inicio_dt if modo == "administrativo" else data_inicio_dt + timedelta(days=1)

    print(f"\n[NOTA] Criando nota: {modo.upper()} | {data_inicio_dt.strftime('%d/%m/%Y')}")

    driver.get(SGI_URL_CRIAR_NOTA)
    try:
        wait.until(EC.url_contains("boletim_eletronico_notas_dp_inicio.php"))
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except TimeoutException:
        print("[AVISO] Não confirmei carregamento da tela Criar Nota.")

    _selecionar_boletim_e_gravar(driver)
    numero_nota = _preencher_formulario(driver, modo, data_inicio_dt, data_fim_dt)

    return {
        "modo": modo,
        "data": data_inicio_dt.strftime("%d/%m/%Y"),
        "data_fim": data_fim_dt.strftime("%d/%m/%Y"),
        "numero_nota": numero_nota,
        "status": "OK" if numero_nota != "nao_identificado" else "NOTA_NAO_IDENTIFICADA",
    }


# ---------------------------------------------------------------------------
# Função pública
# ---------------------------------------------------------------------------

def criar_notas(itens: List[Dict], usuario: str, senha: str) -> List[Dict]:
    """
    Cria notas no SGI para cada item da lista.

    Cada item deve ter:
      - modo: "administrativo" | "operacional"
      - data: "dd/mm/aaaa"
      - data_fim: "dd/mm/aaaa"  (opcional — calculado automaticamente se omitido)

    Retorna lista com os mesmos itens acrescidos de:
      - numero_nota: str
      - status: "OK" | "NOTA_NAO_IDENTIFICADA" | "ERRO: <mensagem>"
    """
    if not itens:
        return []

    resultados = []
    driver = criar_driver()

    try:
        login_completo(driver, usuario, senha)

        for idx, item in enumerate(itens, start=1):
            print(f"\n{'='*60}")
            print(f"[LOTE] Item {idx}/{len(itens)}")
            try:
                modo = _normalizar_modo(item.get("modo", ""))
                resultado = _criar_uma_nota(
                    driver,
                    modo=modo,
                    data=item.get("data", ""),
                    data_fim=item.get("data_fim"),
                )
                resultados.append(resultado)
            except Exception as e:
                print(f"[ERRO] Item {idx}: {e}")
                resultados.append({
                    "modo": item.get("modo", ""),
                    "data": item.get("data", ""),
                    "data_fim": item.get("data_fim", ""),
                    "numero_nota": "",
                    "status": f"ERRO: {e}",
                })
    finally:
        driver.quit()

    return resultados
