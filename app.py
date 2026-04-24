import streamlit as st
import cv2
import numpy as np
import pandas as pd
from pdf2image import convert_from_path, pdfinfo_from_path 
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
import tempfile, io, gc, pytz
from datetime import datetime

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Super Perseu - IP", page_icon="📝", layout="centered")

# --- LOGO ---
st.image("https://www.institutoponte.org.br/wp-content/uploads/2025/02/Logo-Instituto-Ponto.png", width=220)
st.title("Correção Automática de Gabaritos")

with st.sidebar:
    st.header("Informações")
    serie = st.selectbox("Série:", ["7º Ano", "8º Ano", "9º Ano", "1ª Série", "2ª Série"])
    polo = st.text_input("Polo:", placeholder="Ex: Bela Cruz")
    st.info("💡 Modo 'Tons de Cinza' ativado no scanner.")

# --- ENTRADA DE GABARITO ---
st.subheader("1. Gabarito Oficial")
gabarito_inputs = {}
for label, range_q in [("Português", range(1, 11)), ("Matemática", range(11, 21))]:
    st.write(f"**{label}**")
    cols = st.columns(10)
    for i in range_q:
        gabarito_inputs[i] = cols[(i-1)%10].text_input(f"Q{i}", "A", key=f"q{i}", max_chars=1).upper()

# --- FUNÇÕES CORE ---
def isolar_blocos(img_original):
    """Encontra os blocos de questões usando binarização simples"""
    cinza = cv2.cvtColor(img_original, cv2.COLOR_BGR2GRAY)
    # Binarização rápida para achar as âncoras (quadrados pretos)
    _, binario = cv2.threshold(cinza, 150, 255, cv2.THRESH_BINARY_INV)
    
    h_total, w_total = binario.shape[:2]
    contornos, _ = cv2.findContours(binario, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    marcadores = []
    
    for c in contornos:
        if 900 <= cv2.contourArea(c) <= 1600:
            x, y, w, h = cv2.boundingRect(c)
            if 0.7 <= (w/h) <= 1.3 and (y + h/2) > (h_total * 0.3):
                marcadores.append([x + w//2, y + h//2])

    if len(marcadores) < 8: return None, None
    x_m = w_total / 2
    m_e = sorted([p for p in marcadores if p[0] < x_m], key=lambda x: x[1])
    m_d = sorted([p for p in marcadores if p[0] >= x_m], key=lambda x: x[1])
    
    if len(m_e) < 4 or len(m_d) < 4: return None, None

    def warp(pts, original):
        pts = np.array(pts[:4], dtype="float32")
        # Ordenação: Top-Left, Top-Right, Bottom-Right, Bottom-Left
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)
        ordenados = np.array([pts[np.argmin(s)], pts[np.argmin(diff)], pts[np.argmax(s)], pts[np.argmax(diff)]], dtype="float32")
        destino = np.array([[0,0], [628,0], [628,1093], [0,1093]], dtype="float32")
        matriz = cv2.getPerspectiveTransform(ordenados, destino)
        # Retorna o bloco já em cinza para facilitar leitura
        return cv2.warpPerspective(cinza, matriz, (629, 1094))

    return warp(m_e, cinza), warp(m_d, cinza)

def ler_bolinhas(bloco_cinza, q_ini):
    # Transforma o bloco em binário apenas para contar a tinta
    _, bloco_bin = cv2.threshold(bloco_cinza, 220, 255, cv2.THRESH_BINARY_INV)
    
    res = {}
    xi, yi, px, py, r, lim = 89, 78, 110, 104, 31, 0.30
    for i in range(10):
        marcadas = []
        for j in range(5):
            # Recorta a bolinha e conta pixels pretos
            bolinha = bloco_bin[yi+i*py-r : yi+i*py+r, xi+j*px-r : xi+j*px+r]
            if (cv2.countNonZero(bolinha) / bolinha.size) > lim:
                marcadas.append(chr(65+j))
        
        if len(marcadas) == 1: res[q_ini+i] = marcadas[0]
        elif len(marcadas) > 1: res[q_ini+i] = "ANULADA"
        else: res[q_ini+i] = "EM BRANCO"
    return res

# --- PROCESSO ---
st.divider()
pdf_files = st.file_uploader("Upload de Gabaritos", type=["pdf"], accept_multiple_files=True)

if st.button("🚀 Iniciar Correção", type="primary"):
    if not pdf_files or not polo:
        st.error("Preencha o Polo e envie os arquivos.")
    else:
        dados, num_global = [], 1
        with st.spinner("Corrigindo..."):
            for file in pdf_files:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(file.read())
                    path = tmp.name
                
                total_pags = pdfinfo_from_path(path)["Pages"]
                for p in range(1, total_pags + 1):
                    # thread_count=4 acelera a renderização do PDF
                    pag = convert_from_path(path, dpi=300, first_page=p, last_page=p, thread_count=4)[0]
                    img = cv2.cvtColor(np.array(pag), cv2.COLOR_RGB2BGR)
                    
                    be, bd = isolar_blocos(img)
                    resp = {}
                    if be is not None and bd is not None:
                        resp.update(ler_bolinhas(be, 1))
                        resp.update(ler_bolinhas(bd, 11))
                        ac_p = sum(1 for q in range(1, 11) if resp[q] == gabarito_inputs[q])
                        ac_m = sum(1 for q in range(11, 21) if resp[q] == gabarito_inputs[q])
                    else:
                        ac_p, ac_m = 0, 0
                        resp = {q: "ERRO_LEITURA" for q in range(1, 21)}

                    linha = {"Gabarito": f"Nº {num_global:04d}", **{f"Q{q}": resp[q] for q in range(1, 21)}, "PT": ac_p, "MT": ac_m}
                    dados.append(linha)
                    num_global += 1
                    gc.collect()

        if dados:
            df = pd.DataFrame(dados)
            out = io.BytesIO()
            df.to_excel(out, index=False)
            
            # Formatação de Cores
            wb = load_workbook(io.BytesIO(out.getvalue()))
            ws = wb.active
            ws.insert_rows(2)
            ws.cell(2,1, "Gabarito").font = Font(bold=True, color="0000FF")
            for q in range(1, 21): ws.cell(2, q+1, gabarito_inputs[q]).font = Font(bold=True)
            
            C_OK, C_ER, C_AN = PatternFill("solid", "C6EFCE"), PatternFill("solid", "FFC7CE"), PatternFill("solid", "FFEB9C")
            for r in range(3, ws.max_row + 1):
                for c in range(2, 22):
                    cell = ws.cell(r, c)
                    if cell.value == gabarito_inputs[c-1]: cell.fill = C_OK
                    elif cell.value == "ANULADA": cell.fill = C_AN
                    elif cell.value not in ["EM BRANCO", "ERRO_LEITURA"]: cell.fill = C_ER
            
            final = io.BytesIO()
            wb.save(final)
            st.success(f"Finalizado! {num_global-1} gabaritos corrigidos.")
            st.download_button("📥 Baixar Planilha", final.getvalue(), f"Resultados_{polo}.xlsx", type="primary")

st.markdown("---")
st.caption(f"Super Perseu | {datetime.now(pytz.timezone('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M')}")
