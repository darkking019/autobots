import pytest
from main import run_bot

def test_sucesso_cpf():
    result = run_bot("CPF_VÁLIDO_AQUI")  # Use um CPF de teste (ex: gerado fake)
    assert "dados" in result  # Verifique JSON

# Adicione testes para erro, nome, filtro (baseado nos cenários da seção 5)