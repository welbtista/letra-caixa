import base64

import streamlit as st

import engine as eg

st.set_page_config(page_title="Engenharia Visual | Letras-caixa", page_icon="🔠", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Sora:wght@600;700;800&display=swap');
:root { --bg:#070b17; --panel:#0e1530; --panel2:#141d3f; --line:rgba(255,255,255,.09); --txt:#e9edfb; --mut:#98a3c7;
        --org:#ff6b2c; --gold:#ffb938; --blue:#4d8bff; }
html, body, .stApp { color-scheme: dark; font-family:'Inter',sans-serif; color:var(--txt); }
.stApp { background: radial-gradient(1200px 600px at 85% -10%, rgba(77,139,255,.18), transparent 60%),
                     radial-gradient(900px 500px at -10% 10%, rgba(255,107,44,.12), transparent 55%), var(--bg); }
#MainMenu, footer, header[data-testid="stHeader"] { visibility:hidden; height:0; }
.block-container { padding-top:1.6rem; max-width:1280px; }
h1,h2,h3,h4 { font-family:'Sora',sans-serif; color:var(--txt); letter-spacing:-.3px; }
.stMarkdown, .stMarkdown p, .stMarkdown li, .stCaption, [data-testid="stCaptionContainer"] { color:var(--txt); }
[data-testid="stCaptionContainer"] { color:var(--mut); }

/* HERO */
.hero { position:relative; overflow:hidden; border-radius:24px; padding:30px 36px; margin-bottom:24px;
        background: linear-gradient(135deg, rgba(20,29,63,.95), rgba(10,16,38,.95)); border:1px solid var(--line);
        box-shadow: 0 20px 60px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.06); }
.hero:before { content:""; position:absolute; right:-120px; top:-140px; width:420px; height:420px; border-radius:50%;
        background: radial-gradient(circle, rgba(255,107,44,.45), transparent 65%); }
.hero:after { content:""; position:absolute; left:35%; bottom:-200px; width:420px; height:420px; border-radius:50%;
        background: radial-gradient(circle, rgba(77,139,255,.28), transparent 65%); }
.hero > * { position:relative; z-index:1; }
.brand { display:flex; align-items:center; gap:14px; margin-bottom:6px; }
.logo { width:46px; height:46px; border-radius:14px; display:flex; align-items:center; justify-content:center;
        font-family:'Sora',sans-serif; font-weight:800; color:#0b1020; font-size:1.05rem;
        background:linear-gradient(135deg,var(--gold),var(--org)); box-shadow:0 8px 24px rgba(255,107,44,.45); }
.hero h1 { font-size:2.15rem; font-weight:800; margin:0; padding:0; line-height:1.1;
        background:linear-gradient(90deg,#fff,#c9d6ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.badge { display:inline-block; border:1px solid rgba(255,185,56,.45); color:var(--gold); background:rgba(255,185,56,.08);
        padding:3px 12px; border-radius:999px; font-size:.72rem; font-weight:700; letter-spacing:.8px; text-transform:uppercase; }
.hero p { color:var(--mut); margin:8px 0 18px 0; font-size:1.02rem; max-width:760px; }
.steps { display:flex; gap:10px; flex-wrap:wrap; }
.step { background:rgba(255,255,255,.05); border:1px solid var(--line); border-radius:12px; padding:8px 14px;
        font-size:.85rem; font-weight:600; color:var(--txt); backdrop-filter: blur(6px); }
.step b { display:inline-block; width:22px; height:22px; line-height:22px; text-align:center; border-radius:50%; margin-right:8px;
        background:linear-gradient(135deg,var(--gold),var(--org)); color:#0b1020; font-size:.75rem; }

/* KPIs */
.kpi-grid { display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin:8px 0 16px 0; }
.kpi { position:relative; background:linear-gradient(160deg, rgba(255,255,255,.07), rgba(255,255,255,.02));
       border:1px solid var(--line); border-radius:18px; padding:16px 18px; overflow:hidden; }
.kpi:before { content:""; position:absolute; left:0; top:0; height:3px; width:100%; background:linear-gradient(90deg,var(--org),var(--gold)); opacity:.9; }
.kpi-l { font-size:.7rem; text-transform:uppercase; letter-spacing:1px; color:var(--mut); font-weight:700; }
.kpi-v { font-family:'Sora',sans-serif; font-size:1.7rem; font-weight:800; margin-top:4px;
         background:linear-gradient(90deg,#fff,#cfd9ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.kpi-s { font-size:.78rem; color:var(--mut); }
@media (max-width:900px){ .kpi-grid{ grid-template-columns:repeat(2,1fr);} }

/* Cartões */
.card { background:linear-gradient(160deg, rgba(255,255,255,.06), rgba(255,255,255,.015)); border:1px solid var(--line);
        border-radius:18px; padding:20px 22px; }
.card h4 { margin:6px 0 6px 0; color:var(--txt); font-size:1.05rem; }
.card p { color:var(--mut); font-size:.9rem; margin:0; }
.feat { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:6px 0 18px 0; }
@media (max-width:900px){ .feat{ grid-template-columns:1fr;} }
.feat .ico { font-size:1.6rem; }

/* Legenda */
.legend { display:grid; grid-template-columns:repeat(2,1fr); gap:10px 22px; background:rgba(255,255,255,.035);
          border:1px solid var(--line); border-radius:16px; padding:16px 20px; margin:10px 0 6px 0; }
@media (max-width:900px){ .legend{ grid-template-columns:1fr;} }
.lg { display:flex; gap:12px; align-items:flex-start; color:var(--mut); font-size:.83rem; line-height:1.35; }
.lg b { color:var(--txt); font-size:.78rem; letter-spacing:.4px; }
.sw { flex:0 0 30px; height:6px; border-radius:6px; margin-top:7px; box-shadow:0 0 10px currentColor; }
.legend-title { font-family:'Sora',sans-serif; font-weight:700; color:var(--txt); margin:18px 0 4px 0; font-size:1.05rem; }

/* Downloads */
.dl { display:flex; gap:16px; align-items:center; background:linear-gradient(160deg, rgba(255,255,255,.06), rgba(255,255,255,.015));
      border:1px solid var(--line); border-radius:18px; padding:16px 20px; margin:0 0 8px 0; }
.dl-i { font-size:1.9rem; }
.dl b { color:var(--txt); }
.dl span { color:var(--mut); font-size:.84rem; }
.dl code { font-size:.74rem; color:var(--gold); background:rgba(255,185,56,.1); padding:1px 7px; border-radius:6px; }

/* Barra lateral */
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0c1330,#080d20); border-right:1px solid var(--line); }
[data-testid="stSidebar"] h2 { font-family:'Sora',sans-serif; font-weight:800; color:var(--txt); }
[data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] .stMarkdown { color:var(--mut); }
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] *, label, label * { color:var(--mut) !important; font-size:.82rem; font-weight:500; }
div[data-testid="stExpander"] { background:rgba(255,255,255,.03); border:1px solid var(--line); border-radius:14px; overflow:hidden; }
div[data-testid="stExpander"] summary, div[data-testid="stExpander"] summary * { background:transparent !important; color:var(--txt) !important; font-weight:600; }
div[data-baseweb="input"], div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {
        background:#121b3b !important; border-color:rgba(255,255,255,.12) !important; border-radius:10px !important; }
input, textarea, div[data-baseweb="select"] * { color:var(--txt) !important; -webkit-text-fill-color:var(--txt) !important; }
div[data-baseweb="input"] button { background:transparent !important; color:var(--mut) !important; }
[data-baseweb="popover"] *, ul[role="listbox"], li[role="option"] { background:#121b3b; color:var(--txt); }
[data-testid="stCheckbox"] span { color:var(--txt) !important; }

/* Abas */
.stTabs [data-baseweb="tab-list"] { gap:6px; background:rgba(255,255,255,.04); padding:6px; border-radius:16px; border:1px solid var(--line); }
.stTabs [data-baseweb="tab"] { height:auto; padding:9px 18px; border-radius:11px; background:transparent; }
.stTabs [data-baseweb="tab"], .stTabs [data-baseweb="tab"] * { color:var(--mut) !important; font-weight:600; }
.stTabs [aria-selected="true"] { background:linear-gradient(135deg,var(--org),#ff8a1f) !important; box-shadow:0 6px 18px rgba(255,107,44,.35); }
.stTabs [aria-selected="true"], .stTabs [aria-selected="true"] * { color:#fff !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }

/* Botões e upload */
.stDownloadButton button, .stButton button { border:0; border-radius:12px; font-weight:700; padding:.55rem 1.3rem;
        background:linear-gradient(135deg,var(--org),var(--gold)); color:#0b1020 !important; box-shadow:0 8px 20px rgba(255,107,44,.3); }
.stDownloadButton button:hover { filter:brightness(1.08); transform:translateY(-1px); }
.stDownloadButton button * { color:#0b1020 !important; }
div[data-testid="stFileUploader"] section { background:linear-gradient(160deg, rgba(77,139,255,.10), rgba(255,255,255,.02));
        border:2px dashed rgba(255,185,56,.55); border-radius:18px; padding:26px; }
div[data-testid="stFileUploader"] section * { color:var(--txt) !important; }
div[data-testid="stFileUploader"] section button { background:rgba(255,255,255,.08) !important; border:1px solid var(--line) !important; border-radius:10px; }
div[data-testid="stFileUploaderFile"] { background:rgba(255,255,255,.05); border-radius:10px; }

/* Alertas e tabelas */
[data-testid="stAlert"] { border-radius:14px; border:1px solid var(--line); }
[data-testid="stAlert"] * { color:var(--txt) !important; }
[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }
img.preview { width:100%; border:1px solid var(--line); border-radius:18px; box-shadow:0 18px 50px rgba(0,0,0,.45); }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="brand"><div class="logo">EV</div><span class="badge">v1.0 · ACM + Acrílico · Router CNC</span></div>
  <h1>Engenharia Visual</h1>
  <p>Do logotipo em SVG ao arquivo de corte: frente, fundo, paredes com emendas, nesting e DXF prontos para a CNC.</p>
  <div class="steps">
    <div class="step"><b>1</b>Envie o SVG</div>
    <div class="step"><b>2</b>Ajuste as medidas</div>
    <div class="step"><b>3</b>Confira a prévia</div>
    <div class="step"><b>4</b>Baixe os arquivos</div>
  </div>
</div>
""", unsafe_allow_html=True)

CUT_LAYERS = ["CORTE_EXTERNO", "CORTE_INTERNO", "REFERENCIA", "ROTULO", "CHAPA"]
ASSEMBLY_LAYERS = ["FRENTE_ACRILICO", "FUNDO_ACM", "PAREDES_EIXO", "CANTOS"]
ALL_LAYERS = CUT_LAYERS + ASSEMBLY_LAYERS


def legend_html(names):
    rows = eg.legend_rows(names)
    items = "".join(
        f'<div class="lg"><span class="sw" style="background:{r["cor_hex"]};color:{r["cor_hex"]}"></span>'
        f'<div><b>{r["camada"]}</b><br>{r["descricao"]}</div></div>' for r in rows)
    return f'<div class="legend">{items}</div>'


def kpi(label, value, sub=""):
    return f'<div class="kpi"><div class="kpi-l">{label}</div><div class="kpi-v">{value}</div><div class="kpi-s">{sub}</div></div>'


SCALE_MODES = {
    "Ajustar dentro da área (largura × altura)": "fit",
    "Fixar a largura": "width",
    "Fixar a altura": "height",
    "Tamanho original do SVG (96 dpi)": "original",
}
PROFILES = {
    "Acrílico sobre as paredes (sobreposto)": "overlay",
    "Acrílico entre as paredes (embutido)": "recess",
}

with st.sidebar:
    st.header("⚙️ Configuração")
    with st.expander("Dimensões", expanded=True):
        mode_label = st.selectbox("Modo de escala", list(SCALE_MODES))
        width = st.number_input("Largura final (mm)", min_value=1.0, value=2000.0)
        height = st.number_input("Altura final máxima (mm)", min_value=1.0, value=800.0)
    with st.expander("Construção", expanded=True):
        depth = st.number_input("Profundidade externa total (mm)", min_value=5.0, value=50.0)
        acrylic = st.number_input("Acrílico frontal (mm)", min_value=1.0, value=3.0)
        acm = st.number_input("ACM lateral/fundo (mm)", min_value=1.0, value=3.0)
        profile_label = st.selectbox("Perfil frontal", list(PROFILES))
        profile = PROFILES[profile_label]
        if profile == "overlay":
            front_offset = st.number_input("Sobra (+) / recuo (−) do acrílico (mm)", value=0.0)
            fit_clearance = 0.3
        else:
            front_offset = 0.0
            fit_clearance = st.number_input("Folga do acrílico nas paredes (mm)", min_value=0.0, value=0.3)
        back_offset = st.number_input("Sobra (+) / recuo (−) do fundo (mm)", value=0.0)
        joint_comp = st.checkbox("Compensar emendas de canto (junta de topo)", value=True)
    with st.expander("Máquina e chapas", expanded=False):
        router = st.number_input("Diâmetro da fresa (mm)", min_value=0.1, value=3.0)
        tool_comp = st.checkbox("Compensar fresa no caminho de corte", value=True)
        part_gap = st.number_input("Folga livre entre caminhos (mm)", min_value=0.0, value=4.0)
        sheet_margin = st.number_input("Margem da borda da chapa (mm)", min_value=0.0, value=5.0)
        st.markdown("**ACM** (largura × comprimento)")
        acm_w = st.number_input("ACM largura (mm)", min_value=50.0, value=1250.0)
        acm_l = st.number_input("ACM comprimento (mm)", min_value=50.0, value=5000.0)
        st.markdown("**Acrílico** (largura × comprimento)")
        acr_w = st.number_input("Acrílico largura (mm)", min_value=50.0, value=2000.0)
        acr_l = st.number_input("Acrílico comprimento (mm)", min_value=50.0, value=3000.0)
    with st.expander("Tiras e cantos", expanded=False):
        max_strip = st.number_input("Comprimento máximo de tira (mm)", min_value=50.0, value=1000.0)
        corner_angle = st.number_input("Ângulo mínimo para considerar canto (°)", min_value=5.0, max_value=170.0, value=35.0)
        corner_window = st.number_input("Janela de detecção de canto (mm)", min_value=0.5, value=2.0)
        min_bend = st.number_input("Raio mínimo de curva da parede (mm)", min_value=1.0, value=30.0)
        min_clear = st.number_input("Largura interna mínima p/ LED (mm)", min_value=1.0, value=20.0)
    with st.expander("Leitura do SVG", expanded=False):
        sample_step = st.number_input("Amostragem de curva (mm)", min_value=0.1, value=0.5)
        simplify_tol = st.number_input("Tolerância de simplificação (mm)", min_value=0.0, value=0.02, format="%.3f")
        autoclose = st.number_input("Fechar caminhos com folga até (mm)", min_value=0.0, value=0.5)
        min_area = st.number_input("Descartar fragmentos menores que (mm²)", min_value=0.0, value=1.0)
    with st.expander("Estimativa de LED", expanded=False):
        led = st.checkbox("Estimar módulos e fonte", value=False)
        led_density = st.number_input("Módulos por m² de área interna", min_value=1.0, value=25.0)
        led_watts = st.number_input("Potência por módulo (W)", min_value=0.1, value=0.72)

upload = st.file_uploader("Arraste aqui a logomarca em SVG (textos convertidos em curvas)", type=["svg"])
if not upload:
    st.markdown("""
<div class="feat">
  <div class="card"><div class="ico">🧩</div><h4>Peças completas</h4><p>Frente de acrílico, fundo de ACM e paredes laterais com compensação de cantos.</p></div>
  <div class="card"><div class="ico">📐</div><h4>Pronto para a CNC</h4><p>Nesting automático em chapas e caminho de corte já compensado pelo diâmetro da fresa.</p></div>
  <div class="card"><div class="ico">🎨</div><h4>Cores explicadas</h4><p>Cada cor de linha do DXF vem com legenda dentro do arquivo e em um texto separado.</p></div>
</div>
""", unsafe_allow_html=True)
    st.markdown('<div class="legend-title">Como ler as cores dos arquivos DXF</div>', unsafe_allow_html=True)
    st.markdown(legend_html(ALL_LAYERS), unsafe_allow_html=True)
    st.stop()

params = eg.Params(
    width=width, height=height, scale_mode=SCALE_MODES[mode_label],
    depth=depth, acrylic=acrylic, acm=acm, profile=profile,
    front_offset=front_offset, back_offset=back_offset, fit_clearance=fit_clearance,
    tool_d=router, tool_comp=tool_comp, part_gap=part_gap, sheet_margin=sheet_margin,
    acm_sheet_w=acm_w, acm_sheet_l=acm_l, acr_sheet_w=acr_w, acr_sheet_l=acr_l,
    sample_step=sample_step, simplify_tol=simplify_tol, autoclose_gap=autoclose, min_area=min_area,
    max_strip=max_strip, corner_angle=corner_angle, corner_window=corner_window,
    joint_comp=joint_comp, min_bend_radius=min_bend, min_clear=min_clear,
    led=led, led_density=led_density, led_watts=led_watts,
)


@st.cache_resource(show_spinner="Processando geometria e nesting...", max_entries=8)
def process(svg_bytes: bytes, prm: eg.Params):
    res = eg.run(svg_bytes, prm)
    files = eg.build_outputs(res) if not res.errors else {}
    return res, files


def show_svg(svg: str):
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    st.markdown(f'<img class="preview" src="data:image/svg+xml;base64,{b64}">',
                unsafe_allow_html=True)


try:
    res, files = process(upload.getvalue(), params)
except Exception as e:  # erro inesperado: mostra detalhe
    st.exception(e)
    st.stop()

for e in res.errors:
    st.error(e)
if res.errors:
    st.stop()

s = res.stats
st.markdown('<div class="kpi-grid">' + "".join([
    kpi("Tamanho", f"{res.actual_w:.0f}×{res.actual_h:.0f}", "mm (largura × altura)"),
    kpi("Peças", s["pecas"], f"{s['tiras']} tiras de parede"),
    kpi("Chapas ACM", s["chapas_acm"], f"{s['area_acm_m2']:.2f} m² de material"),
    kpi("Chapas acrílico", s["chapas_acrilico"], f"{s['area_acrilico_m2']:.2f} m² de material"),
    kpi("Corte total", f"{s['comprimento_corte_m']:.1f} m", f"{s['cantos_detectados']} cantos • parede {s['altura_parede_mm']:.0f} mm"),
]) + "</div>", unsafe_allow_html=True)

if res.warnings:
    st.warning(f"{len(res.warnings)} aviso(s) — veja a aba Validação antes de cortar.")
else:
    st.success("Nenhum aviso de geometria. Faça uma peça-teste antes do lote.")

tab_prev, tab_pecas, tab_chapas, tab_val, tab_dl = st.tabs(
    ["Visão geral", "Peças e tiras", "Chapas (nesting)", "Validação", "Downloads"])

with tab_prev:
    show_svg(eg.preview_assembly(res))
    st.markdown(legend_html(ASSEMBLY_LAYERS), unsafe_allow_html=True)
    if params.led:
        st.info(f"Estimativa LED: ~{s['led_modulos_estimados']} módulos, ~{s['led_potencia_w_estimada']} W; "
                f"fonte sugerida ≥ {s['led_fonte_sugerida_w']} W (margem de 25%). Indicativo, não substitui projeto elétrico.")

with tab_pecas:
    st.markdown("**Lista de corte**")
    st.dataframe(eg.cut_list_rows(res), use_container_width=True, hide_index=True)
    st.markdown("**Resumo por peça**")
    st.dataframe([{"peça": pt.label, "tiras": pt.n_strips, "cantos": len(pt.corners),
                   "raio mín. curva (mm)": None if pt.min_bend_r is None else round(pt.min_bend_r, 1),
                   "área (cm²)": round(pt.outline.area / 100, 1), "perímetro (mm)": round(pt.outline.length, 1)}
                  for pt in res.parts], use_container_width=True, hide_index=True)

with tab_chapas:
    mats = list(res.nest.keys())
    if not mats:
        st.info("Sem chapas.")
    else:
        mat = st.radio("Material", mats, format_func=lambda m: res.nest[m]["title"], horizontal=True)
        info = res.nest[mat]
        n = len(info["sheets"])
        idx = st.slider("Chapa", 1, n, 1) - 1 if n > 1 else 0
        sh = info["sheets"][idx]
        st.caption(f"Chapa {idx + 1}/{n} • {info['sheet_l']:g} × {info['sheet_w']:g} mm • {len(sh['placed'])} peças • "
                   f"aproveitamento {100 * sh['util']:.1f}% (área das peças)")
        show_svg(eg.preview_sheet(res, mat, idx))
        st.markdown(legend_html(["CORTE_EXTERNO", "CORTE_INTERNO", "CHAPA"]), unsafe_allow_html=True)

with tab_val:
    for m in res.warnings:
        st.warning(m)
    for m in res.infos:
        st.info(m)
    if not res.warnings and not res.infos:
        st.success("Sem avisos.")
    with st.expander("Premissas de fabricação"):
        st.markdown(
            "- Paredes de ACM em torno da linha neutra (contorno recuado de ACM/2); comprimento medido nela.\n"
            "- Cantos: junta de topo — uma tira avança e a outra recua conforme o ângulo; corte reto (sem chanfro 3D).\n"
            "- Curvas: tiras contínuas, sujeitas ao raio mínimo de dobra do seu processo.\n"
            "- Caminho de fresa = contorno deslocado em ½ fresa; furos menores que a fresa são avisados.\n"
            "- Sem pontes (tabs), ordem/profundidade de passes ou pós-processador: configure no software da máquina."
        )

with tab_dl:
    FILES = [
        ("pacote_projeto.zip", "📦", "Pacote completo", "Todos os arquivos abaixo em um só ZIP."),
        ("chapas_acm.dxf", "🟦", "DXF de corte — ACM", "Paredes e fundo já distribuídos nas chapas, com fresa compensada."),
        ("chapas_acrilico.dxf", "🔷", "DXF de corte — acrílico", "Frentes distribuídas nas chapas de acrílico."),
        ("referencia_montagem.dxf", "🧱", "DXF de montagem", "Visão das peças montadas e dos cantos. Não é para cortar."),
        ("lista_de_corte.csv", "📋", "Lista de corte", "Todas as peças, medidas e chapa de cada uma (abre no Excel)."),
        ("LEGENDA_CORES.txt", "🎨", "Legenda das cores", "Explica o que cada cor de linha significa nos DXF."),
        ("relatorio_projeto.json", "🧾", "Relatório técnico", "Parâmetros, estatísticas e avisos."),
    ]
    mimes = {"zip": "application/zip", "dxf": "application/dxf", "csv": "text/csv", "json": "application/json", "txt": "text/plain"}
    cols = st.columns(2)
    n = 0
    for fn, icon, title, desc in FILES:
        if fn not in files:
            continue
        with cols[n % 2]:
            st.markdown(f'<div class="dl"><div class="dl-i">{icon}</div><div><b>{title}</b><br><span>{desc}</span><br>'
                        f'<code>{fn}</code></div></div>', unsafe_allow_html=True)
            st.download_button("Baixar", files[fn], file_name=fn, mime=mimes[fn.rsplit(".", 1)[1]], key=fn)
        n += 1
    st.markdown('<div class="legend-title">O que significa cada cor de linha nos DXF</div>', unsafe_allow_html=True)
    st.markdown("**Chapas de corte**")
    st.markdown(legend_html(CUT_LAYERS), unsafe_allow_html=True)
    st.markdown("**Montagem**")
    st.markdown(legend_html(ASSEMBLY_LAYERS), unsafe_allow_html=True)
    st.caption("Essa mesma legenda também está desenhada dentro de cada DXF (à esquerda da chapa), na camada LEGENDA — desative-a antes de cortar.")
