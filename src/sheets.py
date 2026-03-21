import json
import gspread
import asyncio
import os
import logging
from google.oauth2.service_account import Credentials

from src.bot import run_bot  # run_bot agora retorna dict!

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

def get_gspread_client():
    try:
        creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        logger.exception("Erro ao criar cliente gspread (credenciais inválidas?)")
        raise

async def consultar_planilha(
    spreadsheet_id: str,
    worksheet_name: str = "TÉCNICO",
    coluna_param: str = "A",
    limite: int = 50,
    start_row: int = 2
):
    """
    Lê params de uma coluna da planilha e executa run_bot em paralelo para cada um.
    Retorna dict com resultados processados.
    """
    client = get_gspread_client()
    
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        sheet = spreadsheet.worksheet(worksheet_name)
    except Exception as e:
        logger.exception("Erro ao abrir planilha")
        return {
            "error": f"Erro ao abrir planilha: {str(e)}",
            "processados": 0,
            "resultados": []
        }

    # Calcula índice da coluna (A=1, B=2, etc.)
    coluna_param = coluna_param.upper()
    if not ('A' <= coluna_param <= 'Z'):
        return {
            "error": f"Coluna inválida: {coluna_param}. Use A-Z.",
            "processados": 0,
            "resultados": []
        }
    
    col_index = ord(coluna_param) - ord('A') + 1
    valores = sheet.col_values(col_index)[start_row-1 : start_row-1 + limite]
    params = [v.strip() for v in valores if v.strip()]

    if not params:
        logger.info("Nenhum dado válido encontrado na coluna")
        return {
            "error": "Nenhum dado válido encontrado na coluna",
            "processados": 0,
            "resultados": []
        }

    logger.info(f"Iniciando processamento paralelo de {len(params)} parâmetros")

    # Cria tasks async para cada param
    tasks = [run_bot(param) for param in params]  # run_bot é async e retorna dict
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    resultados = []
    for i, raw in enumerate(raw_results):
        param = params[i]
        
        if isinstance(raw, Exception):
            logger.error(f"Erro ao processar {param}: {str(raw)}")
            resultados.append({
                "param": param,
                "erro": str(raw),
                "dados": {},
                "evidencias": []
            })
            continue
        
        # raw agora deve ser dict (graças à mudança no run_bot)
        if not isinstance(raw, dict):
            logger.warning(f"Retorno inesperado para {param}: tipo {type(raw)}")
            resultados.append({
                "param": param,
                "erro": f"Retorno inválido do bot (esperado dict, recebeu {type(raw)})",
                "dados": {},
                "evidencias": []
            })
            continue
        
        resultados.append({
            "param": param,
            "dados": raw.get("dados", {}),
            "evidencias": raw.get("evidencias", []),
            "erro": raw.get("erro")
        })

    logger.info(f"[DEBUG] Processados {len(resultados)} itens. Exemplo primeiro: {resultados[0] if resultados else 'vazio'}")

    return {
        "processados": len(resultados),
        "resultados": resultados,
        "mensagem": f"Processados {len(resultados)} itens da planilha"
    }