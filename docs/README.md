# mostQI RPA - Portal da Transparência

**Solução RPA assíncrona robusta** para extração automatizada de dados do Portal da Transparência do Governo Federal (`portaldatransparencia.gov.br`).

---

## TL;DR

Bot RPA assíncrono em Python construído com:

- **FastAPI** + **Playwright**
- **Controle de concorrência com asyncio + Semaphore**
- **Pool compartilhado de navegadores**
- **Processamento em lote via Google Sheets**
- **Captura completa de evidências** (PNG + Base64)
- **Docker-first** com healthcheck e volumes persistentes

Projetado para extração confiável, total auditabilidade e fácil revisão.

**Deploy em produção:** [https://autobots-production-8bc0.up.railway.app/](https://autobots-production-8bc0.up.railway.app/)

---

## Visão Geral do Projeto

Este projeto implementa um bot RPA pronto para produção que:

- Consulta o Portal da Transparência por nome, CPF ou NIS
- Extrai o "Panorama da relação com o Governo Federal" e todos os detalhes de "Recebimentos de recursos"
- Gera evidências completas (screenshots físicos + Base64)
- Suporta consultas individuais e processamento em lote via Google Sheets
- Expõe API REST moderna com frontend SPA interativo

Desenvolvido com foco em confiabilidade, rastreabilidade e escalabilidade.

---

## Principais Funcionalidades

- Scraping assíncrono com Playwright (navegação estável + AJAX)
- Consultas individuais e em lote (API + Google Sheets)
- Captura completa de evidências (pastas PNG por pessoa + Base64)
- Frontend SPA moderno (Tailwind + visualizador de evidências em modal)
- Interface CLI para testes paralelos
- Deploy Docker-first com limites de recurso e healthcheck
- Logging estruturado em arquivo
- Integração Google Sheets via service account

---

## Visão Geral da Arquitetura

```ascii
                  ┌─────────────────────┐
                  │   Frontend (SPA)    │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │      FastAPI        │
                  │     (API Layer)     │
                  └──────────┬──────────┘
                             │
                     run_bot(param)
                             │
              ┌──────────────▼──────────────┐
              │  Playwright Browser Pool    │
              │  + Async Semaphore Control  │
              └──────────────┬──────────────┘
                             │
                  Portal da Transparência
Execution Flow:

FastAPI recebe a requisição
run_bot() adquire slot no semaphore
Browser context é criado a partir do pool compartilhado
Navegação + scraping + captura de screenshots
Evidências são armazenadas (físicas + Base64)
Contexto é fechado e semaphore é liberado
JSON estruturado é retornado ao cliente


```markdown
## Decisões Técnicas Importantes
Arquitetura 100% assíncrona
Todo o processamento usa asyncio + asyncio.gather() para máxima performance sem threads.
Browser Pool
Instância única do Chromium (com lock) reutilizada por todas as requisições — reduz drasticamente consumo de memória e tempo de inicialização.
Controle de Concorrência
asyncio.Semaphore(MAX_CONTEXTS) (padrão: 6, configurável via variável de ambiente).
Lógica de Retry
Backoff exponencial com jitter em todas as navegações críticas (até 5 tentativas).
Evidências e Rastreabilidade
Screenshots salvos em ./evidencia/<nome-slug>/ + Base64 em todas as respostas.
Containerização
Imagem oficial Playwright + shm_size: 2gb, healthcheck e volumes persistentes.
Integração Google Sheets
Processamento paralelo respeitando o mesmo limite de concorrência.



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
│   ├── main.py                ← CLI (argparse + CLI wrapper para execução concorrente do bot)
│   ├── bot.py                 ← função run_bot() 
│   ├── api.py                 ← FastAPI
│   ├── utils.py               ← capture_screenshot + generate_json
│   └──sheets.py
├── front/
│   └── index.html             ←  React simples (demo)
│
├── tests/
│   └── test_bot.py
│
├── data/
│   └── gerador_dados_teste.py ← gerador de dados
│

Como Executar
Deploy em Produção (Railway)
Acesse diretamente:
→ https://autobots-production-8bc0.up.railway.app/
(Swagger em /docs e frontend interativo)
Local com Docker (Recomendado)
Bash# 1. Crie o .env
echo 'GOOGLE_CREDENTIALS={"type": "service_account", ...}' > .env

# 2. Rode
docker compose up --build -d
Desenvolvimento Local
pip install -r requirements.txt


Uso da API
Consulta individual
Bashcurl -X POST https://autobots-production-8bc0.up.railway.app/consultar \
  -H "Content-Type: application/json" \
  -d '{"param": "João Silva Santos"}'
Processamento em lote via planilha (mesmo endpoint /consultar-planilha)
Evidências e Rastreabilidade
Cada execução gera:

Pasta física ./evidencia/<nome-slug>/ com screenshots numerados
Evidências Base64 no JSON (prontas para auditoria)
Logs completos em ./logs/app.log


Performance e Concorrência

Concorrência controlada em 6 contextos simultâneos (configurável)
Pool compartilhado de navegador
Testado com 49 consultas paralelas
Retries automáticos em falhas transitórias


⚠️ Limitações Conhecidas (e próximas melhorias)

Este projeto foi projetado para equilibrar robustez e simplicidade dentro do escopo de um desafio técnico.
Algumas melhorias de nível produção foram intencionalmente deixadas de fora para manter a arquitetura fácil de rodar localmente e fácil de revisar.
Melhorias potenciais (não implementadas):
Locators ainda dependem um pouco do layout do site (governo muda)
Nome dos benefícios ainda genérico em alguns casos (já identificado para próxima versão)
Filas distribuídas (Celery + RabbitMQ/Redis)
Armazenamento de evidências em objeto (S3/MinIO)
Observabilidade completa (Prometheus + OpenTelemetry)
Autoscaling horizontal de workers
Estratégias avançadas de anti-bot
instabilidade extrema em deploy(possivelmente antibots) limite de 2 na nuvem 


O que foi priorizado:

Reprodutibilidade total
Scraping determinístico
Arquitetura clara e fácil de manter
Deploy simples e rápido

📋 Relatório de Entrega
Desafios superados:

Instabilidade do portal (resolvido com retry + browser pool)
Filtro complexo (implementado com lógica inteligente)
Evidências em Base64 + PNG
Processamento paralelo sem travar

Testes cobertos: todos os 5 cenários do desafio + gerador de massa.
como rodar:
python -m pytest tests/test_bot.py -v --asyncio-mode=auto

Conclusão
criado com práticas de produção em mente, com excelente rastreabilidade e performance.
Código limpo, bem estruturado e fácil de estender.
Pronto para avaliação técnica.
Deploy ativo: https://autobots-production-8bc0.up.railway.app/

👨‍💻 Autor
Jonathan Henrique Ribeiro
Contato: jonathanhenriquers@gmail.com | www.linkedin.com/in/jonathanhenriqueribeiro


