import json
import logging
import os
import random
import asyncio
import urllib.parse
from pathlib import Path
from unicodedata import normalize

import base64
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

# ===================== BROWSER POOL GLOBAL (ASYNC) =====================
_global_playwright = None
_global_browser = None
_global_lock = asyncio.Lock()

async def get_browser():
    global _global_playwright, _global_browser
    async with _global_lock:
        if _global_browser is None:
            logger.info("🚀 Iniciando Browser Pool Async (1 browser reutilizável)")
            _global_playwright = await async_playwright().start()
            _global_browser = await _global_playwright.chromium.launch(
                headless=os.getenv("HEADLESS", "true").lower() == "true",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
            )
        return _global_browser


# ===================== CONFIGURAÇÃO =====================
MAX_CONTEXTS = int(os.getenv("MAX_CONTEXTS", "6"))
CONTEXT_SEMAPHORE = asyncio.Semaphore(MAX_CONTEXTS)

MAX_RETRIES   = int(os.getenv("MAX_RETRIES", "5"))
BASE_BACKOFF  = int(os.getenv("BASE_BACKOFF", "3"))
TIMEOUT       = int(os.getenv("TIMEOUT", "60000"))

EVIDENCIA_DIR = Path("evidencia")
EVIDENCIA_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    text = normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = "".join(c if c.isalnum() or c in " -_" else "_" for c in text)
    return text.strip().replace(" ", "_").replace("__", "_")


def ensure_dir(person_name: str) -> Path:
    safe_name = slugify(person_name or "desconhecido")
    person_dir = EVIDENCIA_DIR / safe_name
    person_dir.mkdir(parents=True, exist_ok=True)
    return person_dir


async def capture_screenshot_to_base64(page):
    try:
        screenshot_bytes = await page.screenshot(full_page=True, timeout=30000)
        return base64.b64encode(screenshot_bytes).decode("utf-8")
    except Exception as e:
        logger.warning(f"Falha base64: {e}")
        return None


async def save_screenshot(page, person_dir: Path, filename: str):
    try:
        full_path = person_dir / f"{filename}.png"
        await page.screenshot(path=str(full_path), full_page=True, timeout=30000)
    except Exception as e:
        logger.warning(f"Erro ao salvar PNG: {e}")


async def accept_cookies(page):
    try:
        # Seletor real atual (funciona em todas as páginas)
        btn = page.get_by_text("Aceitar todos", exact=True)
        if await btn.is_visible(timeout=4000):
            await btn.click(timeout=8000)
            await page.wait_for_timeout(1500)
            logger.debug("Cookies aceitos")
    except:
        pass  


async def goto_with_retry(page, url):
    for attempt in range(1, MAX_RETRIES + 1):
        current_timeout = TIMEOUT + (attempt * 20000)
        logger.info(f"🔄 Tentativa {attempt}/{MAX_RETRIES} → goto {url[:80]}...")
        try:
            await page.goto(url, timeout=current_timeout, wait_until="domcontentloaded")
            logger.info(f"✅ Página carregada na tentativa {attempt}")
            return True
        except Exception as e:
            logger.warning(f"❌ Falha na tentativa {attempt}: {str(e)[:120]}")
            if attempt == MAX_RETRIES:
                raise
            await asyncio.sleep(BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0, 4))
    return False


