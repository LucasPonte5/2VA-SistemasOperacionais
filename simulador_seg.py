# Desenvolvimento da ETAPA 3: Segurança e Proteção
# Usa a Etapa 2 (simulador_es.py), que usa a Etapa 1 (simulador_so.py)

import contextlib
import hashlib
import io
import os

import simulador_es as es
import simulador_so as fs

MODO_USUARIO = "MODO_USUARIO"
MODO_KERNEL = "MODO_KERNEL"
ASSINATURAS = ["MALWARE_TESTE", "EICAR-STANDARD-ANTIVIRUS-TEST-FILE", "rm -rf /"]
MOSTRAR_ES = False      # True mostra o escalonamento e o RAID de cada operação

BITS = {"r": 4, "w": 2, "x": 1}
NOMES_ACAO = {"r": "LEITURA", "w": "ESCRITA", "x": "EXECUÇÃO"}
PALAVRA_ACAO = {"r": "leitura", "w": "escrita", "x": "execução"}

usuarios = {}     # nome -> salt, hash da senha e grupo
grupos = []
meta = {}         # caminho absoluto -> dono, grupo, permissões, criptografia
registro = {}     # bloco -> hash SHA-256 guardado na gravação
log = []
sessao = None     # usuário logado: nome, grupo e modo


def iniciar(estrategia, senha_root):
    global usuarios, grupos, meta, registro, log, sessao
    es.iniciar(estrategia)
    usuarios = {}
    grupos = ["admin"]
    meta = {}
    registro = {}
    log = []
    sessao = None
    usuarios["root"] = novo_usuario(senha_root, "admin")
    meta["/"] = {"dono": "root", "grupo": "admin", "perm": 0o755, "cifrado": False}


# ---------- utilitários ----------
def silenciar(funcao, *args):
    # esconde os prints da Etapa 2
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        resultado = funcao(*args)
    if MOSTRAR_ES:
        print(saida.getvalue(), end="")
    return resultado


def absoluto(caminho):
    if not caminho.startswith("/"):
        base = fs.caminho_de(fs.atual)
        if base != "/":
            base = base + "/"
        caminho = base + caminho
    partes = []
    for p in caminho.split("/"):
        if p == "" or p == ".":
            continue
        if p == "..":
            if len(partes) > 0:
                partes.pop()
            continue
        partes.append(p)
    return "/" + "/".join(partes)


def pai_de(caminho):
    partes = caminho.split("/")[:-1]
    return "/".join(partes) or "/"


def registrar(texto):
    quem = "ninguém"
    if sessao is not None:
        quem = sessao["usuario"]
    log.append(f"[{len(log) + 1:03d}] ({quem}) {texto}")


def negar(texto):
    print("[NEGADO]: " + texto)
    registrar(texto)
    print("Tentativa não autorizada registrada nos logs do sistema.")


def texto_perm(perm):
    # 0o750 -> "rwxr-x---"
    s = ""
    for deslocamento in (6, 3, 0):
        bits = (perm >> deslocamento) & 7
        s += "r" if bits & 4 else "-"
        s += "w" if bits & 2 else "-"
        s += "x" if bits & 1 else "-"
    return s


# ---------- senhas e criptografia ----------
def hash_senha(senha, salt):
    return hashlib.sha256((salt + senha).encode("utf-8")).hexdigest()


def novo_usuario(senha, grupo):
    salt = os.urandom(8).hex()
    return {"salt": salt, "hash": hash_senha(senha, salt), "grupo": grupo}


def fluxo_de_chave(chave, nonce, tamanho):
    # sequência de bytes a partir da chave
    saida = b""
    contador = 0
    while len(saida) < tamanho:
        saida += hashlib.sha256(chave.encode("utf-8") + nonce + contador.to_bytes(4, "big")).digest()
        contador += 1
    return saida[:tamanho]


def cifrar(dados, chave, nonce):
    return es.xor(dados, fluxo_de_chave(chave, nonce, len(dados)))


def decifrar(dados, chave, nonce):
    return cifrar(dados, chave, nonce)      # o XOR é reversível


