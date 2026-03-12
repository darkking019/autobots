# api.py
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()  
from src.main import run_bot
app = FastAPI(
    title="API Consulta Portal da Transparência - Desafio mostQI",
    description="Robô RPA para consulta de Pessoa Física no Portal da Transparência",
    version="1.0.0"
)
class ConsultaRequest(BaseModel):
    param: str
    filtro: str | None = None
@app.post("/consultar", response_model=dict)
async def consultar(request: ConsultaRequest):
    """
    Endpoint para consultar dados no Portal da Transparência.
    Exemplo de body:
    {
      "param": "187054551",
      "filtro": "BENEFICIÁRIO DE PROGRAMA SOCIAL"
    }
    """
    try:
        resultado = await asyncio.to_thread(run_bot, request.param, request.filtro)
        return json.loads(resultado)  # se run_bot retorna string JSON, converte para dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=PORT)