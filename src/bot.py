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
    for _ in range(4):
        try:
            await page.wait_for_selector('#cookiebar:not(.d-none)', state='visible', timeout=8000)
            btn = page.locator('#accept-all-btn')
            if await btn.is_visible(timeout=3000):
                await btn.click(timeout=10000, force=True)
                await page.wait_for_timeout(2000)
                if await page.locator('#cookiebar').is_hidden(timeout=5000):
                    return True
        except:
            pass
        await page.wait_for_timeout(1500 + random.randint(500, 1500))
    return False


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

        logger.info(f"🚀 Bot Async iniciado para: {parametro} (contextos simultâneos: {MAX_CONTEXTS})")

        browser = await get_browser()
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            bypass_csp=True,
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        logger.debug("Stealth aplicado")

        try:
            termo_encoded = urllib.parse.quote(parametro.strip())
            filtro_encoded = f"&filtro={urllib.parse.quote(filtro.strip())}" if filtro else ""
            busca_url = f"https://portaldatransparencia.gov.br/pessoa-fisica/busca/lista?termo={termo_encoded}{filtro_encoded}"

            if not await goto_with_retry(page, busca_url):
                raise Exception("Falha ao carregar página de busca")

            await accept_cookies(page)
            await page.wait_for_timeout(random.randint(2500, 4000))

            if "busca/lista" in page.url:
                try:
                    await page.wait_for_selector('a[href^="/busca/pessoa-fisica/"]', timeout=15000)
                except PlaywrightTimeout:
                    logger.warning(f"Nenhum resultado para {parametro}")
                    error = f"Nenhum resultado encontrado para '{parametro}'"
                else:
                    pessoa_link = page.locator('a[href^="/busca/pessoa-fisica/"]').first
                    if await pessoa_link.count() > 0:
                        person_name = (await pessoa_link.inner_text()).strip().upper() or person_name
                        await pessoa_link.scroll_into_view_if_needed()
                        await page.wait_for_timeout(1200)
                        await pessoa_link.hover()
                        await pessoa_link.click(force=True)
                        await page.wait_for_load_state("networkidle", timeout=TIMEOUT)

                        person_dir = ensure_dir(person_name)
                        panorama_base64 = await capture_screenshot_to_base64(page)
                        if panorama_base64:
                            evidencias.append({"tipo": "panorama", "descricao": "Perfil inicial", "base64": panorama_base64})
                        await save_screenshot(page, person_dir, "01_panorama_inicial")

            # Panorama texto
            try:
                panorama_title = page.get_by_text("Panorama da relação da pessoa com o Governo Federal")
                if await panorama_title.is_visible(timeout=15000):
                    data["panorama"] = (await panorama_title.locator('xpath=following-sibling::*[1]').inner_text(timeout=TIMEOUT)).strip()
            except:
                data["panorama"] = "Panorama não encontrado"

            # Accordion inicial
            accordion = page.get_by_role("button").filter(has_text="RECEBIMENTOS DE RECURSOS")
            if await accordion.count() > 0:
                await accordion.first.click(force=True)
                await page.wait_for_timeout(random.randint(2500, 3500))

            # === LOOP DETALHES ===
            for i in range(8):
                try:
                    detalhar_links = page.locator('a.br-button.secondary:has-text("Detalhar")')
                    count = await detalhar_links.count()
                    if i >= count:
                        break

                    link = detalhar_links.nth(i)

                    if not await link.is_visible(timeout=3000):
                        await page.mouse.wheel(0, random.randint(400, 700))
                        await page.wait_for_timeout(1200)
                        if not await link.is_visible(timeout=3000):
                            logger.warning(f"Detalhar {i+1} ainda invisível → pulando")
                            continue

                    nome = "Benefício"
                    try:
                        nome = (await link.locator("xpath=preceding::strong[1]").inner_text(timeout=3000)).strip()
                    except:
                        pass

                    logger.debug(f"Detalhe {i+1}: {nome}")

                    await link.scroll_into_view_if_needed(timeout=8000)
                    await page.mouse.move(random.randint(200, 600), random.randint(200, 500))
                    await page.wait_for_timeout(random.uniform(1.2, 2.8))

                    await link.click(timeout=15000, force=True)
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await page.wait_for_timeout(random.randint(2000, 3500))
                    await accept_cookies(page)

                    detalhes = (await page.locator('.br-table, main, section').first.inner_text(timeout=TIMEOUT)).strip() or "Sem detalhes"
                    data["beneficios"].append({"nome": nome, "detalhes": detalhes, "link": page.url})

                    detalhe_base64 = await capture_screenshot_to_base64(page)
                    if detalhe_base64:
                        evidencias.append({"tipo": "beneficio", "nome": nome, "descricao": f"Detalhes {nome}", "base64": detalhe_base64})
                    await save_screenshot(page, ensure_dir(person_name), f"{i+2:02d}_detalhe_{slugify(nome)}")

                    await page.go_back()
                    await page.wait_for_load_state("networkidle", timeout=10000)

                    accordion = page.get_by_role("button").filter(has_text="RECEBIMENTOS DE RECURSOS")
                    if await accordion.count() > 0:
                        if await accordion.first.get_attribute("aria-expanded") == "false":
                            await accordion.first.click(force=True)
                            await page.wait_for_timeout(1500)

                    await page.wait_for_timeout(random.randint(1500, 2500))

                except Exception as e:
                    logger.warning(f"Erro detalhe {i+1}: {e}")
                    continue

            # Screenshot final
            final_base64 = await capture_screenshot_to_base64(page)
            if final_base64:
                evidencias.append({"tipo": "final", "descricao": "Resumo final", "base64": final_base64})
            await save_screenshot(page, ensure_dir(person_name), "99_final_resumo")

        except Exception as e:
            error = str(e)
            logger.error(f"Erro geral {parametro}: {e}")
        finally:
            await context.close()

        return json.dumps({"dados": data, "evidencias": evidencias, "erro": error}, ensure_ascii=False, indent=4)

    finally:
        CONTEXT_SEMAPHORE.release()