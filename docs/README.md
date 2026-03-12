# Desafio mostQI - RPA + Hiperautomação (Portal da Transparência)

**Desafio Full Stack Python** – Parte 1 (obrigatória) + Parte 2 (bônus)  
Repositório: https://github.com/darkking019/autobots.git

## ✨ O que foi entregue 

- ✅ RPA completo com **Playwright** (headless + paralelo)
- ✅ Tratamento exato dos 5 cenários de teste do desafio
- ✅ Evidência em **Base64 + PNG físico**
- ✅ **API REST** com FastAPI (deploy Railway)
- ✅ **Docker** + Dockerfile otimizado
- ✅ Frontend simples (React via CDN) consumindo a API
- ✅ Gerador de CPFs/NIS/nomes brasileiros válidos para testes
- ✅ Execução paralela com `ThreadPoolExecutor`
- ✅ Testes unitários (base)

**Deploy ao vivo**:  
API → https://autobots-production-8bc0.up.railway.app  
Frontend demo → abra o `frontend/index.html`

## 🚀 Como rodar

### 1. Local (CLI)
```bash
pip install -r requirements.txt
playwright install chromium
python src/main.py --param "FATIMA TERMOS" "JOÃO SILVA" "187054551"
2. API Local
python -m uvicorn src.api:app --reload --host 127.0.0.1 --port 8000

# Teste: http://localhost:8000/docs (Swagger)
3. Docker
Bashdocker build -t mostqi-rpa .
docker run --rm mostqi-rpa --param "187054551"
4. Frontend
Abra frontend/index.html no navegador (já aponta para o deploy).
📂 Estrutura do Projeto
Hiperautomacao/
├── README.md                 
├── requirements.txt
├── Dockerfile
├── .env.example
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── main.py                ← CLI (argparse + ThreadPool)
│   ├── bot.py                 ← função run_bot() pura (extraia do main)
│   ├── api.py                 ← FastAPI
│   └── utils.py               ← capture_screenshot + generate_json
│
├── frontend/
│   └── index.html             ← seu React simples (demo)
│
├── tests/
│   └── test_bot.py
│
├── data/
│   └── gerador_dados_teste.py ← gerador de dados
│

🛠️ Decisões Técnicas

Playwright → escolha oficial do desafio + mais estável que Selenium.
FastAPI → moderna, async-ready, Swagger automático.
Docker → garantiu portabilidade .
ThreadPoolExecutor → execução simultânea de múltiplos bots .
Evidência dupla (Base64 + PNG) → confiabilidade em auditoria.

📋 Relatório de Entrega

Desafios enfrentados: instabilidade leve do site e falta de clareza de onde estavam divs no f12 para recuperar os dados necessarios para fazer a busca com os bots.

Testes cobertos: todos os 5 cenários do desafio + gerador de massa.

👨‍💻 Autor
Jonathan Henrique Ribeiro
Contato: jonathanhenriquers@gmail.com | www.linkedin.com/in/jonathanhenriqueribeiro