async def run_bot(parametro: str, filtro: str = None):
    await CONTEXT_SEMAPHORE.acquire()
    try:
        data = {"panorama": "", "beneficios": []}
        evidencias = []
        error = None
        person_name = parametro.strip().upper()

        logger.info(f"🚀 Bot iniciado para: {parametro}")

        browser = await get_browser()
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            bypass_csp=True,
            java_script_enabled=True,
            has_touch=False,
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        try:
            # ===================== BUSCA =====================
            termo_encoded = urllib.parse.quote(parametro.strip())
            busca_url = f"https://portaldatransparencia.gov.br/pessoa-fisica/busca/lista?termo={termo_encoded}"
            if not await goto_with_retry(page, busca_url):
                raise Exception("Falha ao carregar página de busca")

            await accept_cookies(page)
            await page.wait_for_timeout(random.randint(2500, 4000))

            # ===================== ABRIR PERFIL (COM RETRY) =====================
            profile_opened = False
            for attempt in range(3):
                try:
                    await page.wait_for_selector('a[href^="/busca/pessoa-fisica/"]', timeout=15000)
                    pessoa_link = page.locator('a[href^="/busca/pessoa-fisica/"]').first
                    if await pessoa_link.count() == 0:
                        raise PlaywrightTimeout("Nenhum link encontrado")

                    person_name = (await pessoa_link.inner_text()).strip().upper() or person_name
                    await pessoa_link.scroll_into_view_if_needed()
                    await page.wait_for_timeout(random.uniform(1.5, 3.0))
                    await pessoa_link.hover()
                    await pessoa_link.click()

                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await asyncio.sleep(2.5)  # espera humana extra (anti-bot)

                    # Verificação inteligente
                    if "pessoa-fisica" in page.url and page.url != "https://portaldatransparencia.gov.br/":
                        profile_opened = True
                        break
                    else:
                        logger.warning(f"Tentativa {attempt+1}: redirect detectado → retry")
                        await page.go_back()
                except Exception as e:
                    logger.warning(f"Tentativa {attempt+1} falhou: {e}")
                    if attempt == 2:
                        raise

            if not profile_opened:
                raise Exception("Não foi possível abrir o perfil (redirect persistente)")

            # ===================== CAPTURA INICIAL =====================
            person_dir = ensure_dir(person_name)
            panorama_base64 = await capture_screenshot_to_base64(page)
            if panorama_base64:
                evidencias.append({"tipo": "panorama", "descricao": "Perfil inicial", "base64": panorama_base64})
            await save_screenshot(page, person_dir, "01_panorama_inicial")

            profile_url = page.url  # guardamos para referência

            # ===================== PANORAMA TEXTO =====================
            try:
                panorama_title = page.get_by_text("Panorama da relação da pessoa com o Governo Federal")
                if await panorama_title.is_visible(timeout=10000):
                    data["panorama"] = (await panorama_title.locator('xpath=following-sibling::*[1]').inner_text(timeout=15000)).strip()
            except:
                data["panorama"] = "Panorama não encontrado"

            # ===================== PÓS-PERFIL: COOKIES + ACCORDION + DETALHES =====================
            await accept_cookies(page)  # re-executa caso o banner apareça após abrir o perfil
            await page.wait_for_timeout(random.uniform(1.0, 2.0))

            # ===================== ABRIR ACCORDION (robusto) =====================
            try:
                await page.wait_for_selector('button:has-text("Recebimentos de recursos")', timeout=15000)
                accordion_btn = page.locator('button:has-text("Recebimentos de recursos")').first
                
                if await accordion_btn.is_visible(timeout=5000):
                    await accordion_btn.click(timeout=8000)
                    logger.info("✅ Accordion 'Recebimentos de recursos' aberto com sucesso")
                    
                    await page.wait_for_timeout(random.uniform(1.5, 2.5))
                    
                    # Screenshot do accordion aberto
                    acc_base64 = await capture_screenshot_to_base64(page)
                    if acc_base64:
                        evidencias.append({"tipo": "accordion", "descricao": "Recebimentos de recursos expandido", "base64": acc_base64})
                    await save_screenshot(page, person_dir, "02_accordion_recebimentos_expandido")
                    
                    # Espera os links Detalhar carregarem dentro do accordion
                    await page.wait_for_selector('#accordion-recebimentos-recursos a:has-text("Detalhar")', timeout=15000)
            except PlaywrightTimeout:
                logger.warning("Accordion 'Recebimentos de recursos' não encontrado ou já aberto - continuando...")
            except Exception as e:
                logger.warning(f"Erro ao abrir accordion: {e}")

