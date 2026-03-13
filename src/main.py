import argparse
from concurrent.futures import ThreadPoolExecutor
from src.bot import run_bot  

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPA Portal da Transparência - CLI")
    parser.add_argument("--param", nargs="+", required=True, help="Lista de nomes/CPFs/NIS")
    parser.add_argument("--filtro", default=None, help="Filtro opcional")
    parser.add_argument("--workers", type=int, default=5, help="Número de workers paralelos")
    args = parser.parse_args()

    print(f"🚀 Iniciando {len(args.param)} consultas em paralelo...")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(lambda p: run_bot(p, args.filtro), args.param))

    for r in results:
        print(r)