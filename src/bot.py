import json
import random
import base64
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright
import urllib.parse
import os
from pathlib import Path
import unicodedata
# ────────────────────────────────────────────────
# Configurações de retry (vindas do .env ou defaults seguros)
# Fácil de mover para um config.py depois se quiser
# ────────────────────────────────────────────────
MAX_RETRIES   = int(os.getenv("MAX_RETRIES",   3))
BASE_BACKOFF  = int(os.getenv("BASE_BACKOFF",  5))  
TIMEOUT = int(os.getenv("TIMEOUT", 9000))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# Pasta raiz
EVIDENCIA_DIR = Path("evidencia")


def slugify(text: str) -> str:
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = "".join(c if c.isalnum() or c in " -_" else "_" for c in text)
    return text.strip().replace(" ", "_").replace("__", "_")


def ensure_dir(person_name: str) -> Path:
    safe_name = slugify(person_name or "desconhecido")
    person_dir = EVIDENCIA_DIR / safe_name
    person_dir.mkdir(parents=True, exist_ok=True)
    print(f"DEBUG: Pasta criada/confirmada → {person_dir.absolute()}")
    return person_dir


def capture_screenshot_to_base64(page):
    try:
        screenshot_bytes = page.screenshot(full_page=True, timeout=60000)
        img = Image.open(BytesIO(screenshot_bytes))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"DEBUG: Falha base64: {e}")
        return None


def save_screenshot(page, person_dir: Path, filename: str):
    try:
        full_path = person_dir / f"{filename}.png"
        page.screenshot(path=str(full_path), full_page=True, timeout=60000)
        print(f"DEBUG: PNG salvo → {full_path.absolute()}")
    except Exception as e:
        print(f"DEBUG: Erro ao salvar PNG: {e}")


def accept_cookies(page):
    """Tenta aceitar cookies com espera + retry + locator preciso"""
    for tentativa in range(4):  # mais tentativas para JS demorado
        try:
            # Espera o banner ficar visível (remove d-none ou opacity baixa)
            page.wait_for_selector('#cookiebar:not(.d-none)', state='visible', timeout=8000)
            
            # Botão exato por ID e texto
            btn = page.locator('#accept-all-btn')
            if btn.is_visible(timeout=3000):
                btn.click(timeout=10000, force=True)
                print(f"DEBUG: Cookies aceitos via #accept-all-btn (tentativa {tentativa+1})")
                page.wait_for_timeout(2000)  # espera sumir
                # Verifica se sumiu
                if page.locator('#cookiebar').is_hidden(timeout=5000):
                    print("DEBUG: Banner sumiu com sucesso")
                    return True
        except Exception as e:
            print(f"DEBUG: Tentativa {tentativa+1} falhou: {str(e)}")
        page.wait_for_timeout(1500 + random.randint(500, 1500))
    
    print("DEBUG: Não conseguiu aceitar cookies ou banner não apareceu")
    return False
    # Função isolada para retry progressivo no carregamento inicial
# Motivo: sites gov.br têm latência alta e timeouts frequentes
def goto_with_retry(page, url, base_timeout=TIMEOUT, max_retries=MAX_RETRIES):
    
    for attempt in range(1, max_retries + 1):
        current_timeout = base_timeout + (attempt * 20000 )       
        print(f"🔄 Tentativa {attempt}/{max_retries} → goto {url[:80]}...")
        
        try:
            page.goto(url, timeout=current_timeout, wait_until="domcontentloaded")
            print(f"✅ Página carregada na tentativa {attempt}")
            return True
        except Exception as e:
            print(f"❌ Falha na tentativa {attempt}: {str(e)[:120]}")
            if attempt == max_retries:
                raise
            backoff = BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0, 4)
            print(f"⏳ Aguardando {backoff:.1f}s...")
            time.sleep(backoff)
    return False

