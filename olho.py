"""Olho de Deus: dados públicos ao vivo em cima do globo da extensão.

Camadas (todas grátis, sem chave):
  - aviões: adsb.lol (rede comunitária de receptores ADS-B), num raio de ~250 milhas náuticas do ponto que o
    globo está olhando (padrão: a casa dele). A tela anda com cada avião entre uma leitura e outra (rumo e
    velocidade), então eles voam animados;
  - satélites: CelesTrak (estações espaciais + os ~150 mais brilhantes), posição calculada aqui com SGP4 a cada
    pedido — a ISS aparece com nome;
  - terremotos: USGS, magnitude 2,5+ nas últimas 24 h;
  - clima: Open-Meteo nas capitais;
  - notícias: as manchetes (noticias.py) passam num letreiro embaixo.
Cache curto em memória pra não martelar as APIs (aviões 8 s, satélites: elementos 6 h, terremotos 5 min).
"""
import math
import time
from datetime import datetime, timezone

import httpx

CABECALHO = {"User-Agent": "JarvisAssistente/1.0 (uso pessoal)"}
_cache = {}
_castigo = {"ate": 0.0}  # adsb.lol respondeu 429: espera antes de pedir de novo


def _guardado(chave, validade, buscar):
    agora = time.time()
    c = _cache.get(chave)
    if c and agora - c[0] < validade:
        return c[1]
    try:
        dado = buscar()
    except Exception as e:
        print("olho:", chave, e)
        return c[1] if c else []
    _cache[chave] = (agora, dado)
    return dado


# ------------------------------------------------------------------ aviões

def avioes(lat=-30.03, lng=-51.23, raio_nm=250):
    lat, lng = round(float(lat), 1), round(float(lng), 1)

    def buscar():
        if time.time() < _castigo["ate"]:
            raise RuntimeError("adsb.lol pediu calma (429)")
        r = httpx.get(f"https://api.adsb.lol/v2/lat/{lat}/lon/{lng}/dist/{int(raio_nm)}", headers=CABECALHO, timeout=10)
        if r.status_code == 429:
            _castigo["ate"] = time.time() + 60
            raise RuntimeError("adsb.lol pediu calma (429)")
        j = r.json()
        saida = []
        for a in j.get("ac") or []:
            if a.get("lat") is None or a.get("lon") is None or a.get("alt_baro") == "ground":
                continue
            alt_pes = a.get("alt_geom") or a.get("alt_baro") or 0
            saida.append({"id": a.get("hex"), "voo": (a.get("flight") or a.get("r") or "").strip(), "modelo": a.get("t") or "",
                          "lat": a["lat"], "lng": a["lon"], "alt_m": round(float(alt_pes) * 0.3048),
                          "vel_kmh": round(float(a.get("gs") or 0) * 1.852), "rumo": float(a.get("track") or a.get("true_heading") or 0),
                          "visto": time.time() - float(a.get("seen_pos") or 0)})
        return saida
    return _guardado(f"avioes:{lat}:{lng}", 8, buscar)


# ------------------------------------------------------------------ satélites

def _elementos():
    def buscar():
        saida = []
        for grupo in ("stations", "visual"):
            r = httpx.get(f"https://celestrak.org/NORAD/elements/gp.php?GROUP={grupo}&FORMAT=json", headers=CABECALHO, timeout=15)
            saida += r.json()
        vistos, unicos = set(), []
        for e in saida:
            if e["NORAD_CAT_ID"] not in vistos:
                vistos.add(e["NORAD_CAT_ID"])
                unicos.append(e)
        return unicos[:220]
    return _guardado("tle", 6 * 3600, buscar)


_satrecs = {}


def satelites():
    from sgp4 import omm
    from sgp4.api import Satrec, jday
    agora = datetime.now(timezone.utc)
    jd, fr = jday(agora.year, agora.month, agora.day, agora.hour, agora.minute, agora.second + agora.microsecond / 1e6)
    # tempo sideral de Greenwich: gira o referencial inercial (TEME) pro da Terra
    t = (jd - 2451545.0 + fr) / 36525.0
    gmst = math.radians((280.46061837 + 360.98564736629 * (jd - 2451545.0 + fr) + 0.000387933 * t * t) % 360)
    saida = []
    for e in _elementos():
        chave = e["NORAD_CAT_ID"]
        sat = _satrecs.get(chave)
        if sat is None:
            sat = Satrec()
            try:
                omm.initialize(sat, e)
            except Exception:
                continue
            _satrecs[chave] = sat
        erro, r, v = sat.sgp4(jd, fr)
        if erro:
            continue
        x, y, z = r
        xg = x * math.cos(gmst) + y * math.sin(gmst)
        yg = -x * math.sin(gmst) + y * math.cos(gmst)
        raio = math.sqrt(xg * xg + yg * yg + z * z)
        nome = e.get("OBJECT_NAME", "")
        saida.append({"id": chave, "nome": nome, "lat": math.degrees(math.asin(z / raio)),
                      "lng": (math.degrees(math.atan2(yg, xg)) + 540) % 360 - 180, "alt_km": round(raio - 6371),
                      "vel_kms": round(math.sqrt(sum(c * c for c in v)), 2), "destaque": "ISS" in nome or "CSS" in nome})
    return saida


# ------------------------------------------------------------------ terremotos