# ===================== PANORAMA TEXTO =====================
            try:
                panorama_title = page.get_by_text("Panorama da relação da pessoa com o Governo Federal")
                if await panorama_title.is_visible(timeout=10000):
                    data["panorama"] = (await panorama_title.locator('xpath=following-sibling::*[1]').inner_text(timeout=15000)).strip()
            except:
                data["panorama"] = "Panorama não encontrado"

            # ===================== VERIFICAÇÃO + ABERTURA DO ACCORDION =====================
            profile_url = page.url  # ← salva para voltar depois de redirect

            accordion_aberto = False
            for tentativa in range(3):  # até 3 tentativas de abrir
                try:
                    await page.wait_for_selector('button:has-text("Recebimentos de recursos")', timeout=12000)
                    accordion_btn = page.locator('button:has-text("Recebimentos de recursos")').first

                    # Se o botão existe e está visível
                    if await accordion_btn.is_visible(timeout=5000):
                        await accordion_btn.click(delay=random.randint(200, 600))
                        await page.wait_for_timeout(random.uniform(1.2, 2.8))

                        # ✅ CONFERÊNCIA REAL: espera os links Detalhar aparecerem dentro do accordion
                        await page.wait_for_selector(
                            '#accordion-recebimentos-recursos a:has-text("Detalhar")',
                            timeout=15000,
                            state="visible"
                        )
                        logger.info(f"✅ Accordion 'Recebimentos de recursos' aberto com sucesso (tentativa {tentativa+1})")
                        accordion_aberto = True
                        break

                except Exception as e:
                    logger.warning(f"Tentativa {tentativa+1} de abrir accordion falhou: {e}")
                    await page.wait_for_timeout(1500)

            if not accordion_aberto:
                logger.error("❌ Não foi possível abrir o accordion após 3 tentativas")
                # continua mesmo assim (pode ter dados em outros lugares)

            # ===================== LOOP DETALHES – COM TRATAMENTO DE REDIRECT =====================
            for i in range(10):
                try:
                    detalhar_selector = '#accordion-recebimentos-recursos a:has-text("Detalhar"):visible'
                    await page.wait_for_selector(detalhar_selector, timeout=10000, state="visible")
                    links = page.locator(detalhar_selector)

                    if await links.count() <= i:
                        break

                    link = links.nth(i)
                    await link.wait_for(state="visible", timeout=8000)
                    await link.scroll_into_view_if_needed(timeout=8000)
                    await page.wait_for_timeout(random.uniform(800, 1800))

                    nome = (await link.locator("xpath=preceding::strong[1]").inner_text(timeout=4000)).strip() or f"Benefício {i+1}"

                    await link.click(delay=random.randint(150, 400), timeout=12000)
                    await page.wait_for_load_state("networkidle", timeout=25000)

                    # Espera conteúdo carregar
                    await page.wait_for_selector('.br-table, table, section:has-text("Valor")', timeout=15000)

                    # Tratamento de redirect
                    if not page.url.startswith("https://portaldatransparencia.gov.br/beneficios/") or "busca/lista" in page.url:
                        logger.warning(f"Redirect detectado no detalhe {i+1} → voltando para perfil")
                        await page.goto(profile_url, wait_until="networkidle", timeout=20000)
                        await page.wait_for_timeout(random.uniform(1500, 3000))
                        continue

                    # Extração
                    detalhes = (await page.locator('.br-table, main, section').first.inner_text(timeout=TIMEOUT)).strip() or "Sem detalhes"
                    data["beneficios"].append({"nome": nome, "detalhes": detalhes, "link": page.url})

                    # Screenshot
                    detalhe_base64 = await capture_screenshot_to_base64(page)
                    if detalhe_base64:
                        evidencias.append({"tipo": "beneficio", "nome": nome, "descricao": f"Detalhes {nome}", "base64": detalhe_base64})
                    await save_screenshot(page, person_dir, f"{i+3:02d}_detalhe_{slugify(nome)}")

                    # Volta para o perfil (obrigatório por causa do redirect)
                    await page.goto(profile_url, wait_until="networkidle", timeout=20000)
                    await page.wait_for_timeout(random.uniform(1200, 2800))

                except Exception as e:
                    logger.warning(f"Erro no detalhe {i+1}: {e}")
                    continue

            # ===================== FINAL =====================
            final_base64 = await capture_screenshot_to_base64(page)
            if final_base64:
                evidencias.append({"tipo": "final", "descricao": "Resumo final", "base64": final_base64})
            await save_screenshot(page, person_dir, "99_final_resumo")

        except Exception as e:
            error = str(e)
            logger.error(f"Erro geral {parametro}: {e}")
        finally:
            await context.close()

        return json.dumps({"dados": data, "evidencias": evidencias, "erro": error}, ensure_ascii=False, indent=4)

    finally:
        CONTEXT_SEMAPHORE.release()