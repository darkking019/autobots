import json
import logging
import os
import random
import asyncio
import urllib.parse
from pathlib import Path
from unicodedata import normalize

import base64
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# ===================== CLEANUP GLOBAL BROWSER (OBRIGATÓRIO PARA TESTES) =====================
# ===================== GLOBAL BROWSER POOL + CLEANUP (VERSÃO FINAL) =====================
_global_playwright = None
_global_browser = None
_global_lock = None

async def get_browser():
    """Browser global à prova de falhas + recriação automática"""
    global _global_playwright, _global_browser, _global_lock

    if _global_lock is None:
        _global_lock = asyncio.Lock()

    async with _global_lock:
        # Recria se morreu (canal None ou fechado)
        needs_recreate = (
            _global_browser is None or
            getattr(_global_browser, '_channel', None) is None
        )

        if needs_recreate:
            logger.info("🔄 [BROWSER POOL] Recriando browser global...")
            if _global_playwright:
                try:
                    await _global_playwright.stop()
                except:
                    pass
            _global_playwright = await async_playwright().start()
            _global_browser = await _global_playwright.chromium.launch(
                headless=os.getenv("HEADLESS", "true").lower() == "true",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
            )
            logger.info("✅ Browser global recriado com sucesso!")

        if _global_browser is None:
            raise RuntimeError("❌ Browser global falhou ao inicializar!")

        return _global_browser


async def close_global_browser():
    """Fecha o browser global com segurança (usado no fixture de teste)"""
    global _global_browser, _global_playwright
    logger = logging.getLogger(__name__)
    
    if _global_browser:
        try:
            await _global_browser.close()
            _global_browser = None
            logger.info("✅ [CLEANUP] Browser global fechado")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao fechar browser: {e}")
    
    if _global_playwright:
        try:
            await _global_playwright.stop()
            _global_playwright = None
            logger.info("✅ [CLEANUP] Playwright parado")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao parar playwright: {e}")
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
            # Busca Inicial
            busca_url = f"https://portaldatransparencia.gov.br/pessoa-fisica/busca/lista?termo={urllib.parse.quote(parametro.strip())}"
            await goto_with_retry(page, busca_url)
            await accept_cookies(page)
            await page.wait_for_timeout(3000)

            # ==============================================================
            #  APLICAÇÃO DE FILTROS INTELIGENTE (aceita ID OU texto do label)
            # ==============================================================
            if filtro:
                logger.info(f"Aplicando filtros de busca: {filtro}")
                
                filtros_lista = [f.strip() for f in filtro.split(",") if f.strip()]
                filtro_aplicado_com_sucesso = False

                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        logger.info(f"🔄 Tentativa {attempt}/{MAX_RETRIES} de aplicar filtros")

                        # 1. Garantir que o box #box-busca-refinada está aberto
                        refine_box = page.locator('#box-busca-refinada')
                        if not await refine_box.is_visible(timeout=4000):
                            btn_refinar = page.locator(
                                'button[aria-controls="box-busca-refinada"], '
                                'button:has-text("Refine a Busca"), '
                                'button:has-text("refinar")'
                            ).first
                            if await btn_refinar.is_visible(timeout=5000):
                                await btn_refinar.click(force=True)
                                await page.wait_for_timeout(1200)
                            await refine_box.wait_for(state="visible", timeout=8000)
                            logger.debug("✅ Box 'Refine a Busca' aberto")

                        # 2. Resolver cada filtro de forma inteligente (ID ou texto do label)
                        falhas = []
                        for user_input in filtros_lista:
                            logger.debug(f"🔍 Resolvendo filtro: '{user_input}'")

                            # Tenta como ID direto primeiro
                            direct_checkbox = page.locator(f'#{user_input}')
                            if await direct_checkbox.count() > 0:
                                label = page.locator(f'label[for="{user_input}"]')
                                await label.click(force=True)
                                await page.wait_for_timeout(500)
                                if await direct_checkbox.is_checked():
                                    logger.debug(f"✅ '{user_input}' (ID direto) marcado")
                                    continue
                                else:
                                    falhas.append(user_input)
                                    continue

                            # Tenta como texto do label (suporte a "Beneficiário de Programa Social")
                            label_locator = page.locator(
                                f'#box-busca-refinada label:has-text("{user_input}")'
                            ).first
                            if await label_locator.count() > 0:
                                await label_locator.click(force=True)
                                await page.wait_for_timeout(500)
                                fid = await label_locator.get_attribute('for')
                                checkbox = page.locator(f'#{fid}')
                                if await checkbox.is_checked():
                                    logger.debug(f"✅ '{user_input}' → #{fid} marcado")
                                    continue
                                else:
                                    falhas.append(user_input)
                            else:
                                falhas.append(user_input)

                        if falhas:
                            raise Exception(f"Filtros não encontrados/marcados: {falhas}")

                        # 3. Clicar em Consultar
                        btn_consultar = page.locator('#btnConsultarPF')
                        await btn_consultar.click(force=True)
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        await page.wait_for_timeout(3000)

                        filtro_aplicado_com_sucesso = True
                        logger.info(f"✅ Filtro aplicado com sucesso na tentativa {attempt}")
                        break

                    except Exception as e:
                        logger.warning(f"Tentativa {attempt} falhou: {str(e)[:150]}")
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0.5, 2))

                if not filtro_aplicado_com_sucesso:
                    logger.warning("⚠️ Não foi possível aplicar o filtro após todas as tentativas. Continuando busca SEM filtro.")

            # ==============================================================

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

        return {
            "dados": data,
            "evidencias": evidencias,
            "erro": error
        }

    finally:
        CONTEXT_SEMAPHORE.release()