# ---------- modos de execução, login e usuários ----------
def exigir_kernel(operacao):
    if sessao is None:
        print("Nenhum usuário autenticado. Faça login primeiro.")
        return False
    if sessao["modo"] != MODO_KERNEL:
        negar(f"A operação '{operacao}' exige {MODO_KERNEL}, e o usuário "
              f"'{sessao['usuario']}' está em {sessao['modo']}.")
        return False
    return True


def login(nome, senha):
    global sessao
    print("Senha: " + "*" * len(senha))
    u = usuarios.get(nome)
    if u is None or hash_senha(senha, u["salt"]) != u["hash"]:
        registrar(f"Falha de autenticação para o usuário '{nome}'")
        print("Falha na autenticação: usuário ou senha incorretos.")
        return False
    modo = MODO_KERNEL if nome == "root" else MODO_USUARIO
    sessao = {"usuario": nome, "grupo": u["grupo"], "modo": modo}
    registrar(f"Login de '{nome}' em {modo}")
    print(f"Autenticado com sucesso. Usuário: '{nome}' | Grupo: '{u['grupo']}' | Modo: {modo}")
    return True


def logout():
    global sessao
    if sessao is not None:
        registrar("Logout")
        print(f"Usuário '{sessao['usuario']}' saiu do sistema.")
    sessao = None


def criar_grupo(nome):
    if not exigir_kernel("criar_grupo"):
        return
    if nome in grupos:
        print(f"Erro: o grupo '{nome}' já existe.")
        return
    grupos.append(nome)
    registrar(f"Grupo '{nome}' criado")
    print(f"Grupo '{nome}' criado.")


def criar_usuario(nome, senha, grupo):
    if not exigir_kernel("criar_usuario"):
        return
    if nome in usuarios:
        print(f"Erro: o usuário '{nome}' já existe.")
        return
    if grupo not in grupos:
        print(f"Erro: o grupo '{grupo}' não existe.")
        return
    usuarios[nome] = novo_usuario(senha, grupo)
    registrar(f"Usuário '{nome}' criado no grupo '{grupo}'")
    print(f"Usuário '{nome}' criado no grupo '{grupo}'.")


def mostrar_usuarios():
    if not exigir_kernel("mostrar_usuarios"):
        return
    print("[CADASTRO DE USUÁRIOS]")
    for nome in sorted(usuarios):
        u = usuarios[nome]
        print(f"{nome:<8} grupo={u['grupo']:<6} salt={u['salt']} hash={u['hash'][:24]}...")
    print("Grupos: " + ", ".join(grupos))


def mostrar_log():
    if not exigir_kernel("mostrar_log"):
        return
    print("[LOGS DO SISTEMA]")
    for linha in log:
        print(linha)


# ---------- controle de acesso (ACL estilo Unix) ----------
def verificar(caminho, acao):
    if sessao is None:
        print("Nenhum usuário autenticado. Faça login primeiro.")
        return False
    caminho = absoluto(caminho)
    if caminho not in meta:
        print("Erro: caminho não encontrado: " + caminho)
        return False
    m = meta[caminho]
    usuario = sessao["usuario"]
    grupo = sessao["grupo"]
    if sessao["modo"] == MODO_KERNEL:
        permitido = True
    else:
        if usuario == m["dono"]:
            bits = (m["perm"] >> 6) & 7
        elif grupo == m["grupo"]:
            bits = (m["perm"] >> 3) & 7
        else:
            bits = m["perm"] & 7
        permitido = (bits & BITS[acao]) != 0
    if permitido:
        print(f"[ACL] {NOMES_ACAO[acao]} em '{caminho}' por '{usuario}': PERMITIDO "
              f"({texto_perm(m['perm'])}, {sessao['modo']})")
        return True
    print("[SISTEMA DE SEGURANÇA - VERIFICAÇÃO DE ACL]")
    print(f"Objeto      : {caminho}")
    print(f"Proprietário: {m['dono']} (Grupo: {m['grupo']})")
    print(f"Permissões  : {texto_perm(m['perm'])} ({m['perm']:o})")
    print(f"Ação Pedida : {NOMES_ACAO[acao]} por '{usuario}' (Grupo: {grupo})")
    print()
    negar(f"O usuário '{usuario}' não possui permissão de {PALAVRA_ACAO[acao]} "
          f"no objeto '{caminho}'.")
    return False


