"""
engine.py — Núcleo geométrico do gerador de letras-caixa (ACM + acrílico, CNC router).

Fluxo:
  SVG -> amostragem de curvas (com transformações resolvidas) -> polígonos com furos (even-odd)
  -> peças (letras/formas) -> frente de acrílico, fundo de ACM, paredes laterais (tiras)
  -> nesting em chapas -> DXF de corte (com compensação da fresa) + lista de corte + relatório.

Todas as unidades em milímetros.
"""
from __future__ import annotations

import bisect
import csv
import io
import json
import math
import os
import re
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import ezdxf
from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.validation import make_valid
from svgpathtools import svg2paths2

try:  # Document resolve <g transform>, rect, circle, etc.
    from svgpathtools import Document
except Exception:  # pragma: no cover
    Document = None

ROUND, MITRE = 1, 2  # estilos de junção do buffer


# ----------------------------------------------------------------------------
# Parâmetros
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Params:
    # Dimensões
    width: float = 2000.0
    height: float = 800.0
    scale_mode: str = "fit"          # fit | width | height | original
    # Construção
    depth: float = 50.0              # profundidade externa total
    acrylic: float = 3.0
    acm: float = 3.0
    profile: str = "overlay"         # overlay (acrílico sobre as paredes) | recess (acrílico entre as paredes)
    front_offset: float = 0.0        # só overlay: sobra (+) ou recuo (-) do acrílico
    back_offset: float = 0.0         # sobra (+) ou recuo (-) do fundo
    fit_clearance: float = 0.3       # folga do acrílico no modo recess
    # Máquina
    tool_d: float = 3.0
    tool_comp: bool = True
    part_gap: float = 4.0            # distância livre entre caminhos de fresa vizinhos
    sheet_margin: float = 5.0
    # Chapas (largura x comprimento)
    acm_sheet_w: float = 1250.0
    acm_sheet_l: float = 5000.0
    acr_sheet_w: float = 2000.0
    acr_sheet_l: float = 3000.0
    # Geometria
    sample_step: float = 0.5
    simplify_tol: float = 0.02
    autoclose_gap: float = 0.5
    min_area: float = 1.0
    # Tiras
    max_strip: float = 1000.0
    corner_angle: float = 35.0
    corner_window: float = 2.0
    joint_comp: bool = True
    min_bend_radius: float = 30.0
    min_clear: float = 20.0
    # LED (estimativa)
    led: bool = False
    led_density: float = 25.0        # módulos por m² de área interna
    led_watts: float = 0.72          # W por módulo


@dataclass
class Item:
    uid: str
    label: str
    kind: str          # frente | fundo | tira
    material: str      # ACM | ACR
    thickness: float
    geom: Polygon      # normalizado em (0,0)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PartResult:
    idx: int
    label: str
    outline: Polygon
    front: Any
    back: Any
    neutral: Any
    corners: List[Dict[str, Any]]
    n_strips: int
    min_bend_r: Optional[float]
    warnings: List[str]


@dataclass
class Result:
    params: Params
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    infos: List[str] = field(default_factory=list)
    actual_w: float = 0.0
    actual_h: float = 0.0
    side_h: float = 0.0
    parts: List[PartResult] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)
    nest: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------------------
# Utilidades geométricas
# ----------------------------------------------------------------------------
def iter_polys(g):
    if g is None or g.is_empty:
        return
    if isinstance(g, Polygon):
        yield g
    elif hasattr(g, "geoms"):
        for x in g.geoms:
            yield from iter_polys(x)


def only_polygons(g):
    polys = list(iter_polys(g))
    if not polys:
        return Polygon()
    return polys[0] if len(polys) == 1 else unary_union(polys)


def ring_pts(ring) -> List[tuple]:
    c = [(float(x), float(y)) for x, y in ring.coords]
    if len(c) > 1 and c[0] == c[-1]:
        c = c[:-1]
    return c


