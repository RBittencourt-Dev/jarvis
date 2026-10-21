"""Primeiro uso / outro PC: garante o config.json local antes de qualquer módulo ler.

O repositório traz só o config.padrao.json (genérico, sem dado pessoal). Cada PC tem o seu config.json (fora do git):
  - não existe → nasce do padrão (o assistente de instalação pergunta o resto: nome, cidade, perfil do PC…);
  - existe → ganha as chaves NOVAS que uma atualização trouxe, sem mexer em nada que já estava lá.
Também cria as pastas locais (dados/, conhecimento/) e o spotify.json a partir do padrão, se faltar.
Importado primeiro no server.py e no palmas.py.
"""
import json
from pathlib import Path

RAIZ = Path(__file__).parent
PADRAO = RAIZ / "config.padrao.json"
LOCAL = RAIZ / "config.json"


def _juntar(local, padrao):
    """Chaves que faltam no local vêm do padrão (também dentro de dicionários); o que existe fica."""
    for k, v in padrao.items():
        if k not in local:
            local[k] = v
        elif isinstance(v, dict) and isinstance(local[k], dict) and k not in ("apelidos", "casa"):
            _juntar(local[k], v)
    return local


def garantir():
    padrao = json.loads(PADRAO.read_text(encoding="utf-8")) if PADRAO.exists() else {}
    if LOCAL.exists():
        try:
            local = json.loads(LOCAL.read_text(encoding="utf-8"))
        except ValueError:
            local = {}
        antes = json.dumps(local, sort_keys=True)
        _juntar(local, padrao)
        if json.dumps(local, sort_keys=True) != antes:
            LOCAL.write_text(json.dumps(local, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        LOCAL.write_text(json.dumps(padrao, ensure_ascii=False, indent=2), encoding="utf-8")
    for pasta in ("dados", "conhecimento"):
        (RAIZ / pasta).mkdir(exist_ok=True)
    cid = padrao.get("spotify_client_id")
    if cid and not (RAIZ / "spotify.json").exists():
        (RAIZ / "spotify.json").write_text(json.dumps({"client_id": cid}), encoding="utf-8")


garantir()
