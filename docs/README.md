# Desafio Full Stack Python - Parte 1

Este projeto implementa um **robô RPA em Python** utilizando [Playwright](https://playwright.dev/python/) para automatizar consultas no [Portal da Transparência](https://portaldatransparencia.gov.br).  
O objetivo é buscar informações de pessoas físicas, capturar evidências e retornar os dados em formato JSON.

---

## 🚀 Funcionalidades

- Execução simultânea de múltiplas consultas (ThreadPoolExecutor).
- Captura de **evidência em Base64** para o JSON e **arquivo físico `.png`** para conferência.
- Tratamento de erros com mensagens claras:
  - Nenhum resultado encontrado.
  - Timeout ou falha de carregamento.
- Extração de:
  - Panorama da relação da pessoa com o Governo Federal.
  - Benefícios recebidos (nome, detalhes, link).
- Saída estruturada em JSON.

---

## 📂 Estrutura do Projeto

src/
├── main.py              # Ponto de entrada (argparse, executor paralelo)
├── bot.py               # Função run_bot e lógica Playwright
├── utils.py             # Funções auxiliares (screenshot, JSON)
└── requirements.txt     # Dependências

Código

---

## ⚙️ Requisitos

- Python 3.10+
- Playwright
- Pillow

Instalação das dependências:

```bash
pip install -r requirements.txt
playwright install
▶️ Como Executar
Rodar múltiplas consultas em paralelo:

bash
python src/main.py --param "FATIMA TERMOS" "JOÃO SILVA" "MARIA OLIVEIRA" --filtro "BENEFICIÁRIO DE PROGRAMA SOCIAL"
📤 Exemplo de Saída
json
{
    "dados": {
        "panorama": "RECEBIMENTOS DE RECURSOS",
        "beneficios": [
            {
                "nome": "Auxílio Emergencial",
                "detalhes": "Detalhes do benefício...",
                "link": "/beneficios/auxilio-emergencial/187054551"
            }
        ]
    },
    "evidencia_base64": "iVBORw0KGgoAAAANSUhEUgAABQAAA...",
    "erro": null
}
🛡️ Tratamento de Erros
"erro": "Foram encontrados 0 resultados para o termo JOÃO SILVA com filtro BENEFICIÁRIO DE PROGRAMA SOCIAL"

"erro": "Não foi possível retornar os dados no tempo de resposta solicitado"

📑 Decisões Técnicas
Playwright escolhido pela robustez em automação web headless.

Execução paralela com ThreadPoolExecutor para suportar múltiplas consultas.

Evidência dupla (Base64 + arquivo físico) para confiabilidade.

Mensagens de erro padronizadas para facilitar testes e validação.

# Desafio mostQI - RPA Hiperautomação

## Como rodar

### Local
pip install -r requirements.txt
playwright install chromium
python src/cli.py --param "FATIMA TERMOS"

### Docker
docker build -t mostqi-rpa .
docker run --rm mostqi-rpa --param "187054551"
## Parte 2 – Hiperautomação (Bônus)

### API REST
Implementei uma API mínima com **FastAPI** expondo o endpoint:

POST /consultar

Body exemplo:
```json
{
  "param": "187054551",
  "filtro": "BENEFICIÁRIO DE PROGRAMA SOCIAL"
}
👨‍💻 Autor
Jonathan Henrique Ribeiro  