def densify(pts: List[tuple], h: float) -> List[tuple]:
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        out.append(a)
        d = math.dist(a, b)
        k = int(d // h)
        for j in range(1, k + 1):
            t = j * h / d
            if t < 1.0 - 1e-9:
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def normalize(g):
    b = g.bounds
    return affinity.translate(g, -b[0], -b[1])


# ----------------------------------------------------------------------------
# Leitura e amostragem do SVG
# ----------------------------------------------------------------------------
def load_svg_paths(data: bytes):
    warnings: List[str] = []
    text = data.decode("utf-8", errors="ignore")
    if re.search(r"<text[\s>]", text):
        warnings.append("O SVG contém <text>: textos não são lidos. Converta os textos em curvas.")
    if re.search(r"<image[\s>]", text):
        warnings.append("O SVG contém imagem raster (<image>), que foi ignorada.")
    if re.search(r"<clipPath|<mask", text):
        warnings.append("Máscaras/recortes (clipPath/mask) não são aplicados. Aplique-os no editor vetorial.")

    fd, name = tempfile.mkstemp(suffix=".svg")
    paths: list = []
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if Document is not None:
            try:
                paths = list(Document(name).paths())
            except Exception:
                paths = []
        if not paths:
            raw, _, _ = svg2paths2(name)
            paths = list(raw)
            if paths and re.search(r"transform\s*=", text):
                warnings.append("Foram encontradas transformações no SVG que podem não ter sido aplicadas. "
                                "Verifique as dimensões ou converta/expanda as transformações no editor vetorial.")
    finally:
        try:
            os.unlink(name)
        except OSError:
            pass
    return paths, warnings


def _seg_points(seg, step: float, fixed_n: Optional[int]):
    if type(seg).__name__ == "Line":
        return [seg.end]
    if fixed_n:
        n = fixed_n
    else:
        try:
            length = float(seg.length())
        except Exception:
            length = abs(seg.end - seg.start)
        n = int(min(4000, max(2, math.ceil(length / max(step, 1e-9)))))
    return [seg.point(i / n) for i in range(1, n + 1)]


def sample_paths(paths, step: float, fixed_n: Optional[int] = None):
    """Retorna lista de subcaminhos, cada um como lista de números complexos."""
    rings = []
    for path in paths:
        try:
            subs = path.continuous_subpaths()
        except Exception:
            subs = [path]
        for sp in subs:
            if len(sp) == 0:
                continue
            pts = [sp.start]
            for seg in sp:
                pts.extend(_seg_points(seg, step, fixed_n))
            rings.append(pts)
    return rings


# ----------------------------------------------------------------------------
# Análise de anéis (cantos, raios) e tiras laterais
# ----------------------------------------------------------------------------
def analyse_ring(pts: List[tuple], p: Params):
    h = max(0.25, min(p.corner_window / 2.0, 1.0))
    pts = densify(pts, h)
    n = len(pts)
    if n < 3:
        return None
    S = [0.0] * n
    for i in range(1, n):
        S[i] = S[i - 1] + math.dist(pts[i - 1], pts[i])
    total = S[-1] + math.dist(pts[-1], pts[0])
    if total <= 1e-9:
        return None
    win = max(p.corner_window, 1e-3)

    def idx_at(sv: float) -> int:
        sv %= total
        j = bisect.bisect_left(S, sv)
        if j >= n:
            return 0 if (total - sv) < (sv - S[n - 1]) else n - 1
        if j > 0 and (sv - S[j - 1]) < (S[j] - sv):
            return j - 1
        return j

    turns = [0.0] * n
    for i in range(n):
        a = pts[idx_at(S[i] - win)]
        b = pts[idx_at(S[i] + win)]
        q = pts[i]
        v1x, v1y = q[0] - a[0], q[1] - a[1]
        v2x, v2y = b[0] - q[0], b[1] - q[1]
        if (v1x == 0 and v1y == 0) or (v2x == 0 and v2y == 0):
            continue
        turns[i] = math.degrees(math.atan2(v1x * v2y - v1y * v2x, v1x * v2x + v1y * v2y))

    cands = sorted((i for i in range(n) if abs(turns[i]) >= p.corner_angle), key=lambda i: -abs(turns[i]))
    corners: List[int] = []
    for i in cands:
        ok = True
        for j in corners:
            d = abs(S[i] - S[j])
            d = min(d, total - d)
            if d <= win:
                ok = False
                break
        if ok:
            corners.append(i)
    corners.sort()

    # raio mínimo de curvatura fora dos cantos
    w2 = max(4.0, 2.0 * p.acm)
    mask = [False] * n
    for c in corners:
        a, b = idx_at(S[c] - w2), idx_at(S[c] + w2)
        i = a
        guard = 0
        while guard <= n:
            mask[i] = True
            if i == b:
                break
            i = (i + 1) % n
            guard += 1
    min_r = None
    for i in range(n):
        if mask[i]:
            continue
        a = pts[idx_at(S[i] - w2)]
        b = pts[idx_at(S[i] + w2)]
        q = pts[i]
        area2 = abs((q[0] - a[0]) * (b[1] - a[1]) - (q[1] - a[1]) * (b[0] - a[0]))
        if area2 < 1e-9:
            continue
        r = math.dist(a, q) * math.dist(q, b) * math.dist(a, b) / (2.0 * area2)
        if min_r is None or r < min_r:
            min_r = r

    cinfo = [{"xy": pts[c], "turn": turns[c], "interior_angle": 180.0 - turns[c]} for c in corners]
    runs = []
    m = len(corners)
    if m == 0:
        runs.append({"L": total, "c0": None, "c1": None})
    else:
        for k in range(m):
            c0, c1 = corners[k], corners[(k + 1) % m]
            L = total if m == 1 else (S[c1] - S[c0]) % total
            runs.append({"L": L, "c0": k, "c1": (k + 1) % m})
    return {"total": total, "corners": cinfo, "runs": runs, "min_r": min_r}


def _joint_ext(phi: float, p: Params) -> float:
    """Extensão (+) ou recuo (-) da ponta da tira que chega ao canto (a que sai usa o sinal oposto)."""
    if not p.joint_comp:
        return 0.0
    t = math.tan(math.radians(phi / 2.0))
    lim = 2.0 * p.acm
    if abs(t) < 1e-3:
        return math.copysign(lim, t if t != 0 else 1.0)
    return max(-lim, min(lim, (p.acm / 2.0) / t))


def build_strips(neutral, p: Params, side_h: float, label: str, warnings: List[str]):
    pieces: List[Dict[str, Any]] = []
    corners_xy: List[Dict[str, Any]] = []
    min_r: Optional[float] = None
    for poly in iter_polys(neutral):
        poly = orient(poly, 1.0)  # material sempre à esquerda do sentido do anel
        for ri, ring in enumerate([poly.exterior, *poly.interiors]):
            info = analyse_ring(ring_pts(ring), p)
            if not info:
                continue
            if info["min_r"] is not None and (min_r is None or info["min_r"] < min_r):
                min_r = info["min_r"]
            corners_xy.extend(info["corners"])
            ext = [_joint_ext(c["interior_angle"], p) for c in info["corners"]]
            for rk, run in enumerate(info["runs"]):
                e0 = ext[run["c0"]] if run["c0"] is not None else 0.0
                e1 = ext[run["c1"]] if run["c1"] is not None else 0.0
                ltot = run["L"] + e1 - e0
                if ltot <= 0.5:
                    warnings.append(f"{label}: trecho de parede muito curto após compensação de canto; verifique manualmente.")
                    continue
                n = max(1, math.ceil(ltot / p.max_strip - 1e-9))
                for k in range(n):
                    pieces.append({
                        "length": ltot / n, "height": side_h, "ring": ri, "run": rk,
                        "k": k + 1, "n": n,
                        "ang_ini": round(info["corners"][run["c0"]]["interior_angle"], 1) if (run["c0"] is not None and k == 0) else None,
                        "ang_fim": round(info["corners"][run["c1"]]["interior_angle"], 1) if (run["c1"] is not None and k == n - 1) else None,
                    })
    return pieces, corners_xy, min_r


# ----------------------------------------------------------------------------
# Construção de cada peça (letra/forma)
# ----------------------------------------------------------------------------
def build_part(i: int, poly: Polygon, p: Params, side_h: float):
    label = f"L{i}"
    pw: List[str] = []
    if p.profile == "recess":
        front = poly.buffer(-(p.acm + p.fit_clearance), join_style=ROUND)
    else:
        front = poly.buffer(p.front_offset, join_style=ROUND) if p.front_offset else poly
    back = poly.buffer(p.back_offset, join_style=ROUND) if p.back_offset else poly
    neutral = poly.buffer(-p.acm / 2.0, join_style=MITRE, mitre_limit=4.0)

    if neutral.is_empty:
        pw.append(f"{label}: traço mais fino que a espessura da parede ({p.acm} mm); não é possível gerar paredes.")
        pieces, corners, min_r = [], [], None
    else:
        pieces, corners, min_r = build_strips(neutral, p, side_h, label, pw)

    interior = poly.buffer(-p.acm, join_style=ROUND)
    if interior.is_empty:
        pw.append(f"{label}: sem espaço interno útil (traço < 2×ACM).")
    else:
        keep = interior.buffer(-p.min_clear / 2.0, join_style=ROUND).buffer(p.min_clear / 2.0, join_style=ROUND)
        narrow = interior.difference(keep).area
        if interior.area > 0 and narrow / interior.area > 0.02:
            pw.append(f"{label}: {100 * narrow / interior.area:.0f}% da área interna tem largura livre < {p.min_clear:g} mm "
                      f"(espaço para LED/fiação).")
    if min_r is not None and min_r < p.min_bend_radius:
        pw.append(f"{label}: raio mínimo de curva da parede ≈ {min_r:.1f} mm (< {p.min_bend_radius:g} mm). "
                  f"Exige canais de dobra/entalhes ou peça segmentada.")
    return pieces, corners, front, back, neutral, min_r, pw


# ----------------------------------------------------------------------------
# Nesting (prateleiras / shelf first-fit)
# ----------------------------------------------------------------------------
def nest_items(items: List[Item], sheet_w: float, sheet_l: float, gap: float, margin: float):
    ux, uy = sheet_l - 2 * margin, sheet_w - 2 * margin
    prepared, unplaced = [], []
    for it in items:
        b = it.geom.bounds
        w, h = b[2] - b[0], b[3] - b[1]
        cands = []
        for rot in (0, 90):
            ww, hh = (w, h) if rot == 0 else (h, w)
            if ww <= ux + 1e-9 and hh <= uy + 1e-9:
                cands.append((rot, ww, hh))
        if not cands:
            unplaced.append(it)
            continue
        cands.sort(key=lambda c: c[2])  # lado maior ao longo do comprimento da chapa
        rot, ww, hh = cands[0]
        prepared.append((it, rot, ww, hh))
    prepared.sort(key=lambda t: (-t[3], -t[2]))

    sheets: List[Dict[str, Any]] = []

    def place(sh, it, rot, ww, hh, pos):
        g = it.geom
        if rot == 90:
            g = affinity.rotate(g, 90, origin=(0, 0))
        b = g.bounds
        g = affinity.translate(g, -b[0] + pos[0] + margin, -b[1] + pos[1] + margin)
        sh["placed"].append({"item": it, "geom": g, "rot": rot})

    for it, rot, ww, hh in prepared:
        done = False
        for sh in sheets:
            for shelf in sh["shelves"]:
                if hh <= shelf["h"] + 1e-9 and shelf["x"] + ww <= ux + 1e-9:
                    place(sh, it, rot, ww, hh, (shelf["x"], shelf["y"]))
                    shelf["x"] += ww + gap
                    done = True
                    break
            if done:
                break
            if sh["y"] + hh <= uy + 1e-9:
                shelf = {"y": sh["y"], "h": hh, "x": ww + gap}
                sh["shelves"].append(shelf)
                sh["y"] += hh + gap
                place(sh, it, rot, ww, hh, (0.0, shelf["y"]))
                done = True
                break
        if not done:
            sh = {"shelves": [], "y": 0.0, "placed": []}
            sheets.append(sh)
            shelf = {"y": 0.0, "h": hh, "x": ww + gap}
            sh["shelves"].append(shelf)
            sh["y"] = hh + gap
            place(sh, it, rot, ww, hh, (0.0, 0.0))

    area = sheet_w * sheet_l
    for sh in sheets:
        sh["util"] = sum(pl["geom"].area for pl in sh["placed"]) / area if area else 0.0
    return sheets, unplaced


def cut_geom(g, p: Params):
    return g.buffer(p.tool_d / 2.0, join_style=ROUND) if p.tool_comp else g


# ----------------------------------------------------------------------------
# Pipeline principal
# ----------------------------------------------------------------------------
def run(svg_bytes: bytes, p: Params) -> Result:
    res = Result(params=p)

    side_h = p.depth - p.acm - (p.acrylic if p.profile == "overlay" else 0.0)
    res.side_h = side_h
    if side_h < 5:
        res.errors.append(f"Altura útil da parede = {side_h:.1f} mm. Aumente a profundidade ou reduza as espessuras.")
        return res

    paths, w = load_svg_paths(svg_bytes)
    res.warnings.extend(w)
    if not paths:
        res.errors.append("Nenhum caminho encontrado no SVG. Converta formas e textos em caminhos (outline).")
        return res

    # 1ª passada (grosseira) para descobrir a escala
    coarse = sample_paths(paths, 1.0, fixed_n=24)
    xs = [pt.real for r in coarse for pt in r]
    ys = [-pt.imag for r in coarse for pt in r]
    sw, sh = max(xs) - min(xs), max(ys) - min(ys)
    if sw <= 0 or sh <= 0:
        res.errors.append("A logo tem largura ou altura zero.")
        return res
    if p.scale_mode == "original":
        scale = 25.4 / 96.0
    elif p.scale_mode == "width":
        scale = p.width / sw
    elif p.scale_mode == "height":
        scale = p.height / sh
    else:
        scale = min(p.width / sw, p.height / sh)

    # 2ª passada (fina)
    fine = sample_paths(paths, p.sample_step / scale)
    rings_mm = []
    open_rings = 0
    auto_closed = 0
    for pts in fine:
        coords = [(pt.real * scale, -pt.imag * scale) for pt in pts]
        gap = math.dist(coords[0], coords[-1])
        if gap <= 1e-4:
            coords = coords[:-1]
        elif gap <= p.autoclose_gap:
            auto_closed += 1
        else:
            open_rings += 1
            continue
        if len(coords) >= 3:
            rings_mm.append(coords)
    if open_rings:
        res.warnings.append(f"{open_rings} caminho(s) aberto(s) ignorado(s) (folga > {p.autoclose_gap:g} mm). "
                            f"Feche os contornos no editor vetorial ou aumente a tolerância de fechamento.")
    if auto_closed:
        res.infos.append(f"{auto_closed} caminho(s) com folga pequena foram fechados automaticamente.")
    if not rings_mm:
        res.errors.append("Nenhum contorno fechado utilizável.")
        return res

    # Polígonos com furos pela regra even-odd (diferença simétrica)
    geom = None
    fixed = 0
    for r in rings_mm:
        poly = Polygon(r)
        if not poly.is_valid:
            fixed += 1
            poly = only_polygons(make_valid(poly))
        if poly.is_empty:
            continue
        geom = poly if geom is None else geom.symmetric_difference(poly)
    if geom is None or geom.is_empty:
        res.errors.append("Geometria vazia após processar os contornos.")
        return res
    if fixed:
        res.infos.append(f"{fixed} contorno(s) com auto-interseção foram reparados automaticamente. Confira o resultado na prévia.")
    geom = only_polygons(geom)
    if p.simplify_tol > 0:
        geom = geom.simplify(p.simplify_tol, preserve_topology=True)
    geom = normalize(geom)

    polys = [g for g in iter_polys(geom) if g.area >= p.min_area]
    dropped = len(list(iter_polys(geom))) - len(polys)
    if dropped:
        res.infos.append(f"{dropped} fragmento(s) minúsculo(s) (< {p.min_area:g} mm²) descartado(s).")
    if not polys:
        res.errors.append("Todas as formas ficaram menores que a área mínima.")
        return res
    polys.sort(key=lambda g: g.bounds[0])

    allg = unary_union(polys)
    b = allg.bounds
    res.actual_w, res.actual_h = b[2] - b[0], b[3] - b[1]
    if res.actual_w > p.width + 0.5 or res.actual_h > p.height + 0.5:
        res.warnings.append(f"A logo ({res.actual_w:.0f}×{res.actual_h:.0f} mm) ultrapassa a área alvo "
                            f"({p.width:g}×{p.height:g} mm) neste modo de escala.")

    items: List[Item] = []
    for i, poly in enumerate(polys, start=1):
        pieces, corners, front, back, neutral, min_r, pw = build_part(i, poly, p, side_h)
        res.warnings.extend(pw)
        label = f"L{i}"
        for k, pc in enumerate(pieces, start=1):
            items.append(Item(f"{label}-T{k:02d}", f"{label}-T{k:02d}", "tira", "ACM", p.acm,
                              Polygon([(0, 0), (pc["length"], 0), (pc["length"], pc["height"]), (0, pc["height"])]), pc))
        for j, g in enumerate(iter_polys(back), start=1):
            suf = "" if j == 1 else f".{j}"
            items.append(Item(f"{label}-FUNDO{suf}", f"{label}-FUNDO{suf}", "fundo", "ACM", p.acm, normalize(g), {}))
        for j, g in enumerate(iter_polys(front), start=1):
            suf = "" if j == 1 else f".{j}"
            items.append(Item(f"{label}-FRENTE{suf}", f"{label}-FRENTE{suf}", "frente", "ACR", p.acrylic, normalize(g), {}))
        if front.is_empty:
            res.warnings.append(f"{label}: a frente de acrílico ficou vazia com o perfil/folgas atuais.")
        res.parts.append(PartResult(i, label, poly, front, back, neutral, corners, len(pieces), min_r, pw))
    res.items = items

    # Nesting por material
    cfg = {
        "ACM": ("ACM (lateral/fundo)", p.acm_sheet_w, p.acm_sheet_l),
        "ACR": ("Acrílico (frente)", p.acr_sheet_w, p.acr_sheet_l),
    }
    margin = p.sheet_margin + (p.tool_d / 2.0 if p.tool_comp else 0.0)
    gap = p.tool_d + p.part_gap
    cut_len = 0.0
    lost_holes = 0
    for mat, (title, sw_, sl_) in cfg.items():
        its = [i for i in items if i.material == mat]
        if not its:
            continue
        sheets, unplaced = nest_items(its, sw_, sl_, gap, margin)
        for u in unplaced:
            bb = u.geom.bounds
            res.warnings.append(f"{u.label} ({bb[2]-bb[0]:.0f}×{bb[3]-bb[1]:.0f} mm) não cabe na chapa de {title} "
                                f"({sl_:g}×{sw_:g} mm). Reduza a escala, aumente a chapa ou segmente a peça.")
        for sh in sheets:
            for pl in sh["placed"]:
                cg = cut_geom(pl["geom"], p)
                cut_len += sum(pg.exterior.length + sum(r.length for r in pg.interiors) for pg in iter_polys(cg))
                lost_holes += sum(len(pg.interiors) for pg in iter_polys(pl["geom"])) - \
                    sum(len(pg.interiors) for pg in iter_polys(cg))
        res.nest[mat] = {"title": title, "sheet_w": sw_, "sheet_l": sl_, "sheets": sheets, "unplaced": unplaced}
    if lost_holes > 0 and p.tool_comp:
        res.warnings.append(f"{lost_holes} furo(s) menor(es) que a fresa de {p.tool_d:g} mm desaparecem no caminho de corte.")

    # Estatísticas
    strips = [i for i in items if i.kind == "tira"]
    all_corners = sum(len(pt.corners) for pt in res.parts)
    acm_area = sum(i.geom.area for i in items if i.material == "ACM")
    acr_area = sum(i.geom.area for i in items if i.material == "ACR")
    interior_area = sum(only_polygons(pt.outline.buffer(-p.acm)).area for pt in res.parts)
    res.stats = {
        "pecas": len(res.parts),
        "tiras": len(strips),
        "comprimento_tiras_m": sum(i.meta["length"] for i in strips) / 1000.0,
        "altura_parede_mm": side_h,
        "cantos_detectados": all_corners,
        "area_acm_m2": acm_area / 1e6,
        "area_acrilico_m2": acr_area / 1e6,
        "chapas_acm": len(res.nest.get("ACM", {}).get("sheets", [])),
        "chapas_acrilico": len(res.nest.get("ACR", {}).get("sheets", [])),
        "comprimento_corte_m": cut_len / 1000.0,
        "area_interna_m2": interior_area / 1e6,
        "perimetro_total_m": sum(pt.outline.length for pt in res.parts) / 1000.0,
    }
    if p.led:
        mods = math.ceil(res.stats["area_interna_m2"] * p.led_density)
        res.stats["led_modulos_estimados"] = mods
        res.stats["led_potencia_w_estimada"] = round(mods * p.led_watts, 1)
        res.stats["led_fonte_sugerida_w"] = math.ceil(mods * p.led_watts * 1.25 / 10.0) * 10
    return res


# ----------------------------------------------------------------------------
# Prévia em SVG
# ----------------------------------------------------------------------------
def _poly_d(g) -> str:
    ds = []
    for poly in iter_polys(g):
        for ring in [poly.exterior, *poly.interiors]:
            c = list(ring.coords)
            ds.append("M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in c) + "Z")
    return " ".join(ds)


def svg_preview(layers: List[Dict[str, Any]], bounds, width_px: int = 1000, pad_ratio: float = 0.03,
                dots: Optional[List[tuple]] = None, dot_color: str = "#ffe600", bg: str = "#0a1128") -> str:
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    pad = max(w, h) * pad_ratio
    vx, vy, vw, vh = x0 - pad, -(y1 + pad), w + 2 * pad, h + 2 * pad
    height_px = int(width_px * vh / vw) if vw else width_px
    gs = 10 ** math.floor(math.log10(max(w, h, 1.0) / 10.0)) if max(w, h) > 0 else 10
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vx:.2f} {vy:.2f} {vw:.2f} {vh:.2f}" '
           f'width="{width_px}" height="{height_px}">',
           f'<defs><pattern id="g" width="{gs}" height="{gs}" patternUnits="userSpaceOnUse">'
           f'<path d="M {gs} 0 L 0 0 0 {gs}" fill="none" stroke="#ffffff" stroke-opacity="0.06" stroke-width="1" '
           f'vector-effect="non-scaling-stroke"/></pattern></defs>',
           f'<rect x="{vx:.2f}" y="{vy:.2f}" width="{vw:.2f}" height="{vh:.2f}" fill="{bg}"/>',
           f'<rect x="{vx:.2f}" y="{vy:.2f}" width="{vw:.2f}" height="{vh:.2f}" fill="url(#g)"/>',
           '<g transform="scale(1,-1)">']
    for ly in layers:
        d = _poly_d(ly["geom"])
        if not d:
            continue
        title = f"<title>{ly['title']}</title>" if ly.get("title") else ""
        out.append(f'<path d="{d}" fill="{ly.get("fill", "none")}" fill-opacity="{ly.get("opacity", 1)}" '
                   f'fill-rule="evenodd" stroke="{ly.get("stroke", "none")}" stroke-width="{ly.get("sw", 1)}" '
                   f'vector-effect="non-scaling-stroke">{title}</path>')
    for (x, y) in dots or []:
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{max(w, h) * 0.003:.2f}" fill="{dot_color}" stroke="#222" stroke-width="1" vector-effect="non-scaling-stroke"/>')
    out.append("</g></svg>")
    return "".join(out)


