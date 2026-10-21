"""Cofre de chaves do Jarvis: tokens e chaves de API criptografados com a proteção do próprio Windows (DPAPI).

Só a conta do Windows dele, neste PC, consegue abrir o dados/cofre.bin — copiar o arquivo pra outro PC não adianta.
Nunca guarda senha de login: só chaves/tokens que ELE gerou (Groq, Gemini, GitHub, Notion, Telegram…) e os tokens
de OAuth dos conectores. As chaves antigas em arquivo (groq.json…) continuam funcionando; o botão "Proteger chaves"
das Configurações move elas pra cá.
"""
import ctypes
import json
import threading
from ctypes import wintypes as w
from pathlib import Path

RAIZ = Path(__file__).parent
ARQUIVO = RAIZ / "dados" / "cofre.bin"
_trava = threading.Lock()


class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", w.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(dados: bytes):
    buf = ctypes.create_string_buffer(dados, len(dados))
    return _BLOB(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _proteger(dados: bytes) -> bytes:
    entrada, _buf = _blob(dados)
    saida = _BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(entrada), "jarvis", None, None, None, 0x1, ctypes.byref(saida)):
        raise OSError("DPAPI recusou")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _abrir(dados: bytes) -> bytes:
    entrada, _buf = _blob(dados)
    saida = _BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(entrada), None, None, None, None, 0x1, ctypes.byref(saida)):
        raise OSError("DPAPI recusou (outro usuário ou outro PC?)")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _ler():
    if not ARQUIVO.exists():
        return {}
    try:
        return json.loads(_abrir(ARQUIVO.read_bytes()).decode("utf-8"))
    except Exception:
        return {}


def _gravar(d):
    ARQUIVO.parent.mkdir(exist_ok=True)
    ARQUIVO.write_bytes(_proteger(json.dumps(d, ensure_ascii=False).encode("utf-8")))


def pegar(nome, padrao=None):
    with _trava:
        return _ler().get(nome, padrao)


def guardar(nome, valor):
    with _trava:
        d = _ler()
        d[nome] = valor
        _gravar(d)


def apagar(nome):
    with _trava:
        d = _ler()
        if d.pop(nome, None) is not None:
            _gravar(d)


def nomes():
    """Só os NOMES das chaves guardadas (a tela nunca recebe o valor)."""
    with _trava:
        return sorted(_ler())


def proteger_arquivos_antigos():
    """groq.json/gemini.json → cofre; o arquivo antigo vira .protegido (vazio de chave)."""
    movidas = []
    for prov, arquivo in (("groq", "groq.json"), ("gemini", "gemini.json")):
        p = RAIZ / arquivo
        if not p.exists():
            continue
        try:
            chave = json.loads(p.read_text(encoding="utf-8")).get("chave", "").strip()
        except ValueError:
            continue
        if chave:
            guardar(f"chave:{prov}", chave)
            p.write_text(json.dumps({"chave": "", "obs": "chave movida pro cofre (dados/cofre.bin)"}), encoding="utf-8")
            movidas.append(prov)
    return movidas
