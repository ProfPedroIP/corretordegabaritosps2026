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

# Configuração da página Web
st.set_page_config(page_title="SCA - Instituto Ponte", page_icon="📝", layout="centered")

# --- LOGO ---
URL_LOGO = "https://www.institutoponte.org.br/wp-content/uploads/2025/02/Logo-Instituto-Ponto.png"
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    st.image(URL_LOGO, width=250)

def isolar_blocos_com_protecao(imagem_cv):
    altura_total, largura_total = imagem_cv.shape[:2]
    y_limite_superior = int(altura_total * 0.30)
    area_min, area_max = 900, 1600 
    
    cinza = cv2.cvtColor(imagem_cv, cv2.COLOR_BGR2GRAY)
    desfoque = cv2.GaussianBlur(cinza, (5, 5), 0)
    _, binario = cv2.threshold(desfoque, 180, 255, cv2.THRESH_BINARY_INV) 
    
    contornos, _ = cv2.findContours(binario, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    marcadores = []
    for c in contornos:
        perimetro = cv2.arcLength(c, True)
        aprox = cv2.approxPolyDP(c, 0.05 * perimetro, True)
        area = cv2.contourArea(c)
        if len(aprox) == 4 and area_min <= area <= area_max:
            x, y, w, h = cv2.boundingRect(aprox)
            if 0.5 <= (w / float(h)) <= 1.5:
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
        return cv2.warpPerspective(imagem_cv, matriz, (629, 1094))

    return processar(m_esq), processar(m_dir)

def ler_bolinhas(img_bloco, q_ini):
    """v1.8: Motor de Limiarização Adaptativa - O terror da caneta azul clara"""
    # 1. Pegamos o canal mínimo para dar o primeiro destaque no azul
    b, g, r = cv2.split(img_bloco)
    img_min = cv2.min(cv2.min(b, g), r)
    
    # 2. Em vez de Threshold fixo ou CLAHE, usamos o Adaptativo. 
    # Ele detecta o que é 'tinta' comparando o pixel com o fundo ao redor dele.
    binario = cv2.adaptiveThreshold(img_min, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                     cv2.THRESH_BINARY_INV, 51, 15)
    
    respostas = {}
    alts = ['A', 'B', 'C', 'D', 'E']
    xi, yi, px, py, raio = 89, 78, 110, 104, 31
    
    # 3. Limite de 25% (0.25): Equilíbrio ideal para 300 DPI
    limite = 0.18

    for i in range(10): 
        marcadas = []
        for j in range(5): 
            cx, cy = xi + (j * px), yi + (i * py)
            celula = binario[cy-raio : cy+raio, cx-raio : cx+raio]
            if celula.size > 0 and (cv2.countNonZero(celula) / celula.size) > limite:
                marcadas.append(alts[j])
        
        if len(marcadas) == 0: respostas[q_ini+i] = "EM BRANCO"
        elif len(marcadas) > 1: respostas[q_ini+i] = "ANULADA"
        else: respostas[q_ini+i] = marcadas[0]
    return respostas

# --- INTERFACE ---
st.title("Correção Automática de Gabaritos")
st.markdown("Sistema de correção oficial do Processo Seletivo 2026 do **Instituto Ponte**")

with st.expander("📖 Instruções de Uso", expanded=True):
    st.write("1. Use o **Adobe Scan** para gerar os PDFs.")
    st.write("2. O programa **não lê nomes**. Os resultados seguem a ordem física das páginas.")
    st.write("3. Enumere fisicamente os gabaritos para referência na planilha.")

st.subheader("1. Identificação e Gabarito")
c1, c2 = st.columns(2)
serie_escolhida = c1.selectbox("Selecione a Série:", ["7º Ano", "8º Ano", "9º Ano", "1ª Série", "2ª Série"])
polo_escolhido = c2.text_input("Polo:", placeholder="Ex: Bela Cruz")

st.divider()
gabarito_inputs = {}

st.markdown("#### 📚 Português (Questões 01 a 10)")
cols_pt = st.columns(10)
for i in range(1, 11):
    gabarito_inputs[i] = cols_pt[i-1].text_input(f"Q{i}", "A", key=f"q{i}", max_chars=1).upper()

st.markdown("#### 📐 Matemática (Questões 11 a 20)")
cols_mt = st.columns(10)
for i in range(11, 21):
    gabarito_inputs[i] = cols_mt[i-11].text_input(f"Q{i}", "A", key=f"q{i}", max_chars=1).upper()

st.divider()
st.subheader("2. Envio de Arquivos")
arquivos_pdf = st.file_uploader("Arraste os PDFs aqui", type=["pdf"], accept_multiple_files=True)

if st.button("🚀 Executar Correção dos Gabaritos", type="primary"):
    if not arquivos_pdf:
        st.warning("Envie ao menos um arquivo PDF.")
    elif not polo_escolhido:
        st.error("Preencha o campo 'Polo'.")
    else:
        total_geral_paginas = 0
        arquivos_info = []
        with st.spinner("Contabilizando gabaritos..."):
            for file in arquivos_pdf:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(file.read())
                    tmp_path = tmp.name
                    info = pdfinfo_from_path(tmp_path)
                    total_geral_paginas += info["Pages"]
                    arquivos_info.append((tmp_path, file.name, info["Pages"]))

        dados_consolidados = []
        num_global = 1
        progress_bar = st.progress(0)
        status_text = st.empty()

        for tmp_path, nome_file, total_pags in arquivos_info:
            for p in range(1, total_pags + 1):
                progress_bar.progress((num_global - 1) / total_geral_paginas)
                status_text.text(f"Corrigindo Gabarito {num_global} de {total_geral_paginas}...")
                
                pagina_imagem = convert_from_path(tmp_path, dpi=300, first_page=p, last_page=p)[0]
                img = cv2.cvtColor(np.array(pagina_imagem), cv2.COLOR_RGB2BGR)
                del pagina_imagem 
                
                bloco_e, bloco_d = isolar_blocos_com_protecao(img)
                resp = {}
                if bloco_e is not None and bloco_d is not None:
                    resp.update(ler_bolinhas(bloco_e, 1))
                    resp.update(ler_bolinhas(bloco_d, 11))
                    ac_pt = sum(1 for q in range(1, 11) if resp.get(q) == gabarito_inputs[q])
                    ac_mt = sum(1 for q in range(11, 21) if resp.get(q) == gabarito_inputs[q])
                else:
                    ac_pt, ac_mt = 0, 0
                    for q in range(1, 21): resp[q] = "ERRO_LEITURA"

                linha = {"Questão/Gabarito": f"Nº {num_global:04d}"}
                for q in range(1, 21): linha[f"Q{q}"] = resp.get(q)
                linha["Português"] = ac_pt
                linha["Matemática"] = ac_mt
                dados_consolidados.append(linha)
                num_global += 1
                gc.collect()

        progress_bar.progress(1.0)
        if dados_consolidados:
            df = pd.DataFrame(dados_consolidados)
            output = io.BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            wb = load_workbook(output)
            ws = wb.active
            ws.insert_rows(2)
            ws.cell(row=2, column=1).value = "Gabarito Correto"
            ws.cell(row=2, column=1).font = Font(bold=True, color="0000FF")
            for q in range(1, 21):
                c = ws.cell(row=2, column=q+1)
                c.value = gabarito_inputs[q]
                c.font = Font(bold=True)
                c.alignment = Alignment(horizontal="center")

            C_ACERTO = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
            C_ERRO = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
            C_ANULADA = PatternFill(start_color='FFEB9C', end_color='FFEB9C', fill_type='solid')

            for row in range(3, ws.max_row + 1):
                for col in range(2, 22):
                    cell = ws.cell(row=row, column=col)
                    q_idx = col - 1
                    if cell.value == gabarito_inputs[q_idx]: cell.fill = C_ACERTO
                    elif cell.value == "ANULADA": cell.fill = C_ANULADA
                    elif cell.value not in ["EM BRANCO", "ERRO_LEITURA"]: cell.fill = C_ERRO

            final_out = io.BytesIO()
            wb.save(final_out)
            final_out.seek(0)
            status_text.empty()
            st.success(f"✅ Sucesso! {len(dados_consolidados)} gabaritos corrigidos.")
            st.download_button(
                label="📥 Baixar Planilha",
                data=final_out,
                file_name=f"Resultados - {serie_escolhida} - {polo_escolhido}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

# --- RODAPÉ ---
st.markdown("---")
fuso_br = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(fuso_br)
st.caption(f"🚀 **Super Perseu v2.0** | Instituto Ponte | Gerado em: {agora.strftime('%d/%m/%Y às %H:%M:%S')}")
