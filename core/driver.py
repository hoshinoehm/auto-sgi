"""
Cria o WebDriver do Chrome com suporte a modo headless via variáveis de ambiente.

Variáveis de ambiente relevantes:
  HEADLESS        true|false  (padrão: true)
  CHROME_BIN      caminho para o binário do Chrome/Chromium
  CHROMEDRIVER_PATH  caminho para o chromedriver (se omitido, usa webdriver-manager)
"""
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def criar_driver() -> webdriver.Chrome:
    headless = os.environ.get("HEADLESS", "true").lower() == "true"

    options = Options()

    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin

    if headless:
        options.add_argument("--headless=new")

    # Segurança / sandbox
    options.add_argument("--no-sandbox")
    options.add_argument("--no-zygote")               # evita crash do processo zygote em containers Docker
    options.add_argument("--disable-dev-shm-usage")  # usa /tmp em vez de /dev/shm (evita crash por falta de memória compartilhada)

    # Redução de uso de memória
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-features=TranslateUI,BlinkGenPropertyTrees")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--renderer-process-limit=1")
    options.add_argument("--disable-cache")
    options.add_argument("--disk-cache-size=0")
    options.add_argument("--media-cache-size=0")
    options.add_argument("--aggressive-cache-discard")
    options.add_argument("--disable-application-cache")
    options.add_argument("--js-flags=--max-old-space-size=128")

    # Evita que o SGI detecte o Chromium como bot
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
    if chromedriver_path:
        service = Service(chromedriver_path)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())

    return webdriver.Chrome(service=service, options=options)
