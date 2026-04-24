import streamlit as st
import cv2
import numpy as np
import pandas as pd
from pdf2image import convert_from_path, pdfinfo_from_path 
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
import tempfile
import io
import gc 
from datetime import datetime
import pytz

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="SCA - Instituto Ponte", page_icon="📝", layout="centered")

# --- LOGO ---
URL_LOGO = "https://www.institutoponte.org.br/wp-content/uploads/2025/02/Logo-Instituto-Ponto.png"
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    st.image(URL_LOGO, width=250)

def isolar_blocos_simples(imagem_binaria):
    """Localiza as âncoras usando a imagem já binarizada"""
    altura_total, largura_total = imagem_binaria.shape[:2]
    y_limite_superior = int(altura_total * 0.30)
    area_min, area_max = 900, 1600 
    
    # Como a imagem já vem binarizada e com contraste, apenas aplicamos um leve desfoque para limpar
    desfoque = cv2.GaussianBlur(imagem_binaria, (3, 3), 0)
    contornos, _ = cv2.findContours(desfoque, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    marcadores = []
    for c in contornos:
        perimetro = cv2.arcLength(c, True)
        aprox = cv2.approxPolyDP(c, 0.05 * perimetro, True)
        area = cv2.contourArea(c)
        if len(aprox) == 4 and area_min <= area <= area_max:
            x, y, w, h = cv2.boundingRect(aprox)
            if 0.7 <= (w / float(h)) <= 1.3:
                cx, cy = x + (w//2), y + (h//2)
                if cy > y_limite_superior:
                    marcadores.append([cx, cy])

    if len(marcadores) < 8: return None, None
    x_meio = largura_total / 2
    m_esq = [p for p in marcadores if p[0] < x_meio]
    m_dir = [p for p in marcadores if p[0] >= x_meio]
    
    if len(m_esq) < 4 or len(m_dir) < 4: return None, None

    def ordenar_4(pts):
        pts_arr = np.array(pts)
        ret = np.zeros((4, 2), dtype="float32")
        s = pts_arr.sum(axis=1)
        ret[0], ret[2] = pts_arr[np.argmin(s)], pts_arr[np.argmax(s)]
        d = np.diff(pts_arr, axis=1)
        ret[1], ret[3] = pts_arr[np.argmin(d)], pts_arr[np.argmax(d)]
        return ret

    def processar(pts):
        origem = ordenar_4(pts)
        destino = np.array([[0,0], [628,0], [628,1093], [0,1093]], dtype="float32")
        matriz = cv2.getPerspectiveTransform(origem, destino)
        return cv2.warpPerspective(imagem_binaria, matriz, (629, 1094))

    return processar(m_esq), processar(m_dir)

def ler_bolinhas_simples(img_binaria_bloco, q_ini):
    """Lê as bolinhas na imagem que já está em preto e branco"""
    respostas = {}
    alts = ['A', 'B', 'C', 'D', 'E']
    xi, yi, px, py, raio = 89, 78, 110, 104, 31
    
    # Limite
    limite = 0.30

    for i in range(10): 
        marcadas = []
        for j in range(5): 
            cx, cy = xi + (j * px), yi + (i * py)
            celula = img_binaria_bloco[cy-raio : cy+raio, cx-raio : cx+raio]
            if celula.size > 0 and (cv2.countNonZero(celula) / celula.size) > limite:
                marcadas.append(alts[j])
        
        if len(marcadas) == 0: respostas[q_ini+i] = "EM BRANCO"
        elif len(marcadas) > 1: respostas[q_ini+i] = "ANULADA"
        else: respostas[q_ini+i] = marcadas[0]
    return respostas

# --- INTERFACE ---
st.title("Correção Automática de Gabaritos")
st.markdown("Processo Seletivo - Instituto Ponte 2026")

st.subheader("1. Identificação e Gabarito")
c1, c2 = st.columns(2)
serie_escolhida = c1.selectbox("Selecione a Série:", ["7º Ano", "8º Ano", "9º Ano", "1ª Série", "2ª Série"])
polo_escolhido = c2.text_input("Polo:", placeholder="Ex: Bela Cruz")

st.divider()
gabarito_inputs = {}

st.markdown("#### 📚 Português (01 a 10)")
cols_pt = st.columns(10)
for i in range(1, 11):
    gabarito_inputs[i] = cols_pt[i-1].text_input(f"Q{i}", "A", key=f"q{i}", max_chars=1).upper()

st.markdown("#### 📐 Matemática (11 a 20)")
cols_mt = st.columns(10)
for i in range(11, 21):
    gabarito_inputs[i] = cols_mt[i-11].text_input(f"Q{i}", "A", key=f"q{i}", max_chars=1).upper()

st.divider()
arquivos_pdf = st.file_uploader("Arraste os PDFs aqui", type=["pdf"], accept_multiple_files=True)

if st.button("🚀 Iniciar Correção", type="primary"):
    if not arquivos_pdf or not polo_escolhido:
        st.error("Preencha todos os campos e envie o PDF.")
    else:
        total_pags = 0
        arquivos_info = []
        for file in arquivos_pdf:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file.read())
                tmp_path = tmp.name
                total_pags += pdfinfo_from_path(tmp_path)["Pages"]
                arquivos_info.append((tmp_path, pdfinfo_from_path(tmp_path)["Pages"]))

        dados = []
        num_global = 1
        bar = st.progress(0)
        status = st.empty()

        for tmp_path, pags_no_file in arquivos_info:
            for p in range(1, pags_no_file + 1):
                bar.progress((num_global - 1) / total_pags)
                status.text(f"Processando Gabarito {num_global}...")
                
                # 1. Converte PDF para Imagem
                pag_pil = convert_from_path(tmp_path, dpi=300, first_page=p, last_page=p)[0]
                img = cv2.cvtColor(np.array(pag_pil), cv2.COLOR_RGB2BGR)
                
                # 2. AUMENTA CONTRASTE E BRILHO (Simplificado)
                # Alpha 1.5 (Contraste), Beta 0 (Brilho)
                img_enhanced = cv2.convertScaleAbs(img, alpha=1.5, beta=0)
                
                # 3. FORÇA PRETO E BRANCO (Binarização Global)
                cinza = cv2.cvtColor(img_enhanced, cv2.COLOR_BGR2GRAY)
                # Threshold:
                _, binario = cv2.threshold(cinza, 200, 255, cv2.THRESH_BINARY_INV)
                
                # 4. Isola e Lê
                bloco_e, bloco_d = isolar_blocos_simples(binario)
                resp = {}
                if bloco_e is not None and bloco_d is not None:
                    resp.update(ler_bolinhas_simples(bloco_e, 1))
                    resp.update(ler_bolinhas_simples(bloco_d, 11))
                    ac_pt = sum(1 for q in range(1, 11) if resp.get(q) == gabarito_inputs[q])
                    ac_mt = sum(1 for q in range(11, 21) if resp.get(q) == gabarito_inputs[q])
                else:
                    ac_pt, ac_mt = 0, 0
                    for q in range(1, 21): resp[q] = "ERRO_LEITURA"

                linha = {"Questão/Gabarito": f"Nº {num_global:04d}"}
                for q in range(1, 21): linha[f"Q{q}"] = resp.get(q)
                linha["Português"], linha["Matemática"] = ac_pt, ac_mt
                dados.append(linha)
                num_global += 1
                gc.collect()

        bar.progress(1.0)
        if dados:
            df = pd.DataFrame(dados)
            output = io.BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            st.success("Concluído!")
            st.download_button("📥 Baixar Planilha", output, f"Resultados_{polo_escolhido}.xlsx", type="primary")

# --- RODAPÉ ---
st.markdown("---")
fuso = pytz.timezone('America/Sao_Paulo')
st.caption(f"🚀 Super Perseu v3.0 | Gerado em: {datetime.now(fuso).strftime('%d/%m/%Y %H:%M')}")
