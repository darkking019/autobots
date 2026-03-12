from playwright.sync_api import sync_playwright
import base64
from PIL import Image
from io import BytesIO
import json
import argparse
import urllib.parse
import concurrent.futures

def capture_screenshot(page, filename="evidencia.png"):
    try:
        screenshot_bytes = page.screenshot(full_page=True, timeout=60000, path=filename)
        img = Image.open(BytesIO(screenshot_bytes))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"DEBUG: Falha ao capturar screenshot: {e}")
        return None



def generate_json(data, base64_img, error=None):
    return json.dumps({
        "dados": data,
        "evidencia_base64": base64_img,
        "erro": error
    }, ensure_ascii=False, indent=4)

def run_bot_instance(parametro, filtro=None):
    return run_bot(parametro, filtro)
def run_bot(parametro: str, filtro: str = None):
    data = {"panorama": "", "beneficios": []}
    error = None
    base64_img = None



    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            locale="pt-BR",
            timezone_id="America/Sao_Paulo"
        )
        page = context.new_page()

        try:
            termo_encoded = urllib.parse.quote(parametro.strip())

            # Se filtro foi passado, adiciona na query
            filtro_encoded = f"&filtro={urllib.parse.quote(filtro.strip())}" if filtro else ""
            busca_url = f"https://portaldatransparencia.gov.br/pessoa-fisica/busca/lista?termo={termo_encoded}{filtro_encoded}"
            print(f"DEBUG: Busca direta: {busca_url}")
            page.goto(busca_url, timeout=60000, wait_until="networkidle")
            page.wait_for_timeout(6000)
            print(f"DEBUG: URL carregada: {page.url}")

            # Detecta se caiu na lista de resultados
            if page.get_by_text("resultados para o termo", exact=False).count() > 0 or \
               page.get_by_text("Foram encontrados", exact=False).count() > 0:
                print("DEBUG: Página de lista detectada. Procurando link exato da pessoa...")

                # Prioriza link com nome exato + CPF/localidade se possível
                pessoa_link = page.locator(
                    'a[href*="/pessoa-fisica/"]:has-text("FATIMA TERMOS"), '
                    'a[href*="/pessoa-fisica/"]:has-text("FATIMA")'  # fallback parcial
                ).first

                if pessoa_link.count() == 0:
                    # Tenta por texto mais amplo ou primeiro da lista
                    pessoa_link = page.locator('a[href*="/pessoa-fisica/"]').first
                    if pessoa_link.count() == 0:
                        raise Exception("Nenhum link de pessoa encontrado na lista")

                print(f"DEBUG: Clicando no link da pessoa: {pessoa_link.get_attribute('href')}")
                pessoa_link.click(timeout=20000)
                page.wait_for_load_state('networkidle', timeout=40000)
                page.wait_for_timeout(5000)
                print(f"DEBUG: Entrou no perfil: {page.url}")

           
            # Panorama
            try:
                panorama_title = page.get_by_text("Panorama da relação da pessoa com o Governo Federal", exact=True)
                if panorama_title.is_visible(timeout=20000):
                    panorama_container = panorama_title.locator('xpath=following-sibling::*[1]')
                    data["panorama"] = panorama_container.inner_text(timeout=30000).strip()
                    print("DEBUG: Panorama capturado")
            except Exception as ex:
                data["panorama"] = f"Panorama não capturado: {ex}"

            # Expandir accordion
            accordion_header = page.get_by_text("Recebimentos de recursos", exact=True)
            if accordion_header.count() > 0:
                print("DEBUG: Expandindo accordion...")
                try:
                    accordion_header.click(force=True, timeout=20000)
                    page.wait_for_timeout(5000)
                    print("DEBUG: Accordion expandido")
                except Exception as e:
                    if "Nenhum link" in str(e):
                        error = f"Foram encontrados 0 resultados para o termo {parametro} com filtro {filtro or 'nenhum'}"
                    else:
                        error = f"Não foi possível retornar os dados no tempo de resposta solicitado: {e}"


            accordion_recebimentos = page.locator('#accordion-recebimentos-recursos')
            if accordion_recebimentos.count() > 0:
                accordion_recebimentos.scroll_into_view_if_needed(timeout=15000)

            # Links Detalhar
            beneficio_links = page.locator(
                '#accordion-recebimentos-recursos a.br-button.secondary.mt-3, '
                '#accordion-recebimentos-recursos a[id^="btnDetalhar"], '
                '#accordion-recebimentos-recursos a[href*="/beneficios/"], '
                'a.br-button:has-text("Detalhar"), '
                'a:has-text("Detalhar")'  
            )

            total = beneficio_links.count()
            print(f"DEBUG: Encontrados {total} links 'Detalhar'")

            if total == 0:
                print("DEBUG: Conteúdo do accordion (primeiros 2000 chars):")
                try:
                    print(accordion_recebimentos.inner_text(timeout=20000)[:2000])
                except:
                    print("Accordion vazio ou não encontrado")
                page.screenshot(path="debug-final-perfil.png")
                print("DEBUG: Screenshot salvo: debug-final-perfil.png")

            # Processa os links encontrados
            for i in range(min(total, 8)):
                try:
                    link = beneficio_links.nth(i)
                    if not link.is_visible(timeout=15000):
                        continue

                    nome = "Benefício"
                    strong = link.locator('xpath=preceding::strong[1]')
                    if strong.count() > 0:
                        nome = strong.inner_text(timeout=10000).strip()

                    href = link.get_attribute("href") or ""
                    print(f"DEBUG: Benefício {nome} → {href}")

                    link.click(timeout=25000)
                    page.wait_for_timeout(6000)

                    detalhes = ""
                    try:
                        detalhes_selector = page.locator(
                            '.br-table, .table, main, div.box-ficha__resultados, section'
                        ).first
                        if detalhes_selector.is_visible(timeout=30000):
                            detalhes = detalhes_selector.inner_text(timeout=40000).strip()
                    except:
                        detalhes = "Detalhes não capturados"

                    data["beneficios"].append({
                        "nome": nome,
                        "detalhes": detalhes or "Vazio",
                        "link": href
                    })

                    page.go_back()
                    page.wait_for_timeout(4000)
                except Exception as e:
                    print(f"Erro no benefício {i+1}: {e}")
                    continue

            base64_img = capture_screenshot(page, filename=f"evidencia_{parametro}.png")


        except Exception as e:
            error = str(e)
        finally:
            browser.close()

    return generate_json(data, base64_img, error)
import concurrent.futures
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--param", nargs="+", required=True, help="Lista de parâmetros (nomes/CPFs/NIS)")
    parser.add_argument("--filtro", default=None)
    args = parser.parse_args()
    # Executa várias buscas em paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda p: run_bot(p, args.filtro), args.param))
        
    # Imprime os resultados
    for r in results:
        print(r)