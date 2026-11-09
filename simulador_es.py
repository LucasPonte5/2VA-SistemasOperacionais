# Desenvolvimento da ETAPA 2: Entrada/Saída
# Usa o sistema de arquivos da Etapa 1 (simulador_so.py)
# Escalonamento do braço do disco (SSTF) e armazenamento em RAID 5

import simulador_so as fs

NUM_TRILHAS = 200
TRILHAS_POR_BLOCO = NUM_TRILHAS // fs.NUM_BLOCOS    # 200 // 32 = 6
NUM_DISCOS = 3                                      # RAID 5 com 3 discos
NUM_FAIXAS = fs.NUM_BLOCOS // 2                     # cada faixa: 2 blocos de dados + 1 de paridade

cabeca = 53
discos = []        # discos[d][faixa] = conteúdo (bytes) guardado no disco d
conteudos = {}     # conteúdo original de cada arquivo, para conferir


def iniciar(estrategia):
    global cabeca, discos, conteudos
    fs.iniciar(estrategia)
    cabeca = 53
    discos = []
    for d in range(NUM_DISCOS):
        discos.append([bytes(fs.TAM_BLOCO)] * NUM_FAIXAS)
    conteudos = {}


def trilha_do_bloco(bloco):
    return bloco * TRILHAS_POR_BLOCO


# ---------- escalonamento do braço ----------
def escalonar_sstf(trilhas, inicio, tipo="leitura/escrita"):
    print(f"[E/S] Requisições de {tipo} pendentes nas trilhas: {trilhas}")
    print(f"Posição atual da cabeça de leitura: Trilha {inicio}")
    print()
    pendentes = list(trilhas)
    pos = inicio
    ordem = [str(pos)]
    contas = []
    movimentos = []
    total = 0
    while len(pendentes) > 0:
        # pega a trilha mais próxima da cabeça
        proxima = pendentes[0]
        for t in pendentes:
            if abs(t - pos) < abs(proxima - pos):
                proxima = t
        pendentes.remove(proxima)
        mov = abs(proxima - pos)
        contas.append(f"|{pos}-{proxima}|")
        movimentos.append(str(mov))
        ordem.append(str(proxima))
        total += mov
        pos = proxima
    print("--- ESCALONAMENTO DE DISCO: SSTF (Shortest Seek Time First) ---")
    print("Ordem de Atendimento : " + " -> ".join(ordem))
    print("Deslocamento da Cabeça: " + " + ".join(contas))
    print("Total de Movimento    : " + " + ".join(movimentos) + f" = {total} trilhas")
    return pos


# ---------- RAID 5 ----------
def xor(a, b):
    r = bytearray(len(a))
    for i in range(len(a)):
        r[i] = a[i] ^ b[i]
    return bytes(r)


def disco_paridade(faixa):
    return NUM_DISCOS - 1 - faixa % NUM_DISCOS


def discos_de_dados(faixa):
    lista = []
    for d in range(NUM_DISCOS):
        if d != disco_paridade(faixa):
            lista.append(d)
    return lista


def onde(bloco):
    # em que faixa e em que disco o bloco do sistema de arquivos fica
    faixa = bloco // 2
    return faixa, discos_de_dados(faixa)[bloco % 2]


def raid_gravar(bloco, dados):
    faixa, d = onde(bloco)
    discos[d][faixa] = dados
    d1, d2 = discos_de_dados(faixa)
    discos[disco_paridade(faixa)][faixa] = xor(discos[d1][faixa], discos[d2][faixa])


def raid_ler(bloco):
    faixa, d = onde(bloco)
    return discos[d][faixa]


