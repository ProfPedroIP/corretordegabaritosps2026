import os

readme_content = """# SCA - Sistema de Correção Automática (Projeto Super Perseu)

![Status](https://img.shields.io/badge/Status-Finalizado-brightgreen)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Framework-FF4B4B)

O **SCA (Super Perseu)** é uma solução de Visão Computacional desenvolvida para automatizar a correção de gabaritos do Processo Seletivo do **Instituto Ponte**. O sistema processa arquivos PDF digitalizados, identifica as marcações dos candidatos e gera planilhas detalhadas com resultados por disciplina.

---

## 🚀 Funcionalidades

* **Processamento em Lote:** Suporta o upload de múltiplos arquivos PDF simultaneamente.
* **Visão Computacional de Precisão:** Utiliza transformações de perspectiva e filtros morfológicos para ler marcações mesmo em digitalizações com leves inclinações.
* **Separação por Disciplina:** Contabiliza automaticamente acertos de **Português (Q01-Q10)** e **Matemática (Q11-Q20)**.
* **Relatório Inteligente:** Gera um arquivo Excel (.xlsx) com:
    * Células coloridas (**Verde** para acerto, **Vermelho** para erro, **Amarelo** para anulada).
    * Linha de "Gabarito Esperado" para conferência pedagógica rápida.
    * Nome do arquivo dinâmico baseado na Série e no Polo.
* **Interface Web Amigável:** Desenvolvido com Streamlit para ser intuitivo para usuários não técnicos.

---

## 🛠️ Tecnologias Utilizadas

* [Python](https://www.python.org/) - Linguagem base.
* [OpenCV](https://opencv.org/) - Processamento de imagem e visão computacional.
* [Streamlit](https://streamlit.io/) - Interface web.
* [Pandas](https://pandas.pydata.org/) - Manipulação de dados.
* [Openpyxl](https://openpyxl.readthedocs.io/) - Formatação e estilo de planilhas Excel.
* [pdf2image](https://pypi.org/project/pdf2image/) - Conversão de documentos PDF para processamento visual.

---

## 📂 Estrutura do Repositório

```text
├── .streamlit/
│   └── config.toml      # Configuração da identidade visual (Cores do Instituto Ponte)
├── app.py               # Código principal da aplicação
├── requirements.txt     # Dependências do Python
├── packages.txt         # Dependências do sistema (Poppler para leitura de PDF)
└── README.md            # Documentação do projeto
