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


# ------------------------------------------------------------------ "que avião é esse?": rota, companhia, modelo e foto

MODELOS_AVIAO = {  # código ICAO do tipo → nome falado
    "A20N": "Airbus A320neo", "A320": "Airbus A320", "A319": "Airbus A319", "A321": "Airbus A321", "A21N": "Airbus A321neo",
    "A332": "Airbus A330-200", "A333": "Airbus A330-300", "A339": "Airbus A330-900neo", "A359": "Airbus A350-900",
    "A35K": "Airbus A350-1000", "A388": "Airbus A380", "B737": "Boeing 737-700", "B738": "Boeing 737-800",
    "B38M": "Boeing 737 MAX 8", "B39M": "Boeing 737 MAX 9", "B744": "Boeing 747-400", "B748": "Boeing 747-8",
    "B763": "Boeing 767-300", "B772": "Boeing 777-200", "B77W": "Boeing 777-300ER", "B788": "Boeing 787-8",
    "B789": "Boeing 787-9", "B78X": "Boeing 787-10", "E190": "Embraer E190", "E195": "Embraer E195", "E295": "Embraer E195-E2",
    "E290": "Embraer E190-E2", "E145": "Embraer ERJ-145", "AT72": "ATR 72", "AT76": "ATR 72-600", "AT45": "ATR 42-500",
    "C525": "Cessna Citation", "C208": "Cessna Caravan", "PC12": "Pilatus PC-12", "BE20": "Beechcraft King Air",
}
_detalhes = {}
NOMES_DE_HOJE = {"TAM Brazilian Airlines": "LATAM", "LAN Airlines": "LATAM", "Gol Linhas Aéreas Inteligentes": "Gol",
                 "GOL Linhas Aereas Inteligentes": "Gol", "Azul Brazilian Airlines": "Azul", "Azul Linhas Aereas Brasileiras": "Azul",
                 "Aerolineas Argentinas": "Aerolíneas Argentinas", "JS Aviation": "JetSMART",
                 "JetSMART SpA": "JetSMART", "Sky Airline": "SKY Airline"}


def detalhes_aviao(hex_="", voo="", reg="", tipo=""):
    """Tudo que dá pra saber de um avião no ar, de fontes abertas: rota e companhia (adsbdb, pelo número do voo),
    dono/modelo (adsbdb, pelo código do transponder) e foto (Planespotters pela matrícula/hex; se não tiver, uma foto
    livre do mesmo modelo no Wikimedia Commons). Guardado por avião."""
    chave = hex_ or voo or reg
    if chave in _detalhes:
        return _detalhes[chave]
    d = {"hex": hex_, "voo": voo, "matricula": reg, "tipo": tipo, "modelo": MODELOS_AVIAO.get(tipo, tipo)}
    if voo:
        try:
            c = httpx.get(f"https://api.adsbdb.com/v0/callsign/{voo}", headers=CABECALHO, timeout=8).json().get("response")
            rota = c.get("flightroute") if isinstance(c, dict) else None
            if rota:
                o, de = rota.get("origin") or {}, rota.get("destination") or {}
                d["companhia"] = NOMES_DE_HOJE.get((rota.get("airline") or {}).get("name"), (rota.get("airline") or {}).get("name"))
                d["origem"] = o.get("municipality") or o.get("name")
                d["destino"] = de.get("municipality") or de.get("name")
                d["origem_aeroporto"], d["destino_aeroporto"] = o.get("name"), de.get("name")
        except Exception:
            pass
    if hex_:
        try:
            r = httpx.get(f"https://api.adsbdb.com/v0/aircraft/{hex_}", headers=CABECALHO, timeout=8).json().get("response")
            a = r.get("aircraft") if isinstance(r, dict) else None
            if a:
                d["dono"] = a.get("registered_owner")
                d["matricula"] = d["matricula"] or a.get("registration")
                d["fabricante"] = a.get("manufacturer")
                if a.get("url_photo"):  # airport-data bloqueia foto fora do site: só se nada mais tiver foto
                    d["_reserva"] = a["url_photo"]
        except Exception:
            pass
    for caminho in ([f"reg/{d['matricula']}"] if d.get("matricula") else []) + ([f"hex/{hex_}"] if hex_ else []):
        if d.get("foto") and "plnspttrs" in d["foto"]:
            break
        try:
            p = httpx.get(f"https://api.planespotters.net/pub/photos/{caminho}", headers=CABECALHO, timeout=8).json()
            foto = (p.get("photos") or [None])[0]
            if foto:
                d["foto"] = (foto.get("thumbnail_large") or foto.get("thumbnail") or {}).get("src")
                d["credito"] = f"Foto: {foto.get('photographer', '')} · Planespotters.net"
                d["foto_pagina"] = foto.get("link")
                break
        except Exception:
            pass
    if not d.get("foto") and d.get("modelo"):  # foto livre do mesmo modelo (e da companhia, se der)
        try:
            import pesquisa_painel
            for termo in ([f"{d['companhia']} {d['modelo']}"] if d.get("companhia") else []) + [d["modelo"]]:
                fotos = pesquisa_painel.fotos_commons(termo, 3)
                if fotos:
                    d["foto"], d["credito"] = fotos[0]["url"], f"Mesmo modelo ({termo}) · {fotos[0]['credito']}"
                    break
        except Exception:
            pass
    if not d.get("foto") and d.get("_reserva"):
        d["foto"], d["credito"] = d["_reserva"], "airport-data.com"
    d.pop("_reserva", None)
    _detalhes[chave] = d
    return d


