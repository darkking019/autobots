import json
import gspread
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import logging

from src.bot import run_bot

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def get_gspread_client():
    creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

def consultar_planilha(
    spreadsheet_id: str,
    worksheet_name: str = "Sheet1",
    coluna_param: str = "A",
    limite: int = 50,
    start_row: int = 2
):
    client = get_gspread_client()
    
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        sheet = spreadsheet.worksheet(worksheet_name)
    except Exception as e:
        logger.exception("Erro ao abrir planilha")
        return {
            "error": f"Erro ao abrir planilha: {str(e)}",
            "processados": 0
        }

    # Lê apenas a coluna desejada
    col_index = ord(coluna_param.upper()) - ord('A') + 1
    valores = sheet.col_values(col_index)[start_row-1 : start_row-1 + limite]

    params = [v.strip() for v in valores if v.strip()]

    if not params:
        return {"error": "Nenhum dado válido encontrado na coluna", "processados": 0}

    resultados = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_param = {executor.submit(run_bot, param): param for param in params}

        for future in as_completed(future_to_param):
            param = future_to_param[future]
            try:
                resultado_str = future.result()
                data = json.loads(resultado_str)
                resultados.append({
                    "param": param,
                    "dados": data.get("dados", {}),
                    "evidencias": data.get("evidencias", []),
                    "erro": data.get("erro")
                })
            except Exception as e:
                resultados.append({
                    "param": param,
                    "erro": str(e)
                })

    return {
        "processados": len(resultados),
        "resultados": resultados,
        "mensagem": f"Processados {len(resultados)} itens da planilha"
    }