def preview_assembly(res: Result) -> str:
    cf, cb, cw, cc = (LAYER_INFO[k][1] for k in ("FRENTE_ACRILICO", "FUNDO_ACM", "PAREDES_EIXO", "CANTOS"))
    layers = []
    for pt in res.parts:
        layers.append({"geom": pt.back, "fill": cb, "opacity": 0.28, "stroke": cb, "sw": 1.5, "title": f"{pt.label} fundo ACM"})
        layers.append({"geom": pt.front, "fill": cf, "opacity": 0.30, "stroke": cf, "sw": 1.5, "title": f"{pt.label} frente acrílico"})
        layers.append({"geom": pt.neutral, "fill": "none", "stroke": cw, "sw": 1.6, "title": f"{pt.label} eixo das paredes"})
    allg = unary_union([pt.outline for pt in res.parts])
    dots = [c["xy"] for pt in res.parts for c in pt.corners]
    return svg_preview(layers, allg.bounds, dots=dots, dot_color=cc)


def preview_sheet(res: Result, mat: str, idx: int) -> str:
    info = res.nest[mat]
    sh = info["sheets"][idx]
    p = res.params
    sheet = Polygon([(0, 0), (info["sheet_l"], 0), (info["sheet_l"], info["sheet_w"]), (0, info["sheet_w"])])
    layers = [{"geom": sheet, "fill": "#121b3b", "stroke": LAYER_INFO["CHAPA"][1], "sw": 1.5}]
    holes = []
    for pl in sh["placed"]:
        cg = cut_geom(pl["geom"], p)
        fill = {"tira": LAYER_INFO["PAREDES_EIXO"][1], "fundo": LAYER_INFO["FUNDO_ACM"][1],
                "frente": LAYER_INFO["FRENTE_ACRILICO"][1]}[pl["item"].kind]
        layers.append({"geom": cg, "fill": fill, "opacity": 0.32, "stroke": LAYER_INFO["CORTE_EXTERNO"][1], "sw": 1.0,
                       "title": pl["item"].label})
        holes.extend(Polygon(r) for pg in iter_polys(cg) for r in pg.interiors)
    if holes:
        layers.append({"geom": MultiPolygon(holes), "fill": "#121b3b", "stroke": LAYER_INFO["CORTE_INTERNO"][1], "sw": 1.0})
    return svg_preview(layers, sheet.bounds, pad_ratio=0.01)