def frase_do_aviao(a, d):
    """Como o Jarvis fala do avião: voo, modelo, companhia, rota, altura e velocidade."""
    partes = [f"É o voo {a.get('voo') or d.get('voo') or 'sem número'}"]
    if d.get("modelo"):
        partes.append(f"um {d['modelo']}")
    if d.get("companhia"):
        partes.append(f"da {d['companhia']}")
    texto = ", ".join(partes)
    if d.get("origem") and d.get("destino"):
        texto += f", de {d['origem']} pra {d['destino']}"
    if a.get("alt_m"):
        texto += f". Tá a {round(a['alt_m'] / 100) * 100:,} metros".replace(",", ".")
    if a.get("vel_kmh"):
        texto += f", a {a['vel_kmh']} km/h"
    return texto + "."


_ultimos = {"lista": [], "centro": None}  # os aviões que a tela pediu por último (pra "que avião é esse?")


def lembrar_lista(lista, centro):
    _ultimos.update(lista=lista, centro=centro)


def mais_perto(lat, lng, lista=None):
    import math
    lista = lista if lista is not None else _ultimos["lista"]
    if not lista:
        return None
    return min(lista, key=lambda a: (a["lat"] - lat) ** 2 + ((a["lng"] - lng) * math.cos(math.radians(lat))) ** 2)


# ------------------------------------------------------------------ câmeras ao vivo (só públicas e oficiais: Windy Webcams)

def cameras(chave, lat, lng, raio_km=60, limite=40):
    """Câmeras públicas perto de um ponto (estrada, praia, cidade, aeroporto). Chave grátis em api.windy.com/keys."""
    r = httpx.get("https://api.windy.com/webcams/api/v3/webcams", headers={"x-windy-api-key": chave}, timeout=15,
                  params={"nearby": f"{lat},{lng},{min(250, int(raio_km))}", "limit": limite, "include": "images,location,player,urls",
                          "lang": "pt"})
    if r.status_code == 401:
        raise PermissionError("a chave da Windy foi recusada")
    r.raise_for_status()
    lista = []
    for w in r.json().get("webcams", []):
        loc, img, pl = w.get("location") or {}, (w.get("images") or {}).get("current") or {}, w.get("player") or {}
        if loc.get("latitude") is None:
            continue
        lista.append({"id": str(w.get("webcamId")), "nome": w.get("title") or "Câmera", "lat": loc["latitude"], "lng": loc["longitude"],
                      "cidade": loc.get("city") or "", "foto": img.get("preview") or img.get("thumbnail"),
                      "player": pl.get("live") or pl.get("day") or "", "ativa": w.get("status") == "active"})
    return lista
