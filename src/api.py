import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv

from src.sheets import consultar_planilha
from src.bot import run_bot   # agora async e retorna dict!

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="API Consulta Portal da Transparência - Desafio mostQI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConsultaRequest(BaseModel):
    param: str
    filtro: str | None = None

class PlanilhaRequest(BaseModel):
    spreadsheet_id: str
    worksheet_name: str = "Sheet1"
    coluna_param: str = "A"
    limite: int = 50
    start_row: int = 2

FRONTEND_PATH = "frontend/index.html"

@app.post("/consultar")
async def consultar(request: ConsultaRequest):
    try:
        resultado = await run_bot(request.param, request.filtro)  # ← async direto (sem to_thread)
        return resultado
    except Exception as e:
        logger.exception("Erro na rota /consultar")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/consultar-planilha")
async def consultar_da_planilha(req: PlanilhaRequest):
    try:
        resultado = await consultar_planilha(
            spreadsheet_id=req.spreadsheet_id,
            worksheet_name=req.worksheet_name,
            coluna_param=req.coluna_param,
            limite=req.limite,
            start_row=req.start_row
        )
        return resultado
    except Exception as e:
        logger.exception("Erro na rota /consultar-planilha")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(FRONTEND_PATH)

@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str):
    if full_path.startswith(("docs", "consultar", "consultar-planilha", "openapi")):
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(FRONTEND_PATH)

if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=PORT)