# ----------------------------------------------------------------------------
# DXF
# ----------------------------------------------------------------------------
# nome da camada -> (cor ACI do DXF, cor hex equivalente, descrição)
LAYER_INFO = {
    "CORTE_EXTERNO": (5, "#4d8bff", "Contorno externo de corte (fresa passa por fora/na linha). Cortar DEPOIS dos internos."),
    "CORTE_INTERNO": (1, "#ff3b30", "Furos e recortes internos. Cortar PRIMEIRO."),
    "REFERENCIA": (9, "#b8b8b8", "Contorno nominal da peça (sem compensação da fresa). NÃO cortar."),
    "ROTULO": (3, "#2ecc71", "Nome da peça e título da chapa. NÃO cortar."),
    "CHAPA": (8, "#808080", "Borda da chapa de material. NÃO cortar."),
    "FRENTE_ACRILICO": (4, "#18d6e6", "Contorno da frente de acrílico (montagem)."),
    "FUNDO_ACM": (6, "#ff4fe0", "Contorno do fundo de ACM (montagem)."),
    "PAREDES_EIXO": (30, "#ff8a1f", "Linha central das paredes laterais (montagem)."),
    "CANTOS": (2, "#ffe600", "Círculos marcando os cantos/emendas (montagem)."),
    "NOTAS": (7, "#ffffff", "Observações do projeto."),
    "LEGENDA": (7, "#ffffff", "Quadro de legenda. NÃO cortar."),
}
_LAYERS = [(n, v[0]) for n, v in LAYER_INFO.items()]


