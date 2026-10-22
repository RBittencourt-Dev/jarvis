"""Estabelecimentos no globo: "mostra os Burger King", "restaurantes em Porto Alegre", "farmácias aqui perto",
e o filtro falado depois ("só em Porto Alegre", "agora no centro", "perto de mim").

Fonte: OpenStreetMap (grátis). Nominatim responde rápido (até 50 por busca, dentro da região); o Overpass, quando
está de pé, completa a lista em segundo plano (ele acha TODOS com aquele nome/marca na região).
Região da busca, nessa ordem: a que ele disse ("em X") → a que está selecionada no globo (clique) →
a da busca anterior → perto da casa dele (categoria) ou o Brasil (marca/nome).
Estado da última busca em `ultima` (pro "só em X" refiltrar).
"""
import re
import threading
import time
import unicodedata

import httpx

CABECALHO = {"User-Agent": "JarvisAssistente/1.0 (uso pessoal)"}
BRASIL = [-33.87, 5.27, -73.98, -28.63]  # sul, norte, oeste, leste
# categoria falada → (frase que o Nominatim entende, filtro do Overpass)
CATEGORIAS = {
    "restaurante": ("restaurant", '["amenity"="restaurant"]'), "lanchonete": ("fast food", '["amenity"="fast_food"]'),
    "hamburgueria": ("fast food", '["cuisine"~"burger"]'), "pizzaria": ("pizza", '["cuisine"~"pizza"]'),
    "farmacia": ("pharmacy", '["amenity"="pharmacy"]'), "posto": ("fuel", '["amenity"="fuel"]'),
    "posto de gasolina": ("fuel", '["amenity"="fuel"]'), "hospital": ("hospital", '["amenity"="hospital"]'),
    "mercado": ("supermarket", '["shop"="supermarket"]'), "supermercado": ("supermarket", '["shop"="supermarket"]'),
    "banco": ("bank", '["amenity"="bank"]'), "caixa eletronico": ("atm", '["amenity"="atm"]'),
    "academia": ("gym", '["leisure"="fitness_centre"]'), "hotel": ("hotel", '["tourism"="hotel"]'),
    "cafe": ("cafe", '["amenity"="cafe"]'), "cafeteria": ("cafe", '["amenity"="cafe"]'), "bar": ("bar", '["amenity"="bar"]'),
    "escola": ("school", '["amenity"="school"]'), "igreja": ("church", '["amenity"="place_of_worship"]'),
    "padaria": ("bakery", '["shop"="bakery"]'), "shopping": ("mall", '["shop"="mall"]'), "estacionamento": ("parking", '["amenity"="parking"]'),
    "pet shop": ("pet shop", '["shop"="pet"]'), "veterinario": ("veterinary", '["amenity"="veterinary"]'),
    "dentista": ("dentist", '["amenity"="dentist"]'), "clinica": ("clinic", '["amenity"="clinic"]'),
    "oficina": ("car repair", '["shop"="car_repair"]'), "loja": ("shop", '["shop"]'), "sorveteria": ("ice cream", '["amenity"="ice_cream"]'),
    "churrascaria": ("restaurant", '["cuisine"~"barbecue|steak"]'), "sushi": ("sushi", '["cuisine"~"sushi|japanese"]'),
    "aeroporto": ("airport", '["aeroway"="aerodrome"]'), "parque": ("park", '["leisure"="park"]'),
}
ultima = {}
ESTADOS = ["Rio Grande do Sul", "Santa Catarina", "Paraná", "São Paulo", "Rio de Janeiro", "Minas Gerais", "Espírito Santo",
           "Distrito Federal", "Goiás", "Mato Grosso do Sul", "Mato Grosso", "Bahia", "Pernambuco", "Ceará", "Paraíba",
           "Rio Grande do Norte", "Alagoas", "Sergipe", "Piauí", "Maranhão", "Pará", "Amazonas", "Tocantins", "Rondônia",
           "Acre", "Amapá", "Roraima"]


def _sa(t):
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


def categoria(termo):
    t = _sa(termo).strip()
    t = re.sub(r"(?:oes|aes)$", "ao", t)
    for chave in sorted(CATEGORIAS, key=len, reverse=True):
        if t == chave or t == chave + "s" or t == chave + "es" or t.rstrip("s") == chave:
            return chave
    return None


def _caixa_perto(lat, lng, km=6):
    d = km / 111
    return [lat - d, lat + d, lng - d / max(0.2, abs(__import__("math").cos(lat * 3.1416 / 180))),
            lng + d / max(0.2, abs(__import__("math").cos(lat * 3.1416 / 180)))]


