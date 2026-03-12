# api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from src.main import run_bot # Importa a função principal do bot


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
        resultado = run_bot(request.param, request.filtro)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)