def legend_rows(names):
    return [{"camada": n, "cor_hex": LAYER_INFO[n][1], "cor_aci": LAYER_INFO[n][0], "descricao": LAYER_INFO[n][2]}
            for n in names if n in LAYER_INFO]


def legend_text(names) -> str:
    lines = ["LEGENDA DE CORES DO DXF", "=" * 60, ""]
    for r in legend_rows(names):
        lines.append(f"{r['camada']:<16} cor CAD #{r['cor_aci']:<3} ({r['cor_hex']})  {r['descricao']}")
    lines += ["", "Atenção: a camada LEGENDA e as camadas marcadas como NÃO cortar devem ser desativadas na máquina."]
    return "\n".join(lines)


def add_legend(msp, x: float, y: float, names):
    """Quadro de legenda na camada LEGENDA, com cor explícita por entidade (não vira linha de corte)."""
    msp.add_text("LEGENDA DE CORES (nao cortar)", dxfattribs={"layer": "LEGENDA", "height": 18}).set_placement((x, y))
    yy = y - 40
    for r in legend_rows(names):
        msp.add_line((x, yy + 5), (x + 60, yy + 5), dxfattribs={"layer": "LEGENDA", "color": r["cor_aci"]})
        txt = f"{r['camada']}: {r['descricao']}"
        msp.add_text(txt, dxfattribs={"layer": "LEGENDA", "height": 10}).set_placement((x + 75, yy))
        yy -= 22


