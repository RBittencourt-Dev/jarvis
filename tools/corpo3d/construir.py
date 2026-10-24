"""Pipeline do CORPO HUMANO 3D do Jarvis (órgãos REAIS co-registrados, estilo raio-x).

Fonte: BodyParts3D (© DBCLS, CC BY) — o conjunto `partof_BP3D_4.0_obj_99.zip` é UM corpo inteiro segmentado,
todos os pedaços no MESMO referencial → os órgãos se encaixam sozinhos, sem alinhamento manual. Cada órgão é um
conjunto de arquivos `FJ####.obj` dentro do zip, mapeado por um id FMA.

O que este script faz (rode à mão, é build — não roda dentro do Jarvis):
    .venv\\Scripts\\python.exe tools\\corpo3d\\construir.py                  (todos os ORGAOS)
    .venv\\Scripts\\python.exe tools\\corpo3d\\construir.py coracao          (só um, pra testar)

Passos: para cada órgão -> acha os FJ pelo FMA -> extrai do zip -> junta -> DECIMA -> (todos juntos) normaliza no
mesmo enquadramento -> exporta web/modelos/corpo/<slug>.glb + manifesto.json (que o holograma.js lê).

Os mapas e o zip ficam em tools/corpo3d/cache/ (baixados à parte; ver README do BodyParts3D).
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import trimesh
import fast_simplification

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]                      # .../Jarvis
CACHE = AQUI / "cache"
SAIDA = RAIZ / "web" / "modelos" / "corpo"
ZIP = CACHE / "partof_BP3D_4.0_obj_99.zip"
MAPA_ELEM = CACHE / "partof_element_parts.txt"   # concept id \t name \t element file id
DENTRO = "partof_BP3D_4.0_obj_99"                # prefixo das pastas dentro do zip
SAIDA.mkdir(parents=True, exist_ok=True)

ALVO_FACES = 9000      # faces por órgão depois de decimar (leve pra web)
ESCALA_ALVO = 4.8      # altura do conjunto no mundo do holograma

# Órgãos por FMA (ids confirmados na pesquisa + no parts_list). sistema ∈ {orgaos, osseo, muscular, nervoso}.
ORGAOS = [
    {"nome": "Coração",          "slug": "coracao",     "sistema": "orgaos",  "cor": "#ff5d6c", "fma": "FMA7088"},
    {"nome": "Pulmão direito",   "slug": "pulmao_dir",  "sistema": "orgaos",  "cor": "#8fb8ff", "fma": "FMA7309"},
    {"nome": "Pulmão esquerdo",  "slug": "pulmao_esq",  "sistema": "orgaos",  "cor": "#8fb8ff", "fma": "FMA7310"},
    {"nome": "Fígado",           "slug": "figado",      "sistema": "orgaos",  "cor": "#c17a4a", "fma": "FMA7197"},
    {"nome": "Estômago",         "slug": "estomago",    "sistema": "orgaos",  "cor": "#f3b05a", "fma": "FMA7148"},
    {"nome": "Rim direito",      "slug": "rim_dir",     "sistema": "orgaos",  "cor": "#b5724a", "fma": "FMA7204"},
    {"nome": "Rim esquerdo",     "slug": "rim_esq",     "sistema": "orgaos",  "cor": "#b5724a", "fma": "FMA7205"},
    {"nome": "Intestino delgado","slug": "int_delgado", "sistema": "orgaos",  "cor": "#e7a06a", "fma": "FMA7200"},
    {"nome": "Intestino grosso", "slug": "int_grosso",  "sistema": "orgaos",  "cor": "#d98f5a", "fma": "FMA7201"},
    {"nome": "Cérebro",          "slug": "cerebro",     "sistema": "nervoso", "cor": "#ff9bd0", "fma": "FMA50801"},
    {"nome": "Crânio",           "slug": "cranio",      "sistema": "osseo",   "cor": "#dfe7ff", "fma": "FMA46565"},
]


def fma_para_fjs():
    """{FMA -> [FJ####, ...]} a partir do partof_element_parts.txt."""
    m = {}
    for ln in MAPA_ELEM.read_text(encoding="utf-8").splitlines()[1:]:
        p = ln.split("\t")
        if len(p) >= 3 and p[2].strip():
            m.setdefault(p[0].strip(), []).append(p[2].strip())
    return m


def carregar_orgao(zf, fjs):
    """Junta todos os FJ####.obj de um órgão numa Trimesh só."""
    partes = []
    nomes = set(zf.namelist())
    for fj in fjs:
        caminho = f"{DENTRO}/{fj}.obj"
        if caminho not in nomes:
            continue
        m = trimesh.load(io.BytesIO(zf.read(caminho)), file_type="obj", process=False)
        if isinstance(m, trimesh.Scene):
            m = trimesh.util.concatenate(tuple(m.geometry.values()))
        if len(m.faces):
            partes.append(m)
    if not partes:
        return None
    return trimesh.util.concatenate(partes)


def decimar(malha, alvo):
    if len(malha.faces) <= alvo:
        return malha
    v, f = fast_simplification.simplify(np.asarray(malha.vertices), np.asarray(malha.faces), target_count=alvo)
    return trimesh.Trimesh(vertices=v, faces=f, process=False)


def main(argv):
    if not ZIP.exists() or not MAPA_ELEM.exists():
        print("Faltam o zip/mapa do BodyParts3D em tools/corpo3d/cache/. Baixe antes."); return 1
    alvo_slugs = set(argv) if argv else None
    mapa = fma_para_fjs()
    zf = zipfile.ZipFile(ZIP)

    malhas = {}
    for o in ORGAOS:
        if alvo_slugs and o["slug"] not in alvo_slugs:
            continue
        fjs = mapa.get(o["fma"], [])
        print(f"[{o['slug']}] {o['nome']} ({o['fma']}) — {len(fjs)} elementos")
        m = carregar_orgao(zf, fjs)
        if m is None:
            print("  (nenhuma malha encontrada, pulei)"); continue
        antes = len(m.faces)
        m = decimar(m, ALVO_FACES)
        print(f"  faces: {antes} -> {len(m.faces)}")
        malhas[o["slug"]] = m
    if not malhas:
        print("Nada montado."); return 1

    # normaliza o CONJUNTO (preserva a co-registração: um centro e uma escala pra todos). BodyParts3D é Y-up.
    uniao = trimesh.util.concatenate(list(malhas.values()))
    centro = uniao.bounds.mean(axis=0)
    altura = float(uniao.extents[1]) or 1.0
    escala = ESCALA_ALVO / altura

    # carrega manifesto existente pra atualizar só os órgãos regenerados (quando rodo um slug só)
    manif_path = SAIDA / "manifesto.json"
    por_slug = {}
    if manif_path.exists():
        try:
            por_slug = {x["slug"]: x for x in json.loads(manif_path.read_text(encoding="utf-8"))}
        except Exception:
            por_slug = {}

    for o in ORGAOS:
        if o["slug"] not in malhas:
            continue
        m = malhas[o["slug"]]
        m.apply_translation(-centro)
        m.apply_scale(escala)
        destino = SAIDA / f"{o['slug']}.glb"
        m.export(destino)
        por_slug[o["slug"]] = {"nome": o["nome"], "slug": o["slug"], "sistema": o["sistema"], "cor": o["cor"],
                               "arquivo": f"/web/modelos/corpo/{o['slug']}.glb", "faces": int(len(m.faces))}
        print(f"  salvo {destino.name} ({destino.stat().st_size // 1024} KB)")

    ordem = [o["slug"] for o in ORGAOS if o["slug"] in por_slug]
    manif_path.write_text(json.dumps([por_slug[s] for s in ordem], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOK: {len(ordem)} órgãos no manifesto ({manif_path}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