def terremotos():
    def buscar():
        j = httpx.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson", timeout=12).json()
        return [{"id": f["id"], "mag": f["properties"]["mag"], "lugar": f["properties"]["place"],
                 "quando": f["properties"]["time"] / 1000, "lng": f["geometry"]["coordinates"][0],
                 "lat": f["geometry"]["coordinates"][1], "prof_km": f["geometry"]["coordinates"][2]}
                for f in j.get("features", []) if f["properties"].get("mag") is not None]
    return _guardado("terremotos", 300, buscar)


# ------------------------------------------------------------------ clima nas capitais

CAPITAIS = [("Porto Alegre", -30.03, -51.23), ("São Paulo", -23.55, -46.63), ("Rio de Janeiro", -22.91, -43.17),
            ("Brasília", -15.79, -47.88), ("Salvador", -12.97, -38.50), ("Manaus", -3.12, -60.02),
            ("Recife", -8.05, -34.88), ("Curitiba", -25.43, -49.27), ("Florianópolis", -27.60, -48.55),
            ("Belo Horizonte", -19.92, -43.94), ("Fortaleza", -3.73, -38.52), ("Belém", -1.46, -48.49),
            ("Buenos Aires", -34.60, -58.38), ("Montevidéu", -34.90, -56.16), ("Lisboa", 38.72, -9.14),
            ("Nova York", 40.71, -74.01), ("Londres", 51.51, -0.13), ("Tóquio", 35.68, 139.69)]


def clima():
    def buscar():
        j = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=12, params={
            "latitude": ",".join(str(c[1]) for c in CAPITAIS), "longitude": ",".join(str(c[2]) for c in CAPITAIS),
            "current": "temperature_2m,weather_code"}).json()
        j = j if isinstance(j, list) else [j]
        return [{"nome": c[0], "lat": c[1], "lng": c[2], "temp": round(d["current"]["temperature_2m"]),
                 "codigo": d["current"]["weather_code"]} for c, d in zip(CAPITAIS, j)]
    return _guardado("clima", 900, buscar)


def manchetes():
    def buscar():
        import noticias
        _, cartoes = noticias.executar({"tema": ""})
        return [l["texto"] for l in (cartoes[0].get("links", []) if cartoes else [])][:12]
    return _guardado("manchetes", 900, buscar)


CAMADAS = {"avioes": "aviões", "satelites": "satélites", "terremotos": "terremotos", "clima": "clima", "noticias": "notícias"}


# ------------------------------------------------------------------ regiões ("aviões sobrevoando o Brasil")

def area(nome):
    """Lugar → {nome, lat, lng, caixa:[sul, norte, oeste, leste]} pelo Nominatim (guardado: não pergunta de novo)."""
    import json
    from pathlib import Path
    arquivo = Path(__file__).parent / "dados" / "areas.json"
    try:
        guardadas = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        guardadas = {}
    chave = nome.lower().strip()
    if chave in guardadas:
        return guardadas[chave]
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/search", headers=CABECALHO, timeout=10,
                      params={"q": nome, "format": "json", "limit": 1, "accept-language": "pt-BR"}).json()
    except Exception:
        return None
    if not r:
        return None
    s, n, o, l = (float(x) for x in r[0]["boundingbox"])
    achado = {"nome": r[0].get("name") or nome, "lat": float(r[0]["lat"]), "lng": float(r[0]["lon"]), "caixa": [s, n, o, l]}
    guardadas[chave] = achado
    arquivo.parent.mkdir(exist_ok=True)
    arquivo.write_text(json.dumps(guardadas, ensure_ascii=False), encoding="utf-8")
    return achado


_regioes = {}  # chave → {"avioes": {id: avião}, "em": quando terminou a última volta, "rodando": bool}


def avioes_na_caixa(sul, norte, oeste, leste):
    """Aviões numa região grande. O adsb.lol só responde num raio de ~460 km e não aceita rajada de pedidos,
    então a região vira uma grade (no máximo 9 pontos) lida em SEGUNDO PLANO, um ponto a cada 3 s.
    Devolve na hora o que já tem (os aviões vão aparecendo); uma volta nova a cada 45 s."""
    import threading
    chave = f"{sul:.1f}:{norte:.1f}:{oeste:.1f}:{leste:.1f}"
    reg = _regioes.setdefault(chave, {"avioes": {}, "em": 0.0, "rodando": False})
    if not reg["rodando"] and time.time() - reg["em"] > 45:
        reg["rodando"] = True

        def volta():
            alt, larg = norte - sul, leste - oeste
            passo = max(7.0, ((alt * larg) / 9) ** 0.5)
            pontos, lat = [], sul + min(passo, alt) / 2
            while lat < norte + 0.01:
                lng = oeste + min(passo, larg) / 2
                while lng < leste + 0.01:
                    pontos.append((lat, lng))
                    lng += passo
                lat += passo
            vistos = set()
            for la, ln in pontos[:9]:
                while time.time() < _castigo["ate"]:  # o adsb.lol pediu calma: espera em vez de pular a região
                    time.sleep(2)
                for a in avioes(la, ln):
                    if sul - 1 <= a["lat"] <= norte + 1 and oeste - 1 <= a["lng"] <= leste + 1:
                        reg["avioes"][a["id"]] = a
                        vistos.add(a["id"])
                time.sleep(3)
            for id_ in [k for k in reg["avioes"] if k not in vistos]:  # pousou ou saiu da região
                reg["avioes"].pop(id_, None)
            reg["em"], reg["rodando"] = time.time(), False
        threading.Thread(target=volta, daemon=True).start()
    return list(reg["avioes"].values())
