# Desenvolvimento da ETAPA 1: Sistema de Arquivos
# Simulador com alocação contígua e alocação indexada (i-node)

TAM_BLOCO = 1024
NUM_BLOCOS = 32


class Erro(Exception):
    pass


class No:
    def __init__(self, nome, eh_dir, pai):
        self.nome = nome
        self.eh_dir = eh_dir
        self.pai = pai
        self.filhos = {}      # usado só em diretório
        self.tamanho = 0      # em bytes
        self.blocos = []      # blocos de dados do arquivo
        self.indice = None    # bloco do i-node (só na alocação indexada)
        self.letra = ""       # letra do arquivo no mapa


estrategia = ""
raiz = None
atual = None
disco = []
criados = 0


# cria um disco vazio com a estratégia escolhida ('contigua' ou 'indexada')
def iniciar(nome_estrategia):
    global estrategia, raiz, atual, disco, criados
    if nome_estrategia not in ("contigua", "indexada"):
        raise Erro("estratégia inválida: " + nome_estrategia)
    estrategia = nome_estrategia
    raiz = No("", True, None)
    atual = raiz
    disco = [None] * NUM_BLOCOS
    disco[0] = raiz               # bloco 0 = diretório raiz
    criados = 0


def tam(n):
    if n >= 1024 and n % 1024 == 0:
        return str(n // 1024) + " KB"
    return str(n) + " B"


def caminho_de(no):
    if no.pai is None:
        return "/"
    pai = caminho_de(no.pai)
    return ("/" if pai == "/" else pai + "/") + no.nome


def achar(caminho):
    no = raiz if caminho.startswith("/") else atual
    for parte in caminho.split("/"):
        if parte == "" or parte == ".":
            continue
        if parte == "..":
            if no.pai is not None:
                no = no.pai
            continue
        if not no.eh_dir or parte not in no.filhos:
            raise Erro("caminho não encontrado: " + caminho)
        no = no.filhos[parte]
    return no


def achar_pai(caminho):
    caminho = caminho.rstrip("/")
    if "/" in caminho:
        pasta, nome = caminho.rsplit("/", 1)
        if pasta == "":
            pasta = "/"
    else:
        pasta, nome = ".", caminho
    pai = achar(pasta)
    if not pai.eh_dir:
        raise Erro(caminho_de(pai) + " não é um diretório")
    if nome in ("", ".", ".."):
        raise Erro("nome inválido: " + caminho)
    if nome in pai.filhos:
        raise Erro("já existe: " + caminho_de(pai.filhos[nome]))
    return pai, nome


# lista de (bloco inicial, quantidade) dos trechos livres
def buracos():
    lista = []
    i = 0
    while i < NUM_BLOCOS:
        if disco[i] is None:
            j = i
            while j < NUM_BLOCOS and disco[j] is None:
                j += 1
            lista.append((i, j - i))
            i = j
        else:
            i += 1
    return lista


def maior_buraco():
    maior = 0
    for inicio, qtd in buracos():
        if qtd > maior:
            maior = qtd
    return maior


def ocupar(arq, blocos, indice):
    arq.blocos = blocos
    arq.indice = indice
    for b in blocos:
        disco[b] = arq
    if indice is not None:
        disco[indice] = arq


def liberar(arq):
    for b in arq.blocos:
        disco[b] = None
    if arq.indice is not None:
        disco[arq.indice] = None
    arq.blocos = []
    arq.indice = None


def alocar(arq, tamanho):
    n = (tamanho + TAM_BLOCO - 1) // TAM_BLOCO
    livres = []
    for i in range(NUM_BLOCOS):
        if disco[i] is None:
            livres.append(i)

    if estrategia == "contigua":
        # first-fit: primeiro trecho livre onde cabe
        for inicio, qtd in buracos():
            if qtd >= n:
                ocupar(arq, list(range(inicio, inicio + n)), None)
                return
        if len(livres) >= n:
            raise Erro(f"fragmentação externa: há {len(livres)} blocos livres, mas o maior "
                       f"trecho tem {maior_buraco()} e o arquivo precisa de {n}")
        raise Erro("disco cheio")

    # indexada: 1 bloco de i-node + n blocos de dados, em qualquer lugar
    if len(livres) < n + 1:
        raise Erro("disco cheio")
    ocupar(arq, livres[1:n + 1], livres[0])


def mkdir(caminho):
    pai, nome = achar_pai(caminho)
    pai.filhos[nome] = No(nome, True, pai)


def cd(caminho):
    global atual
    no = achar(caminho)
    if not no.eh_dir:
        raise Erro(caminho_de(no) + " não é um diretório")
    atual = no


def criar(caminho, tamanho):
    global criados
    if tamanho <= 0:
        raise Erro("o tamanho deve ser maior que zero")
    pai, nome = achar_pai(caminho)
    arq = No(nome, False, pai)
    alocar(arq, tamanho)
    arq.tamanho = tamanho
    arq.letra = chr(ord("A") + criados % 26)
    criados += 1
    pai.filhos[nome] = arq


def ler(caminho):
    no = achar(caminho)
    if no.eh_dir:
        print("Conteúdo de " + caminho_de(no) + ":")
        for nome in sorted(no.filhos):
            f = no.filhos[nome]
            print("  " + nome + ("/ [DIR]" if f.eh_dir else " (" + tam(f.tamanho) + ") [ARQ]"))
    else:
        print(f"{caminho_de(no)}: {no.tamanho} bytes, blocos de dados {no.blocos}")


def atualizar(caminho, novo_tamanho):
    arq = achar(caminho)
    if arq.eh_dir:
        raise Erro(caminho_de(arq) + " é um diretório")
    if novo_tamanho <= 0:
        raise Erro("o tamanho deve ser maior que zero")
    antigos = (arq.blocos, arq.indice)
    liberar(arq)
    try:
        alocar(arq, novo_tamanho)
    except Erro as e:
        ocupar(arq, antigos[0], antigos[1])    # desfaz
        raise Erro("tamanho não alterado: " + str(e))
    arq.tamanho = novo_tamanho


def remover(caminho):
    no = achar(caminho)
    if no is raiz:
        raise Erro("não é possível remover a raiz")
    if no.eh_dir:
        if no.filhos:
            raise Erro("o diretório não está vazio")
        p = atual
        while p is not None:
            if p is no:
                raise Erro("não é possível remover o diretório atual")
            p = p.pai
    else:
        liberar(no)
    del no.pai.filhos[no.nome]


def mostrar_filhos(no, prefixo):
    dirs = []
    arqs = []
    for nome in sorted(no.filhos):
        if no.filhos[nome].eh_dir:
            dirs.append(nome)
        else:
            arqs.append(nome)
    nomes = dirs + arqs
    for k in range(len(nomes)):
        nome = nomes[k]
        f = no.filhos[nome]
        ultimo = (k == len(nomes) - 1)
        if ultimo:
            ramo = "└── "
        else:
            ramo = "├── "
        if f.eh_dir:
            print(prefixo + ramo + nome + "/ [DIR]")
            if ultimo:
                mostrar_filhos(f, prefixo + "    ")
            else:
                mostrar_filhos(f, prefixo + "│   ")
        else:
            print(prefixo + ramo + nome + " (" + tam(f.tamanho) + ") [ARQ]")


def arvore():
    print("[ÁRVORE DO SISTEMA DE ARQUIVOS]")
    print("/")
    mostrar_filhos(raiz, "")


def juntar_arquivos(no, achados):
    for f in no.filhos.values():
        if f.eh_dir:
            juntar_arquivos(f, achados)
        else:
            achados.append(f)


def primeiro_bloco(arq):
    if arq.indice is not None:
        return arq.indice
    return arq.blocos[0]


def todos_arquivos():
    achados = []
    juntar_arquivos(raiz, achados)
    achados.sort(key=primeiro_bloco)
    return achados


# bytes usados do bloco k do arquivo (k começa em 0)
def ocupados_no_bloco(arq, k):
    if k == len(arq.blocos) - 1:
        return arq.tamanho - k * TAM_BLOCO
    return TAM_BLOCO


def mapa_grafico():
    print("[MAPA GRÁFICO DO DISCO]")
    celulas = []
    for i in range(NUM_BLOCOS):
        d = disco[i]
        if d is None:
            c = " "
        elif d is raiz:
            c = "R"
        elif d.indice == i:
            c = "@"
        else:
            k = d.blocos.index(i)
            c = d.letra if ocupados_no_bloco(d, k) == TAM_BLOCO else d.letra.lower()
        celulas.append("[" + c + "]")
    for ini in range(0, NUM_BLOCOS, 16):
        print(f"{ini:02d}-{ini + 15:02d}: " + "".join(celulas[ini:ini + 16]))
    print("R = raiz | @ = i-node | [ ] = livre | maiúscula = bloco cheio | "
          "minúscula = bloco com fragmentação interna")
    for a in todos_arquivos():
        print(f"  {a.letra} = {caminho_de(a)}")


def fs_status(detalhes=True):
    nome_est = "Contígua" if estrategia == "contigua" else "Indexado"
    print(f"Tamanho do Bloco de Disco: {tam(TAM_BLOCO)} | "
          f"Total de Blocos: {NUM_BLOCOS} ({tam(TAM_BLOCO * NUM_BLOCOS)})")
    if detalhes:
        print()
        print(f"[MAPA DE ALOCAÇÃO DO DISCO ({nome_est})]")
        i = 0
        while i < NUM_BLOCOS:
            d = disco[i]
            if d is None:
                j = i
                while j + 1 < NUM_BLOCOS and disco[j + 1] is None:
                    j += 1
                rotulo = f"Bloco {i:02d}" if i == j else f"Bloco {i:02d}..{j:02d}"
                print(rotulo.ljust(23) + ": [LIVRE]")
                i = j + 1
                continue
            if d is raiz:
                tipo = "[INODE_RAIZ]" if estrategia == "indexada" else "[RAIZ]"
                print(f"Bloco {i:02d} {tipo}".ljust(23) + ": Diretório '/'")
            elif d.indice == i:
                tipo = "[INODE_" + d.nome.split(".")[0].upper() + "]"
                print(f"Bloco {i:02d} {tipo}".ljust(23) + f": Arquivo '{caminho_de(d)}'")
            else:
                k = d.blocos.index(i)
                print(f"Bloco {i:02d} [DADO]".ljust(23) + f": '{caminho_de(d)}' "
                      f"(Bloco {k + 1} - {ocupados_no_bloco(d, k)} bytes ocupados)")
            i += 1
        print()
        mapa_grafico()

    print()
    print("--- RELATÓRIO DE FRAGMENTAÇÃO ---")
    total_interna = 0
    for a in todos_arquivos():
        alocado = len(a.blocos) * TAM_BLOCO
        interna = alocado - a.tamanho
        total_interna += interna
        extra = f" ({tam(a.tamanho)})" if a.tamanho % 1024 == 0 else ""
        print(f"Tamanho Real do Arquivo '{a.nome}': {a.tamanho} bytes{extra}")
        print("Espaço Alocado no Disco".ljust(33) +
              f": {alocado} bytes ({len(a.blocos)} blocos de {tam(TAM_BLOCO)})")
        print("Fragmentação Interna".ljust(33) + f": {interna} bytes "
              f"({round(100 * interna / TAM_BLOCO)}% de desperdício no Bloco {a.blocos[-1]:02d})")
    print("Fragmentação Interna Total".ljust(33) + f": {total_interna} bytes")

    lista = buracos()
    if estrategia == "indexada":
        print("Fragmentação Externa".ljust(33) + ": 0 bytes")
        print("Necessidade de Compactação".ljust(33) + ": NÃO (Blocos alocados via i-node indexado)")
    elif len(lista) > 1:
        livres = 0
        for inicio, qtd in lista:
            livres += qtd
        maior = maior_buraco()
        print("Fragmentação Externa".ljust(33) + f": {(livres - maior) * TAM_BLOCO} bytes "
              f"({livres} blocos livres em {len(lista)} trechos; o maior tem {maior})")
        print("Necessidade de Compactação".ljust(33) +
              ": SIM (blocos livres dispersos)")
    else:
        print("Fragmentação Externa".ljust(33) + ": 0 bytes")
        print("Necessidade de Compactação".ljust(33) + ": NÃO (espaço livre em um único trecho)")


if __name__ == "__main__":
    print("ALOCAÇÃO INDEXADA\n")
    iniciar("indexada")
    mkdir("/sistema")
    mkdir("/sistema/logs")
    criar("/sistema/logs/app.log", 10 * 1024)
    arvore()
    print()
    cd("/sistema")
    criar("dados.txt", 2500)           # caminho relativo
    criar("logs/notas.txt", 6000)      # caminho relativo
    ler("logs")
    ler("dados.txt")
    print()
    fs_status(True)
    print("\n--- atualizar: dados.txt passa para 5000 bytes ---")
    atualizar("dados.txt", 5000)
    ler("dados.txt")
    print("\n--- remover app.log e dados.txt ---")
    remover("/sistema/logs/app.log")
    remover("/sistema/dados.txt")
    fs_status(True)

    print("\n\nALOCAÇÃO CONTÍGUA\n")
    iniciar("contigua")
    mkdir("/docs")
    criar("/docs/a.txt", 8 * 1024)
    criar("/docs/b.txt", 12 * 1024)
    criar("/docs/c.txt", 2500)
    criar("/docs/d.txt", 6000)
    fs_status(True)
    print("\n--- remover b.txt (fica um buraco no meio do disco) ---")
    remover("/docs/b.txt")
    fs_status(True)
    print("\n--- criar arquivo de 13 KB ---")
    try:
        criar("/docs/grande.bin", 13 * 1024)
    except Erro as e:
        print("Erro:", e)