def chmod(caminho, perm):
    ab = absoluto(caminho)
    if sessao is None:
        print("Nenhum usuário autenticado. Faça login primeiro.")
        return
    if ab not in meta:
        print("Erro: caminho não encontrado: " + ab)
        return
    if sessao["modo"] != MODO_KERNEL and sessao["usuario"] != meta[ab]["dono"]:
        negar(f"Só o proprietário ('{meta[ab]['dono']}') ou o root pode mudar as permissões de '{ab}'.")
        return
    meta[ab]["perm"] = perm
    registrar(f"chmod {perm:o} {ab}")
    print(f"Permissões de '{ab}' alteradas para {texto_perm(perm)} ({perm:o}).")


def chown(caminho, dono, grupo):
    if not exigir_kernel("chown"):
        return
    ab = absoluto(caminho)
    if ab not in meta:
        print("Erro: caminho não encontrado: " + ab)
        return
    if dono not in usuarios or grupo not in grupos:
        print("Erro: usuário ou grupo inexistente.")
        return
    meta[ab]["dono"] = dono
    meta[ab]["grupo"] = grupo
    registrar(f"chown {dono}:{grupo} {ab}")
    print(f"Proprietário de '{ab}' alterado para {dono} (Grupo: {grupo}).")


# ---------- operações no sistema de arquivos (com segurança) ----------
def mkdir(caminho):
    ab = absoluto(caminho)
    if not verificar(pai_de(ab), "w"):
        return
    try:
        fs.mkdir(ab)
    except fs.Erro as e:
        print("Erro:", e)
        return
    meta[ab] = {"dono": sessao["usuario"], "grupo": sessao["grupo"], "perm": 0o755, "cifrado": False}
    print(f"Diretório '{ab}' criado.")


def cd(caminho):
    ab = absoluto(caminho)
    if not verificar(ab, "x"):
        return
    try:
        fs.cd(ab)
    except fs.Erro as e:
        print("Erro:", e)


def ls(caminho):
    ab = absoluto(caminho)
    if not verificar(ab, "r"):
        return
    no = fs.achar(ab)
    for nome in sorted(no.filhos):
        filho = ab + "/" + nome if ab != "/" else "/" + nome
        if filho not in meta:
            print(f"---------- ?       ?      {nome}  (sem registro de segurança)")
            continue
        m = meta[filho]
        sufixo = "/" if no.filhos[nome].eh_dir else ""
        print(f"{texto_perm(m['perm'])} {m['dono']:<7} {m['grupo']:<6} {nome}{sufixo}")


def gravar_no_disco(ab, texto, tamanho, chave):
    # grava pela Etapa 2
    novo = ab not in meta
    cifrado = None
    if chave is not None:
        nonce = os.urandom(8)
        cifrado = "0x" + cifrar(texto.encode("utf-8"), chave, nonce).hex().upper()
        silenciar(es.write_file, ab, cifrado)
    else:
        silenciar(es.write_file, ab, texto, tamanho)
    if novo:
        meta[ab] = {"dono": sessao["usuario"], "grupo": sessao["grupo"], "perm": 0o640, "cifrado": False}
    if chave is not None:
        meta[ab]["cifrado"] = True
        meta[ab]["nonce"] = nonce.hex()
        meta[ab]["chave_hash"] = hash_senha(chave, nonce.hex())
    else:
        meta[ab]["cifrado"] = False
    # registra o hash de cada bloco gravado (usado pelo anti-vírus)
    for b in fs.achar(ab).blocos:
        registro[b] = hashlib.sha256(es.raid_ler(b)).hexdigest()
    return cifrado


def chave_confere(ab, chave):
    return hash_senha(chave, meta[ab]["nonce"]) == meta[ab]["chave_hash"]


