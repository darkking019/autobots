import argparse
import asyncio
from src.bot import run_bot  

async def run_parallel(params: list[str], filtro: str | None = None):
    """Executa todas as consultas em paralelo respeitando o semaphore interno do bot"""
    tasks = [run_bot(param, filtro) for param in params]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            print(f"❌ ERRO: {result}")
        else:
            print(result)  # já é o JSON string retornado pelo bot


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPA Portal da Transparência - CLI")
    parser.add_argument("--param", nargs="+", required=True, help="Lista de nomes/CPFs/NIS")
    parser.add_argument("--filtro", default=None, help="Filtro opcional")
    parser.add_argument("--workers", type=int, default=5, help="Número máximo de workers (controlado pelo semaphore interno)")
    args = parser.parse_args()

    print(f"🚀 Iniciando {len(args.param)} consultas em paralelo (asyncio)...")

    asyncio.run(run_parallel(args.param, args.filtro))