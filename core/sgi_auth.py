"""
Funções de login no SGI compartilhadas entre criar_nota e anexos.
Extraídas de sgi_criar_nota.py e sgi_anexos_por_nota.py (lógica idêntica nos dois).
"""
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    StaleElementReferenceException,
    NoAlertPresentException,
)

SGI_URL_LOGIN = "https://sgi.pm.ma.gov.br/Login/"
DEFAULT_TIMEOUT = 30


def acessar_sgi(driver):
    print("[1] Abrindo tela de login do SGI...")
    try:
        driver.get(SGI_URL_LOGIN)
        WebDriverWait(driver, DEFAULT_TIMEOUT).until(
            EC.presence_of_element_located((By.CLASS_NAME, "login100-form"))
        )
        print("[2] Tela de login carregada.")
    except WebDriverException as e:
        print(f"\n[ERRO] Não consegui acessar o SGI. URL: {SGI_URL_LOGIN}")
        print("Detalhes técnicos:", e)
        raise


def fechar_modal_boas_vindas(driver):
    wait = WebDriverWait(driver, 5)
    try:
        print("[2.1] Verificando modal de boas-vindas...")
        ok_button = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#meumodal .modal-footer .btn-primary")
            )
        )
        ok_button.click()
        print("[2.2] Modal de boas-vindas fechado.")
        try:
            wait.until(EC.invisibility_of_element_located((By.ID, "meumodal")))
        except TimeoutException:
            pass
    except TimeoutException:
        print("[2.1] Nenhum modal visível (ok).")
    except StaleElementReferenceException:
        print("[2.1] Modal instável (stale), seguindo.")


def fazer_login(driver, usuario: str, senha: str):
    import os
    from pathlib import Path

    wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
    print("[3] Preenchendo usuário e senha...")

    usuario_input = wait.until(EC.visibility_of_element_located((By.NAME, "login_nome")))
    senha_input = wait.until(EC.visibility_of_element_located((By.NAME, "login_senha")))

    usuario_input.clear()
    usuario_input.send_keys(usuario)

    senha_input.clear()
    senha_input.send_keys(senha)

    botao = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.login100-form-btn")))
    botao.click()
    print("[3.1] Aguardando sistema carregar após login...")

    time.sleep(2)

    try:
        wait.until(lambda d: "Login" not in d.current_url)
        print("[4] Login concluído. URL:", driver.current_url)
    except TimeoutException:
        # Salva screenshot para diagnóstico
        data_dir = Path(os.environ.get("DATA_DIR", "/data"))
        screenshot_path = data_dir / "logs" / "login_falhou.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str(screenshot_path))

        # Tenta capturar mensagem de erro visível na página
        try:
            erros = driver.find_elements("css selector", ".alert, .alert-danger, .msg-erro, [class*='erro'], [class*='error']")
            msgs = [e.text.strip() for e in erros if e.text.strip()]
            if msgs:
                print(f"[ERRO LOGIN] Mensagem na página: {msgs}")
        except Exception:
            pass

        print(f"[ERRO LOGIN] URL ainda é: {driver.current_url}")
        print(f"[DIAGNÓSTICO] Screenshot salvo em: {screenshot_path}")
        raise TimeoutException(
            f"Login não redirecionou. Verifique as credenciais SGI_USUARIO/SGI_SENHA "
            f"ou acesse o screenshot em {screenshot_path}"
        )


def aceitar_alertas_se_existirem(driver, timeout_total=6, intervalo=0.3):
    fim = time.time() + timeout_total
    aceitos = 0
    while time.time() < fim:
        try:
            alert = driver.switch_to.alert
            texto = (alert.text or "").strip()
            alert.accept()
            aceitos += 1
            print(f"[ALERTA] Aceito: {texto}")
            time.sleep(0.5)
        except NoAlertPresentException:
            time.sleep(intervalo)
    return aceitos


def login_completo(driver, usuario: str, senha: str):
    """Abre o SGI, fecha modal e faz login. Função de conveniência."""
    acessar_sgi(driver)
    fechar_modal_boas_vindas(driver)
    fazer_login(driver, usuario, senha)
