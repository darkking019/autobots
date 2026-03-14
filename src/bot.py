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

# ===================== GLOBAL BROWSER POOL =====================
_global_playwright = None
_global_browser = None
_global_lock = asyncio.Lock()

async def get_browser():
    global _global_playwright, _global_browser
    async with _global_lock:
        if _global_browser is None:
            logger.info("🚀 Iniciando Browser Pool Async")
            _global_playwright = await async_playwright().start()
            _global_browser = await _global_playwright.chromium.launch(
                headless=os.getenv("HEADLESS", "true").lower() == "true",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
            )
        return _global_browser

# ===================== CONFIG =====================
MAX_CONTEXTS = int(os.getenv("MAX_CONTEXTS", "6"))
CONTEXT_SEMAPHORE = asyncio.Semaphore(MAX_CONTEXTS)

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
BASE_BACKOFF = int(os.getenv("BASE_BACKOFF", "3"))
TIMEOUT = int(os.getenv("TIMEOUT", "60000"))

EVIDENCIA_DIR = Path("evidencia")
EVIDENCIA_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    text = normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = "".join(c if c.isalnum() or c in " -_" else "_" for c in text)
    return text.strip().replace(" ", "_").replace("__", "_")


def ensure_dir(person_name: str) -> Path:
    safe_name = slugify(person_name or "desconhecido")
    dir_path = EVIDENCIA_DIR / safe_name
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


async def capture_screenshot_to_base64(page):
    try:
        return base64.b64encode(await page.screenshot(full_page=True, timeout=30000)).decode("utf-8")
    except Exception as e:
        logger.warning(f"Falha screenshot base64: {e}")
        return None


async def save_screenshot(page, person_dir: Path, filename: str):
    try:
        await page.screenshot(path=str(person_dir / f"{filename}.png"), full_page=True, timeout=30000)
    except Exception as e:
        logger.warning(f"Erro salvar PNG: {e}")


async def accept_cookies(page):
    try:
        btn = page.get_by_text("Aceitar todos", exact=True)
        if await btn.is_visible(timeout=5000):
            await btn.click(timeout=8000)
            await page.wait_for_timeout(1200)
            logger.debug("Cookies aceitos")
    except:
        pass


async def goto_with_retry(page, url: str):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await page.goto(url, timeout=TIMEOUT + attempt * 15000, wait_until="domcontentloaded")
            return True
        except Exception as e:
            logger.warning(f"Goto falhou (tentativa {attempt}): {str(e)[:100]}")
            if attempt == MAX_RETRIES:
                raise
            await asyncio.sleep(BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0.5, 3))
    return False