def run_bot(parametro: str, filtro: str = None):
    data = {"panorama": "", "beneficios": []}
    evidencias = []
    error = None

    person_name = parametro.strip().upper()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            bypass_csp=True,
        )
        page = context.new_page()

        context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        print("DEBUG: Stealth aplicado")

        try:
            termo_encoded = urllib.parse.quote(parametro.strip())
            filtro_encoded = f"&filtro={urllib.parse.quote(filtro.strip())}" if filtro else ""
            busca_url = f"https://portaldatransparencia.gov.br/pessoa-fisica/busca/lista?termo={termo_encoded}{filtro_encoded}"

            print(f"DEBUG: Acessando → {busca_url}")
            if not goto_with_retry(page, busca_url):
    raise Exception("Falha ao carregar página de busca após todas as tentativas")
           


            # Aceita cookies logo após entrar na página de busca
            accept_cookies(page)
            page.wait_for_timeout(1000 + random.randint(1000, 2000))

            # Entra no perfil
            if "busca/lista" in page.url:
                print("DEBUG: Página de resultados")
                page.wait_for_selector('a[href^="/busca/pessoa-fisica/"]', timeout=40000)
                pessoa_link = page.locator('a[href^="/busca/pessoa-fisica/"]').first

                if pessoa_link.count() > 0:
                    person_name = pessoa_link.inner_text().strip().upper() or person_name
                    print(f"DEBUG: Pessoa detectada: {person_name}")

                    pessoa_link.scroll_into_view_if_needed()
                    page.wait_for_timeout(1200)
                    pessoa_link.hover(timeout=4000)
                    pessoa_link.click(timeout=TIMEOUT, force=True, position={"x": 12, "y": 12})
                    page.wait_for_load_state("networkidle", timeout=TIMEOUT)

                    # Aceita cookies novamente (pode aparecer na página do perfil)
                    accept_cookies(page)
                    page.wait_for_timeout(4000 + random.randint(1000, 3000))
                    print(f"DEBUG: Entrou no perfil → {page.url}")

                    person_dir = ensure_dir(person_name)

                    # Screenshot panorama
                    panorama_base64 = capture_screenshot_to_base64(page)
                    if panorama_base64:
                        evidencias.append({"tipo": "panorama", "descricao": "Perfil inicial", "base64": panorama_base64})
                    save_screenshot(page, person_dir, "01_panorama_inicial")

            # Panorama texto
            try:
                panorama_title = page.get_by_text("Panorama da relação da pessoa com o Governo Federal")
                if panorama_title.is_visible(timeout=15000):
                    container = panorama_title.locator('xpath=following-sibling::*[1]')
                    data["panorama"] = container.inner_text(timeout=TIMEOUT).strip()
                    print("DEBUG: Panorama capturado")
            except:
                data["panorama"] = "Panorama não encontrado"

            # Accordion
            accordion = page.get_by_role("button").filter(has_text="RECEBIMENTOS DE RECURSOS")
            if accordion.count() > 0:
                accordion.first.click(force=True, timeout=TIMEOUT)
                page.wait_for_timeout(4000 + random.randint(1000, 3000))
                print("DEBUG: Accordion expandido")

            # Detalhes
            detalhar_links = page.locator('a, button').filter(has_text="Detalhar")
            count = detalhar_links.count()
            print(f"DEBUG: {count} 'Detalhar' encontrados")

            person_dir = ensure_dir(person_name)

            for i in range(min(count, 8)):
                try:
                    link = detalhar_links.nth(i)
                    nome = "Benefício"
                    try:
                        nome = link.locator("xpath=preceding::strong[1]").inner_text(timeout=5000).strip()
                    except:
                        pass

                    print(f"DEBUG: Detalhe {i+1}: {nome}")

                    link.click(timeout=TIMEOUT, force=True)
                    page.wait_for_timeout(6000 + random.randint(1000, 3000))

                    # Aceita cookies novamente (pode aparecer na página de detalhe)
                    accept_cookies(page)

                    detalhes = page.locator('.br-table, main, section, .container').first.inner_text(timeout=TIMEOUT).strip() or "Sem detalhes"
                    data["beneficios"].append({"nome": nome, "detalhes": detalhes, "link": page.url})

                    detalhe_base64 = capture_screenshot_to_base64(page)
                    if detalhe_base64:
                        evidencias.append({"tipo": "beneficio", "nome": nome, "descricao": f"Detalhes {nome}", "base64": detalhe_base64})

                    save_screenshot(page, person_dir, f"{i+2:02d}_detalhe_{slugify(nome)}")

                    page.go_back()
                    page.wait_for_timeout(4000)

                except Exception as e:
                    print(f"DEBUG: Erro detalhe {i+1}: {str(e)}")
                    continue

            # Final
            final_base64 = capture_screenshot_to_base64(page)
            if final_base64:
                evidencias.append({"tipo": "final", "descricao": "Resumo final", "base64": final_base64})
            save_screenshot(page, person_dir, "99_final_resumo")

        except Exception as e:
            error = str(e)
            print(f"DEBUG: Erro geral: {str(e)}")
        finally:
            browser.close()

    result = {
        "dados": data,
        "evidencias": evidencias,
        "erro": error
    }
    return json.dumps(result, ensure_ascii=False, indent=4)
     