def _new_doc():
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    for name, color in _LAYERS:
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    return doc, doc.modelspace()


def _draw_polys(msp, g, ext_layer: str, int_layer: str, dy: float = 0.0):
    for poly in iter_polys(g):
        msp.add_lwpolyline([(x, y + dy) for x, y in ring_pts(poly.exterior)], close=True, dxfattribs={"layer": ext_layer})
        for r in poly.interiors:
            msp.add_lwpolyline([(x, y + dy) for x, y in ring_pts(r)], close=True, dxfattribs={"layer": int_layer})


def _dxf_bytes(doc) -> bytes:
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def sheets_dxf(res: Result, mat: str) -> bytes:
    info, p = res.nest[mat], res.params
    doc, msp = _new_doc()
    for si, sh in enumerate(info["sheets"]):
        oy = si * (info["sheet_w"] + 300.0)
        msp.add_lwpolyline([(0, oy), (info["sheet_l"], oy), (info["sheet_l"], oy + info["sheet_w"]), (0, oy + info["sheet_w"])],
                           close=True, dxfattribs={"layer": "CHAPA"})
        msp.add_text(f"{info['title']} - CHAPA {si + 1}/{len(info['sheets'])} - {info['sheet_l']:g}x{info['sheet_w']:g} mm - "
                     f"fresa {p.tool_d:g} mm", dxfattribs={"layer": "ROTULO", "height": 20}).set_placement((0, oy - 40))
        for pl in sh["placed"]:
            g = pl["geom"]
            if p.tool_comp:
                _draw_polys(msp, g, "REFERENCIA", "REFERENCIA", oy)
            _draw_polys(msp, cut_geom(g, p), "CORTE_EXTERNO", "CORTE_INTERNO", oy)
            rp = g.representative_point()
            b = g.bounds
            th = max(2.0, min(8.0, (b[3] - b[1]) * 0.25))
            msp.add_text(pl["item"].label, dxfattribs={"layer": "ROTULO", "height": th}).set_placement((rp.x - th * 2, rp.y + oy - th / 2))
    names = ["CORTE_EXTERNO", "CORTE_INTERNO", "ROTULO", "CHAPA"] + (["REFERENCIA"] if p.tool_comp else [])
    add_legend(msp, -1500.0, info["sheet_w"] - 20.0, names)
    return _dxf_bytes(doc)