async def run_bot(parametro: str, filtro: str = None):
    await CONTEXT_SEMAPHORE.acquire()
    try:
        data = {"panorama": "", "beneficios": []}
        evidencias = []
        error = None
        person_name = parametro.strip().upper()

        logger.info(f"🚀 Iniciando bot para: {parametro}")

        browser = await get_browser()
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            bypass_csp=True,
            java_script_enabled=True,
            service_workers="block",
            has_touch=False,
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

        try:
            # Busca + Abrir Perfil
            busca_url = f"https://portaldatransparencia.gov.br/pessoa-fisica/busca/lista?termo={urllib.parse.quote(parametro.strip())}"
            await goto_with_retry(page, busca_url)
            await accept_cookies(page)
            await page.wait_for_timeout(3000)

            # Abrir perfil com retry
            for attempt in range(3):
                try:
                    await page.wait_for_selector('a[href^="/busca/pessoa-fisica/"]', timeout=15000)
                    link = page.locator('a[href^="/busca/pessoa-fisica/"]').first
                    await link.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    if "pessoa-fisica" in page.url:
                        break
                    await page.go_back()
                except Exception as e:
                    logger.warning(f"Perfil tentativa {attempt+1} falhou")
                    if attempt == 2:
                        raise
                    await page.wait_for_timeout(2000)

            person_dir = ensure_dir(person_name)

            # Screenshot inicial + Panorama
            if base64_img := await capture_screenshot_to_base64(page):
                evidencias.append({"tipo": "panorama", "descricao": "Perfil inicial", "base64": base64_img})
            await save_screenshot(page, person_dir, "01_panorama_inicial")

            try:
                title = page.get_by_text("Panorama da relação da pessoa com o Governo Federal")
                if await title.is_visible(timeout=8000):
                    data["panorama"] = (await title.locator("xpath=following-sibling::*[1]").inner_text(timeout=10000)).strip()
            except:
                data["panorama"] = "Panorama não encontrado"

            await accept_cookies(page)

            # Accordion com retry
            accordion_aberto = False
            for _ in range(3):
                try:
                    btn = page.locator('button:has-text("Recebimentos de recursos")').first
                    if await btn.is_visible(timeout=10000):
                        await btn.click(delay=400)
                        await page.wait_for_selector('#loadingcollapse-3', state="hidden", timeout=10000)
                        await page.wait_for_selector('#accordion-recebimentos-recursos a:has-text("Detalhar")', 
                                                    timeout=15000, state="visible")
                        accordion_aberto = True
                        break
                except:
                    await page.wait_for_timeout(1800)

            if accordion_aberto:
                await page.wait_for_timeout(1500)
                if base64_img := await capture_screenshot_to_base64(page):
                    evidencias.append({"tipo": "accordion", "descricao": "Recebimentos de recursos expandido", "base64": base64_img})
                await save_screenshot(page, person_dir, "02_accordion_recebimentos_expandido")

            # Coletar links (com scroll para forçar renderização completa)
            await page.mouse.wheel(0, 2500)
            await page.wait_for_timeout(1200)
            await page.mouse.wheel(0, 2500)
            await page.wait_for_timeout(1500)

            locator = page.locator('#accordion-recebimentos-recursos a').filter(has_text="Detalhar")
            raw_links = await locator.evaluate_all("els => els.map(e => e.href)")
            links = list(dict.fromkeys(
                [link if link.startswith("http") else f"https://portaldatransparencia.gov.br{link}" 
                 for link in raw_links if link]
            ))
            logger.info(f"✅ {len(links)} links Detalhar coletados")

            # Processar detalhes (navegação estável + espera AJAX completa)
            for i, link in enumerate(links):
                try:
                    logger.info(f"Processando detalhe {i+1}/{len(links)}")
                    await goto_with_retry(page, link)
                    await accept_cookies(page)
                    await page.wait_for_load_state("networkidle", timeout=12000)
                    await page.wait_for_timeout(random.randint(2500, 3800))

                    detalhes = await page.locator('.br-table, table, .box-ficha__resultados, main').first.inner_text(timeout=15000)

                    data["beneficios"].append({
                        "nome": f"Beneficio {i+1}",
                        "detalhes": detalhes.strip(),
                        "link": link
                    })

                    if base64_img := await capture_screenshot_to_base64(page):
                        evidencias.append({
                            "tipo": "beneficio",
                            "nome": f"Beneficio {i+1}",
                            "descricao": f"Detalhes beneficio {i+1}",
                            "base64": base64_img
                        })
                    await save_screenshot(page, person_dir, f"{i+3:02d}_detalhe")

                except Exception as e:
                    logger.warning(f"Erro detalhe {i+1}: {e}")

            # Final
            if base64_img := await capture_screenshot_to_base64(page):
                evidencias.append({"tipo": "final", "descricao": "Resumo final", "base64": base64_img})
            await save_screenshot(page, person_dir, "99_final_resumo")

        except Exception as e:
            error = str(e)
            logger.error(f"Erro geral: {e}")
        finally:
            await context.close()

        return json.dumps({"dados": data, "evidencias": evidencias, "erro": error}, ensure_ascii=False, indent=4)

    finally:
        CONTEXT_SEMAPHORE.release()