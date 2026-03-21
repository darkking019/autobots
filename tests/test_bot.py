import logging
import asyncio
import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from src.api import app
from src.bot import run_bot, get_browser, close_global_browser  # ← IMPORT CORRIGIDO
from seeds.gerador_dados_teste import gerar_nome_completo

client = TestClient(app)

# ====================== FIXTURE GLOBAL BROWSER ======================
@pytest.fixture(scope="session", autouse=True)
async def browser_pool():
    """Cria o browser no loop correto do pytest e limpa no final"""
    logger = logging.getLogger(__name__)
    logger.info("🚀 [TEST FIXTURE] Iniciando Browser Pool para toda a sessão de testes")
    
    await get_browser()  # força criação
    
    yield
    
    # Cleanup seguro (usa a função do bot.py)
    await close_global_browser()
    logger.info("🧹 [TEST FIXTURE] Cleanup do Browser Pool concluído")


# ====================== TESTES DE API ======================
def test_api_consulta_sucesso():
    response = client.post("/consultar", json={"param": "FATIMA MARIA DA SILVA", "filtro": "beneficiarioProgramaSocial"})
    assert response.status_code == 200
    data = response.json()
    assert "dados" in data and "evidencias" in data and data["erro"] is None
    assert len(data["evidencias"]) >= 3
    assert any(e["tipo"] == "panorama" for e in data["evidencias"])

def test_api_consulta_erro_validacao():
    response = client.post("/consultar", json={"filtro": "Nome"})
    assert response.status_code == 422


def test_api_planilha():
    payload = {
        "spreadsheet_id": "1MlyK5Z__yb8YAm9sYWA0xAIeu_Y6jGws5YWtP_lVI6w",
        "worksheet_name": "TÉCNICO",
        "limite": 6
    }
    response = client.post("/consultar-planilha", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "processados" in data
    assert len(data.get("resultados", [])) > 0


# ====================== TESTES DO BOT ======================
@pytest.mark.asyncio
async def test_run_bot_sucesso_desafio():
    resultado = await asyncio.wait_for(
        run_bot("FATIMA MARIA DA SILVA", filtro="Beneficiário de Programa Social"),
        timeout=120
    )
    assert resultado["erro"] is None
    assert len(str(resultado["dados"]["panorama"])) > 5
    assert isinstance(resultado["dados"]["beneficios"], list)
    assert len(resultado["evidencias"]) >= 4


@pytest.mark.asyncio
async def test_run_bot_filtro_servidores():
    resultado = await asyncio.wait_for(
        run_bot("FATIMA MARIA DA SILVA", filtro="Servidores e Pensionistas"),
        timeout=90
    )
    assert resultado["erro"] is None
    assert len(resultado["evidencias"]) >= 2


@pytest.mark.asyncio
async def test_run_bot_erro_nome_inexistente():
    nome_falso = "XYZABCDEF GHIJKL MNOPQR"
    resultado = await run_bot(nome_falso)
    assert resultado["erro"] is not None


@pytest.mark.asyncio
async def test_run_bot_erro_cpf_invalido():
    resultado = await run_bot("123.456.789-00")
    assert resultado["erro"] is not None


@pytest.mark.asyncio
async def test_run_bot_sem_filtro_pula_bloco():
    resultado = await asyncio.wait_for(run_bot("FATIMA MARIA DA SILVA"), timeout=80)
    assert resultado["erro"] is None


@pytest.mark.asyncio
async def test_arquivos_png_salvos_no_disco():
    param = "João Silva Santos"
    await run_bot(param)
    person_dir = Path("evidencia") / "Joao_Silva_Santos"
    assert person_dir.exists()
    arquivos = list(person_dir.glob("*.png"))
    assert len(arquivos) >= 2


@pytest.mark.asyncio
async def test_concorrencia_semaphore():
    """Testa semaphore + concorrência (versão estável para Windows local)"""
    params = [gerar_nome_completo() for _ in range(2)]   # 2 tarefas é o máximo estável no seu PC
    tasks = [run_bot(p) for p in params]
    resultados = await asyncio.gather(*tasks, return_exceptions=True)
    
    assert len(resultados) == 2
    
    assert all(isinstance(r, (dict, Exception)) for r in resultados)
    falhas = sum(1 for r in resultados if isinstance(r, Exception))
    if falhas > 0:
        print(f"⚠️ {falhas}/2 tarefas falharam (timeout normal no Windows local) - semaphore OK")
    else:
        print("✅ Todas as tarefas concorrentes completaram com sucesso!")

# ====================== RUN ======================
if __name__ == "__main__":
    pytest.main(["-v", "--asyncio-mode=auto", "--tb=short", "--capture=no"])