def assembly_dxf(res: Result) -> bytes:
    p = res.params
    doc, msp = _new_doc()
    for pt in res.parts:
        _draw_polys(msp, pt.front, "FRENTE_ACRILICO", "FRENTE_ACRILICO")
        _draw_polys(msp, pt.back, "FUNDO_ACM", "FUNDO_ACM")
        _draw_polys(msp, pt.neutral, "PAREDES_EIXO", "PAREDES_EIXO")
        for c in pt.corners:
            msp.add_circle(c["xy"], 1.5, dxfattribs={"layer": "CANTOS"})
    note = (f"MONTAGEM - ref. | prof={p.depth:g} acm={p.acm:g} acr={p.acrylic:g} perfil={p.profile} "
            f"parede h={res.side_h:.1f} | NAO USAR PARA CORTE (ver chapas_*.dxf)")
    msp.add_text(note, dxfattribs={"layer": "NOTAS", "height": 8}).set_placement((0, -25))
    b = unary_union([pt.outline for pt in res.parts]).bounds
    add_legend(msp, b[0] - 900.0, b[3], ["FRENTE_ACRILICO", "FUNDO_ACM", "PAREDES_EIXO", "CANTOS"])
    return _dxf_bytes(doc)


# ----------------------------------------------------------------------------
# Relatórios
# ----------------------------------------------------------------------------
def cut_list_rows(res: Result) -> List[Dict[str, Any]]:
    where = {}
    for mat, info in res.nest.items():
        for si, sh in enumerate(info["sheets"]):
            for pl in sh["placed"]:
                where[pl["item"].uid] = si + 1
    rows = []
    for it in res.items:
        b = it.geom.bounds
        rows.append({
            "peca": it.label, "tipo": it.kind, "material": it.material, "espessura_mm": it.thickness,
            "comprimento_mm": round(b[2] - b[0], 2), "altura_mm": round(b[3] - b[1], 2),
            "area_cm2": round(it.geom.area / 100.0, 1), "chapa": where.get(it.uid, "NAO_ALOCADA"),
            "angulo_ini": it.meta.get("ang_ini"), "angulo_fim": it.meta.get("ang_fim"),
        })
    return rows