def write_file(caminho, texto=None, tamanho=0, chave=None):
    ab = absoluto(caminho)
    if ab in meta:
        if not verificar(ab, "w"):
            return
        if meta[ab]["cifrado"]:
            if chave is None:
                print(f"Erro: '{ab}' está criptografado; informe a chave para gravar.")
                return
            if not chave_confere(ab, chave):
                negar(f"Chave incorreta para o arquivo '{ab}'.")
                return
    else:
        if not verificar(pai_de(ab), "w"):
            return
    if chave is not None and texto is None:
        print("Erro: para criptografar é preciso informar o texto.")
        return
    try:
        gravar_no_disco(ab, texto, tamanho, chave)
    except fs.Erro as e:
        print("Erro:", e)
        return
    estado = "criptografado" if chave is not None else "em texto"
    print(f"Arquivo '{ab}' gravado ({fs.achar(ab).tamanho} bytes, {estado}).")


def read_file(caminho, chave=None):
    ab = absoluto(caminho)
    if not verificar(ab, "r"):
        return None
    try:
        dados = silenciar(es.read_file, ab)
    except fs.Erro as e:
        print("Erro:", e)
        return None
    if meta[ab]["cifrado"]:
        if chave is None:
            print(f"Conteúdo (criptografado): {dados.decode('ascii')[:24]}...")
            return dados
        if not chave_confere(ab, chave):
            negar(f"Chave incorreta para o arquivo '{ab}'.")
            return None
        nonce = bytes.fromhex(meta[ab]["nonce"])
        dados = decifrar(bytes.fromhex(dados.decode("ascii")[2:]), chave, nonce)
    print("Conteúdo: " + dados.decode("utf-8", errors="replace"))
    return dados


def encrypt_file(caminho, chave):
    ab = absoluto(caminho)
    if not verificar(ab, "r") or not verificar(ab, "w"):
        return
    if meta[ab]["cifrado"]:
        print(f"Erro: '{ab}' já está criptografado.")
        return
    try:
        texto = silenciar(es.read_file, ab).decode("utf-8")
        cifrado = gravar_no_disco(ab, texto, 0, chave)
    except (fs.Erro, UnicodeDecodeError) as e:
        print("Erro:", e)
        return
    registrar(f"Arquivo '{ab}' criptografado")
    print(f"Arquivo '{ab}' criptografado com sucesso.")
    print(f'Conteúdo gravado nos blocos físicos: "{cifrado[:12]}... (Encrypted Ciphertext)"')


def rm(caminho):
    ab = absoluto(caminho)
    if ab not in meta:
        print("Erro: caminho não encontrado: " + ab)
        return
    if not verificar(pai_de(ab), "w"):
        return
    no = fs.achar(ab)
    blocos = list(no.blocos) if not no.eh_dir else []
    try:
        fs.remover(ab)
    except fs.Erro as e:
        print("Erro:", e)
        return
    for b in blocos:
        registro.pop(b, None)
    del meta[ab]
    registrar(f"rm {ab}")
    print(f"'{ab}' removido.")


# ---------- anti-vírus simulado ----------
def adulterar_bloco(bloco):
    # simula um ataque direto ao disco, sem passar pelo sistema de arquivos
    raw = es.raid_ler(bloco)
    es.raid_gravar(bloco, bytes([raw[0] ^ 0xFF]) + raw[1:])