def _nominatim(consulta, caixa, limite=50):
    s, n, o, l = caixa
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/search", headers=CABECALHO, timeout=12, params={
            "q": consulta, "format": "json", "limit": limite, "viewbox": f"{o},{n},{l},{s}", "bounded": 1,
            "addressdetails": 1, "accept-language": "pt-BR"})
        itens = r.json() if r.status_code == 200 else []
    except Exception:
        itens = []
    saida = []
    for a in itens:
        end = a.get("address") or {}
        rua = " ".join(x for x in (end.get("road"), end.get("house_number")) if x)
        cidade = end.get("city") or end.get("town") or end.get("village") or ""
        saida.append({"nome": a.get("name") or a.get("display_name", "").split(",")[0], "lat": float(a["lat"]),
                      "lng": float(a["lon"]), "endereco": ", ".join(x for x in (rua, end.get("suburb"), cidade) if x),
                      "id": f"n{a.get('osm_id')}"})
    return saida


def _overpass(filtro, caixa, limite=300):
    s, n, o, l = caixa
    q = f"[out:json][timeout:15];nwr{filtro}({s},{o},{n},{l});out center {limite};"
    for url in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        try:
            r = httpx.post(url, data={"data": q}, headers=CABECALHO, timeout=18)
            if r.status_code != 200:
                continue
            saida = []
            for e in r.json().get("elements", []):
                lat = e.get("lat") or (e.get("center") or {}).get("lat")
                lng = e.get("lon") or (e.get("center") or {}).get("lon")
                if lat is None:
                    continue
                t = e.get("tags") or {}
                rua = " ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber")) if x)
                saida.append({"nome": t.get("name") or t.get("brand") or "", "lat": lat, "lng": lng,
                              "endereco": ", ".join(x for x in (rua, t.get("addr:suburb"), t.get("addr:city")) if x),
                              "id": f"o{e.get('id')}"})
            return saida
        except Exception:
            continue
    return None


def _sem_repetidos(itens):
    saida = []
    for i in itens:
        if not any(abs(i["lat"] - j["lat"]) < 0.0004 and abs(i["lng"] - j["lng"]) < 0.0004 for j in saida):
            saida.append(i)
    return saida


def buscar(termo, area=None, ao_completar=None):
    """area = {"nome", "caixa"} ou None. Devolve (itens, area_usada). ao_completar(itens) chega depois se o
    Overpass achar mais (roda em segundo plano)."""
    cat = categoria(termo)
    if not area:
        import json
        from pathlib import Path
        import celular
        try:
            casa = celular.aqui() or json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))["casa"]
        except Exception:
            casa = {"lat": -30.03, "lng": -51.23}
        area = {"nome": "perto de você", "caixa": _caixa_perto(casa["lat"], casa["lng"])} if cat else {"nome": "no Brasil", "caixa": BRASIL}
    frase = CATEGORIAS[cat][0] if cat else termo
    itens = _sem_repetidos(_nominatim(frase, area["caixa"]))
    if not cat:  # marca/nome: só o que tem o nome no próprio nome (o Nominatim às vezes traz a rua "Burger King")
        palavras = [p for p in re.findall(r"\w{3,}", _sa(termo))]
        itens = [i for i in itens if all(p in _sa(i["nome"]) for p in palavras)] or itens
    ultima.clear()
    ultima.update(termo=termo, area=area, itens=itens, quando=time.time())

    def completar():
        filtro = CATEGORIAS[cat][1] if cat else f'["name"~"{re.escape(termo)}",i]'
        if not cat and area["caixa"] == BRASIL:
            # o Nominatim junta tudo com o mesmo nome no país inteiro: varre estado por estado (1 pedido por segundo,
            # regra deles), começando pelo dele, e os pontos vão aparecendo
            todos = list(itens)
            for uf in ESTADOS:
                if ultima.get("termo") != termo:
                    return  # ele já pediu outra coisa
                time.sleep(1.1)
                novos = [i for i in _nominatim(f"{termo}, {uf}", BRASIL) if all(p in _sa(i["nome"]) for p in re.findall(r"\w{3,}", _sa(termo)))]
                antes = len(todos)
                todos = _sem_repetidos(todos + novos)
                if len(todos) > antes:
                    ultima["itens"] = todos
                    if ao_completar:
                        ao_completar(todos)
            return
        mais = _overpass(filtro, area["caixa"])
        if mais and len(mais) > len(itens) and ultima.get("termo") == termo:
            todos = _sem_repetidos(itens + mais)
            ultima["itens"] = todos
            if ao_completar:
                ao_completar(todos)
    threading.Thread(target=completar, daemon=True).start()
    return itens, area