def mostrar_distribuicao(rotulos):
    print(f"Arranjo Ativo: RAID 5 ({NUM_DISCOS} Discos Físicos, Blocos de {fs.tam(fs.TAM_BLOCO)})")
    print()
    print("[E/S - DISTRIBUIÇÃO EM DISCO]")
    faixas = []
    for b in sorted(rotulos):
        if b // 2 not in faixas:
            faixas.append(b // 2)
    for faixa in faixas:
        for d in range(NUM_DISCOS):
            if d == disco_paridade(faixa):
                texto = f"PARIDADE : XOR(Bloco {2 * faixa:02d}, Bloco {2 * faixa + 1:02d})"
            else:
                b = 2 * faixa + discos_de_dados(faixa).index(d)
                if b in rotulos:
                    texto = f"Bloco {b:02d}: {rotulos[b]} ({fs.tam(fs.TAM_BLOCO)})"
                else:
                    texto = f"Bloco {b:02d}: (não alterado)"
            print(f"Faixa {faixa:02d} | Disco {d + 1}: [{texto}]")


def teste_falha(numero, caminho):
    arq = fs.achar(caminho)
    d = numero - 1
    print()
    print("[TESTE DE FALHA SIMULADO]")
    print(f"* Falha forçada no Disco {numero}!")
    guardado = discos[d]
    discos[d] = [bytes(fs.TAM_BLOCO)] * NUM_FAIXAS      # o disco perde tudo
    outros = []
    for x in range(NUM_DISCOS):
        if x != d:
            outros.append(x)
    tudo_ok = True
    for faixa in range(NUM_FAIXAS):
        discos[d][faixa] = xor(discos[outros[0]][faixa], discos[outros[1]][faixa])
        if discos[d][faixa] != guardado[faixa]:
            tudo_ok = False
    blocos = list(arq.blocos)
    if arq.indice is not None:
        blocos.append(arq.indice)
    encontrou = False
    for b in sorted(blocos):
        faixa, disco_do_bloco = onde(b)
        if disco_do_bloco == d:
            encontrou = True
            ok = discos[d][faixa] == guardado[faixa]
            resultado = "[OK]" if ok else "[FALHOU]"
            print(f"* Recuperando Bloco {b:02d} via operação XOR: "
                  f"(Disco {outros[0] + 1} XOR Disco {outros[1] + 1}) -> Reconstrução {resultado}")
    if not encontrou:
        print("* Nenhum bloco do arquivo estava neste disco (só paridade foi refeita)")
    resultado = "[OK]" if tudo_ok else "[FALHOU]"
    print(f"* Disco {numero} reconstruído: {NUM_FAIXAS} faixas conferidas -> {resultado}")


# ---------- integração com o sistema de arquivos ----------
def write_file(caminho, texto=None, tamanho=0):
    global cabeca
    if texto is not None:
        dados = texto.encode("utf-8")
    else:
        lista = bytearray()
        for i in range(tamanho):
            lista.append((i * 7 + 13) % 256)
        dados = bytes(lista)

    # operação do sistema de arquivos (Etapa 1)
    existe = True
    try:
        fs.achar(caminho)
    except fs.Erro:
        existe = False
    if existe:
        fs.atualizar(caminho, len(dados))
    else:
        fs.criar(caminho, len(dados))
    arq = fs.achar(caminho)
    conteudos[caminho] = dados

    # blocos que precisam ser gravados no disco
    pedidos = list(arq.blocos)
    gravar = {}
    rotulos = {}
    for k in range(len(arq.blocos)):
        pedaco = dados[k * fs.TAM_BLOCO:(k + 1) * fs.TAM_BLOCO]
        gravar[arq.blocos[k]] = pedaco.ljust(fs.TAM_BLOCO, b"\0")
        rotulos[arq.blocos[k]] = f"Dados de {arq.nome} - Part {k + 1}"
    if arq.indice is not None:
        pedidos.append(arq.indice)
        gravar[arq.indice] = bytes(arq.blocos).ljust(fs.TAM_BLOCO, b"\0")
        rotulos[arq.indice] = f"I-NODE de {arq.nome}"

    # cada bloco vira uma requisição de E/S para uma trilha
    trilhas = []
    for b in pedidos:
        trilhas.append(trilha_do_bloco(b))
    cabeca = escalonar_sstf(trilhas, cabeca, "escrita")
    print()
    for b in pedidos:
        raid_gravar(b, gravar[b])
    mostrar_distribuicao(rotulos)


def read_file(caminho):
    global cabeca
    arq = fs.achar(caminho)
    if arq.eh_dir:
        raise fs.Erro(caminho + " é um diretório")
    pedidos = []
    if arq.indice is not None:
        pedidos.append(arq.indice)      # primeiro lê o i-node
    pedidos = pedidos + list(arq.blocos)
    trilhas = []
    for b in pedidos:
        trilhas.append(trilha_do_bloco(b))
    cabeca = escalonar_sstf(trilhas, cabeca, "leitura")
    print()
    dados = b""
    for b in arq.blocos:
        dados = dados + raid_ler(b)
    dados = dados[:arq.tamanho]
    print(f"[E/S - LEITURA] {len(dados)} bytes lidos do RAID 5")
    try:
        print("Conteúdo: " + dados.decode("utf-8"))
    except UnicodeDecodeError:
        print("Conteúdo: (dados binários)")
    return dados


# ---------- demonstração ----------
if __name__ == "__main__":
    print("--- Fila de requisições da aula, cabeça na trilha 53 ---")
    escalonar_sstf([98, 183, 37, 122, 14, 124, 65, 67], 53)

    print("\n\n--- Sistema de arquivos com E/S ---")
    iniciar("indexada")
    fs.mkdir("/sistema")
    fs.mkdir("/sistema/logs")
    fs.mkdir("/dados")

    print("\n> write_file /sistema/logs/app.log --size 10KB")
    write_file("/sistema/logs/app.log", tamanho=10 * 1024)

    print("\n> write_file /dados/nota.txt \"Novo Registro\"")
    write_file("/dados/nota.txt", "Novo Registro")

    print("\n> read_file /dados/nota.txt")
    read_file("/dados/nota.txt")

    print("\n> teste de falha no Disco 2")
    teste_falha(2, "/sistema/logs/app.log")
