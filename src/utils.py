import base64
from PIL import Image
from io import BytesIO
import json

def capture_screenshot(page, filename="evidencia.png"):
    """Captura screenshot e retorna Base64 + salva PNG físico"""
    try:
        screenshot_bytes = page.screenshot(full_page=True, timeout=60000, path=filename)
        img = Image.open(BytesIO(screenshot_bytes))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"DEBUG: Falha ao capturar screenshot: {e}")
        return None

def generate_json(data: dict, base64_img: str, error: str = None):
    """Gera o JSON de saída padrão do desafio"""
    return json.dumps({
        "dados": data,
        "evidencia_base64": base64_img,
        "erro": error
    }, ensure_ascii=False, indent=4)