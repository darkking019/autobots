import random

# Listas realistas de nomes brasileiros (baseadas em distribuições comuns)
primeiros_nomes_m = [
    'João', 'Pedro', 'Lucas', 'Gabriel', 'Mateus', 'Gustavo', 'Felipe', 'Rafael', 'Guilherme',
    'Enzo', 'Miguel', 'Bernardo', 'Heitor', 'Samuel', 'Davi', 'Matheus', 'Henrique', 'Theo',
    'Arthur', 'Caio'
]
primeiros_nomes_f = [
    'Maria', 'Ana', 'Julia', 'Sophia', 'Laura', 'Isabella', 'Manuela', 'Luiza', 'Valentina',
    'Giovanna', 'Helena', 'Beatriz', 'Alice', 'Lara', 'Cecilia', 'Eloa', 'Antonella', 'Isis',
    'Livia', 'Victoria'
]
sobrenomes = [
    'Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues', 'Ferreira', 'Alves', 'Pereira',
    'Lima', 'Gomes', 'Costa', 'Ribeiro', 'Martins', 'Carvalho', 'Almeida', 'Lopes', 'Soares',
    'Fernandes', 'Vieira', 'Barbosa', 'Rocha', 'Dias', 'Nunes', 'Moreira', 'Melo'
]

def gerar_nome_completo():
    """Gera um nome completo brasileiro realista"""
    genero = random.choice(['M', 'F'])
    if genero == 'M':
        primeiro = random.choice(primeiros_nomes_m)
    else:
        primeiro = random.choice(primeiros_nomes_f)
    
   
    qtd_sobrenomes = random.choices([1, 2, 3], weights=[70, 25, 5])[0]
    sobrenomes_escolhidos = random.sample(sobrenomes, qtd_sobrenomes)
    
    return f"{primeiro} {' '.join(sobrenomes_escolhidos)}"

def gerar_cpf(mascara=True):
    """Gera CPF válido (11 dígitos com verificadores corretos)"""
    # Gera os 9 primeiros dígitos
    cpf = [random.randint(0, 9) for _ in range(9)]
    
    # Evita sequências repetidas
    if len(set(cpf)) == 1:
        return gerar_cpf(mascara)  # recursão simples para rerolar
    
    # Calcula primeiro dígito verificador
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = (soma * 10) % 11
    digito1 = resto if resto < 10 else 0
    cpf.append(digito1)
    
    # Calcula segundo dígito verificador
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = (soma * 10) % 11
    digito2 = resto if resto < 10 else 0
    cpf.append(digito2)
    
    cpf_str = ''.join(map(str, cpf))
    
    if mascara:
        return f"{cpf_str[:3]}.{cpf_str[3:6]}.{cpf_str[6:9]}-{cpf_str[9:]}"
    return cpf_str

def gerar_nis(mascara=False):
    """Gera NIS/PIS/PASEP válido (11 dígitos)"""
    # Gera os 10 primeiros dígitos
    pis = [random.randint(0, 9) for _ in range(10)]
    
    # Evita sequências óbvias
    if len(set(pis)) <= 2:
        return gerar_nis(mascara)
    
    # Pesos para cálculo do dígito verificador (padrão brasileiro)
    pesos = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    
    soma = sum(pis[i] * pesos[i] for i in range(10))
    resto = soma % 11
    digito = 0 if resto < 2 else 11 - resto
    
    pis.append(digito)
    
    pis_str = ''.join(map(str, pis))
    
    if mascara:
        return f"{pis_str[:3]}.{pis_str[3:8]}.{pis_str[8:]}"
    return pis_str

def gerar_dados_teste(qtd=1):
    """Gera qtd conjuntos de dados para teste"""
    resultados = []
    for _ in range(qtd):
        nome = gerar_nome_completo()
        cpf = gerar_cpf(mascara=True)
        nis = gerar_nis(mascara=False)
        
        dados = {
            "nome": nome,
            "cpf": cpf,
            "nis": nis
        }
        resultados.append(dados)
    
    return resultados

# Exemplos de uso
if __name__ == "__main__":
    print("Exemplo de 5 conjuntos de dados para teste:\n")
    dados_gerados = gerar_dados_teste(5)
    
    for i, d in enumerate(dados_gerados, 1):
        print(f"#{i}")
        print(f"Nome: {d['nome']}")
        print(f"CPF:  {d['cpf']}")
        print(f"NIS:  {d['nis']}")
        print("-" * 50)