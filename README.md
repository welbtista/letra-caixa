# Engenharia Visual — Gerador de letras-caixa v1.0

## O que faz
- Lê SVG (resolve grupos/transformações, retângulos, círculos, polígonos; contornos internos viram furos — regra even-odd).
- Escala a logo (ajustar à área, fixar largura/altura ou tamanho original).
- Para cada letra/forma gera: **frente de acrílico**, **fundo de ACM** e **paredes laterais** (tiras na linha neutra).
- Detecta **cantos** e compensa as emendas (junta de topo: uma tira avança, a outra recua conforme o ângulo). Curvas ficam em tiras contínuas, divididas pelo comprimento máximo.
- Perfil frontal: acrílico sobreposto ou embutido entre as paredes.
- **Nesting** automático em chapas (ACM e acrílico, tamanhos independentes), com rotação 0/90°.
- **Compensação da fresa** no DXF de corte (camadas CORTE_INTERNO / CORTE_EXTERNO), aviso de furos menores que a fresa.
- Validações: caminhos abertos, auto-interseção (reparo), raio mínimo de curva, largura interna para LED, peças que não cabem na chapa.
- Saídas: `chapas_acm.dxf`, `chapas_acrilico.dxf`, `referencia_montagem.dxf`, `lista_de_corte.csv`, `relatorio_projeto.json`, ZIP.

## Instalação
Python 3.10+
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Preparação do SVG
Converta textos em curvas; use contornos fechados; evite máscaras/clipPath (aplique no editor).

## Limites (leia antes de cortar)
Faça sempre uma **peça-teste** antes do lote. Não incluso: pontes (tabs), ordem/profundidade de passes e pós-processador (faça no software da CNC), chanfro 3D nas emendas, entalhes de dobra no ACM, projeto elétrico (a estimativa de LED é indicativa).
