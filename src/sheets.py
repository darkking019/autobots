import json
import gspread
import asyncio
import os
import logging
from google.oauth2.service_account import Credentials

from src.bot import run_bot  # run_bot deve ser async

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


async def consultar_planilha(
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
        return {"error": f"Erro ao abrir planilha: {str(e)}", "processados": 0}

    col_index = ord(coluna_param.upper()) - ord('A') + 1
    valores = sheet.col_values(col_index)[start_row-1 : start_row-1 + limite]
    params = [v.strip() for v in valores if v.strip()]

    if not params:
        return {"error": "Nenhum dado válido encontrado na coluna", "processados": 0}

    # === EXECUÇÃO PARALELA COM ASYNCIO ===
    tasks = [run_bot(param) for param in params]  # run_bot é async
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    resultados = []
    for i, raw in enumerate(raw_results):
        param = params[i]
        if isinstance(raw, Exception):
            resultados.append({"param": param, "erro": str(raw)})
        else:
            try:
                data = json.loads(raw)
                resultados.append({
                    "param": param,
                    "dados": data.get("dados", {}),
                    "evidencias": data.get("evidencias", []),
                    "erro": data.get("erro")
                })
            except Exception as e:
                resultados.append({"param": param, "erro": f"Erro ao parsear JSON: {e}"})

    return {
        "processados": len(resultados),
        "resultados": resultados,
        "mensagem": f"Processados {len(resultados)} itens da planilha"
    }