def build_outputs(res: Result) -> Dict[str, bytes]:
    files: Dict[str, bytes] = {}
    files["referencia_montagem.dxf"] = assembly_dxf(res)
    if "ACM" in res.nest:
        files["chapas_acm.dxf"] = sheets_dxf(res, "ACM")
    if "ACR" in res.nest:
        files["chapas_acrilico.dxf"] = sheets_dxf(res, "ACR")

    rows = cut_list_rows(res)
    sio = io.StringIO()
    if rows:
        wr = csv.DictWriter(sio, fieldnames=list(rows[0].keys()), delimiter=";")
        wr.writeheader()
        wr.writerows(rows)
    files["lista_de_corte.csv"] = ("\ufeff" + sio.getvalue()).encode("utf-8")

    report = {
        "versao": "1.0",
        "status": "REQUER_PECA_TESTE_ANTES_DO_LOTE",
        "parametros": asdict(res.params),
        "dimensoes_mm": {"largura": res.actual_w, "altura": res.actual_h, "altura_parede": res.side_h},
        "estatisticas": res.stats,
        "pecas": [{"id": pt.label, "tiras": pt.n_strips, "cantos": len(pt.corners),
                   "raio_min_curva_mm": pt.min_bend_r, "area_mm2": pt.outline.area,
                   "perimetro_mm": pt.outline.length} for pt in res.parts],
        "chapas": {m: [{"n": i + 1, "pecas": len(s["placed"]), "aproveitamento": round(s["util"], 4)}
                       for i, s in enumerate(v["sheets"])] for m, v in res.nest.items()},
        "avisos": res.warnings,
        "informacoes": res.infos,
        "premissas": [
            "Paredes: ACM dobrado/colado em torno da linha neutra (contorno recuado de ACM/2).",
            "Cantos: junta de topo com compensação de extensão calculada pelo ângulo; valide com peça-teste.",
            "Regra de preenchimento SVG: even-odd (furos por sobreposição de contornos).",
            "Caminho de fresa = contorno deslocado em fresa/2 (round); sem pontes (tabs), sem ordem/profundidade de passes.",
            "Estimativa de LED é indicativa; não substitui projeto elétrico.",
        ],
    }
    files["LEGENDA_CORES.txt"] = legend_text(
        ["CORTE_EXTERNO", "CORTE_INTERNO", "REFERENCIA", "ROTULO", "CHAPA",
         "FRENTE_ACRILICO", "FUNDO_ACM", "PAREDES_EIXO", "CANTOS"]).encode("utf-8")
    files["relatorio_projeto.json"] = json.dumps(report, indent=2, ensure_ascii=False, default=str).encode("utf-8")

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    files["pacote_projeto.zip"] = zbuf.getvalue()
    return files