def antivirus_scan(caminho="/"):
    if not exigir_kernel("antivirus_scan"):
        return
    base = absoluto(caminho)
    arquivos = []
    for a in fs.todos_arquivos():
        p = fs.caminho_de(a)
        if base == "/" or p == base or p.startswith(base + "/"):
            arquivos.append(a)
    print("[MÓDULO DE SEGURANÇA - VARREDURA DE INTEGRIDADE]")
    print(f"Analisando {len(arquivos)} arquivos em busca de assinaturas maliciosas e hashes corrompidos...")
    largura = 0
    for a in arquivos:
        largura = max(largura, len(fs.caminho_de(a)))
    alertas = 0
    for a in arquivos:
        ab = fs.caminho_de(a)
        if ab not in meta:
            alertas += 1
            print("- " + ab.ljust(largura) + " : [ALERTA] Arquivo sem registro de segurança (criado fora do sistema)")
            registrar(f"Antivírus: arquivo '{ab}' sem registro de segurança")
            continue
        conteudo = b""
        blocos_ruins = []
        for b in a.blocos:
            raw = es.raid_ler(b)
            if registro.get(b) != hashlib.sha256(raw).hexdigest():
                blocos_ruins.append(b)
            conteudo += raw
        conteudo = conteudo[:a.tamanho]
        achadas = []
        if not meta[ab]["cifrado"]:
            for assinatura in ASSINATURAS:
                if assinatura.encode("utf-8") in conteudo:
                    achadas.append(assinatura)
        rotulo = "- " + ab.ljust(largura) + " : "
        if len(blocos_ruins) == 0 and len(achadas) == 0:
            if meta[ab]["cifrado"]:
                print(rotulo + "[OK - Criptografado e Íntegro]")
            else:
                print(rotulo + "[OK - Íntegro]")
            continue
        alertas += 1
        if len(blocos_ruins) > 0:
            print(rotulo + "[ALERTA] Hash do bloco difere do registro oficial!")
            print(f"  Resultado: Possível modificação direta não autorizada no(s) bloco(s) {blocos_ruins} do disco.")
            registrar(f"Antivírus: hash divergente em '{ab}' (blocos {blocos_ruins})")
        for assinatura in achadas:
            print(rotulo + f"[ALERTA] Assinatura maliciosa encontrada: '{assinatura}'")
            registrar(f"Antivírus: assinatura '{assinatura}' em '{ab}'")
    print(f"Varredura concluída: {len(arquivos)} arquivo(s) analisado(s), {alertas} com alerta.")


# ---------- demonstração ----------
if __name__ == "__main__":
    iniciar("indexada", "root123")

    print("=== Administração do sistema ===")
    print("> login --user root")
    login("root", "root123")
    criar_grupo("devs")
    criar_usuario("carlos", "carlos123", "devs")
    criar_usuario("maria", "maria123", "devs")
    mostrar_usuarios()
    print()
    mkdir("/sistema")
    mkdir("/sistema/logs")
    mkdir("/home")
    mkdir("/home/carlos")
    chown("/home/carlos", "carlos", "devs")
    chmod("/home/carlos", 0o750)
    write_file("/sistema/config.sys", "modo=producao;porta=8080")
    chmod("/sistema/config.sys", 0o750)
    write_file("/sistema/logs/app.log", "inicio do sistema\nusuario carlos entrou\n")
    chmod("/sistema/logs/app.log", 0o644)
    ls("/sistema")
    logout()

    print("\n=== Exemplo 3.1: autenticação e ACL ===")
    print("> login --user carlos (senha errada)")
    login("carlos", "senha-errada")
    print("\n> login --user carlos")
    login("carlos", "carlos123")
    print("\n> read_file /sistema/config.sys")
    read_file("/sistema/config.sys")
    print("\n> read_file /sistema/logs/app.log")
    read_file("/sistema/logs/app.log")
    print("\n> criar_usuario eve (operação crítica em MODO_USUARIO)")
    criar_usuario("eve", "eve123", "devs")

    print("\n=== Exemplo 3.2: criptografia e anti-vírus ===")
    print("> write_file /home/carlos/segredo.txt")
    write_file("/home/carlos/segredo.txt", "senha do banco: 12345")
    print("\n> encrypt_file /home/carlos/segredo.txt --key \"MinhaChave123\"")
    encrypt_file("/home/carlos/segredo.txt", "MinhaChave123")
    print("\n> read_file /home/carlos/segredo.txt")
    read_file("/home/carlos/segredo.txt")
    print("\n> read_file /home/carlos/segredo.txt --key \"MinhaChave123\"")
    read_file("/home/carlos/segredo.txt", "MinhaChave123")
    print("\n> read_file /home/carlos/segredo.txt --key \"errada\"")
    read_file("/home/carlos/segredo.txt", "errada")
    print("\n> write_file /home/carlos/baixado.sh")
    write_file("/home/carlos/baixado.sh", "#!/bin/sh\n# MALWARE_TESTE\necho ola\n")
    logout()

    print("\n> ataque direto ao disco (fora do sistema de arquivos)")
    adulterar_bloco(fs.achar("/sistema/logs/app.log").blocos[0])

    print("\n> login --user root")
    login("root", "root123")
    print("\n> antivirus_scan /")
    antivirus_scan("/")
    print()
    mostrar_log()