#Bloco 0 - Verificação e instalação automática de dependências
import subprocess
import sys
import importlib

def verificar_e_instalar(pacotes):
    pacotes_a_instalar = []
    for pacote in pacotes:
        nome_import = pacote.replace("-", "_")
        try:
            importlib.import_module(nome_import)
            print(f"✅ {pacote} já está instalado")
        except ImportError:
            pacotes_a_instalar.append(pacote)
            print(f"⚠️ {pacote} não encontrado. Será instalado...")
    if pacotes_a_instalar:
        print(f"\n📦 Instalando: {', '.join(pacotes_a_instalar)}")
        for pacote in pacotes_a_instalar:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pacote])
        return True
    return False

pacotes_necessarios = ["streamlit", "pandas", "numpy", "plotly", "folium", "streamlit-folium", "requests", "geopy"]
print("🔍 Verificando dependências...")
if verificar_e_instalar(pacotes_necessarios):
    import os
    os.execv(sys.executable, [sys.executable] + sys.argv)

import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from datetime import datetime
import requests
import json

st.set_page_config(page_title="Sistema de Qualidade da Água", page_icon="💧", layout="wide")

# ============================================================
# 🔑 INSIRA SUAS CHAVES AQUI (ÚNICO LUGAR QUE PRECISA ALTERAR)
# ============================================================
CHAVE_API_GOOGLE = ""  # COLE SUA CHAVE DO GOOGLE MAPS AQUI
CHAVE_API_MAPBIOMAS = ""  # COLE SUA CHAVE DO MAPBIOMAS AQUI (opcional)
# ============================================================

# Inicialização da sessão
if 'cadastro_completo' not in st.session_state:
    st.session_state.cadastro_completo = False
if 'dados_app' not in st.session_state:
    st.session_state.dados_app = {"cadastro": {}, "analises": [], "levantamento": {}}
if 'analises_temp' not in st.session_state:
    st.session_state.analises_temp = [{}]

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def estimar_relevo_por_coordenadas(lat, lon):
    """Estima o relevo usando Google Elevation API"""
    if not CHAVE_API_GOOGLE:
        return "Não disponível (insira chave do Google Maps)"
    try:
        url = f"https://maps.googleapis.com/maps/api/elevation/json?locations={lat},{lon}&key={CHAVE_API_GOOGLE}"
        resp = requests.get(url).json()
        if resp['status'] == 'OK':
            elevacao = resp['results'][0]['elevation']
            if elevacao < 100:
                return "Plano/Baixada"
            elif elevacao < 300:
                return "Suave ondulado"
            elif elevacao < 700:
                return "Ondulado"
            else:
                return "Montanhoso"
    except:
        return "Não disponível"

def estimar_cobertura_solo(lat, lon):
    """Estima uso do solo via MapBiomas (se tiver chave)"""
    if not CHAVE_API_MAPBIOMAS:
        return "Não disponível (insira chave do MapBiomas)"
    return "Informação não disponível"

# ============================================================
# CLASSIFICAÇÃO ADAPTATIVA
# ============================================================

def classificar_ponto_adaptativo(analise):
    """Classifica baseado nos parâmetros disponíveis. Se insuficiente, retorna 'Dados insuficientes'"""
    parâmetros_preenchidos = [k for k, v in analise.items() if v not in [None, "", 0] and k not in ['nome', 'lat', 'lon', 'data']]
    
    if len(parâmetros_preenchidos) < 3:
        return "Dados insuficientes", "⚪", ["Adicione mais parâmetros para classificação"], parâmetros_preenchidos
    
    classe = 1
    
    # OD
    if 'od' in analise and analise['od']:
        if analise['od'] < 5: classe = max(classe, 3)
        elif analise['od'] < 6: classe = max(classe, 2)
    
    # pH
    if 'ph' in analise and analise['ph']:
        if analise['ph'] < 6 or analise['ph'] > 9: classe = max(classe, 4)
        elif analise['ph'] < 6.5 or analise['ph'] > 8.5: classe = max(classe, 3)
    
    # DBO
    if 'dbo' in analise and analise['dbo']:
        if analise['dbo'] > 10: classe = max(classe, 4)
        elif analise['dbo'] > 5: classe = max(classe, 3)
        elif analise['dbo'] > 3: classe = max(classe, 2)
    
    # Coliformes
    if 'coliformes' in analise and analise['coliformes']:
        if analise['coliformes'] > 4000: classe = max(classe, 4)
        elif analise['coliformes'] > 1000: classe = max(classe, 3)
        elif analise['coliformes'] > 200: classe = max(classe, 2)
    
    # Metais
    metais = ['chumbo', 'cadmio', 'mercurio', 'arsenio', 'cromo', 'cobre', 'zinco']
    for metal in metais:
        if metal in analise and analise[metal] and analise[metal] > 0.01:
            classe = max(classe, 3)
    
    if classe == 1:
        return "Classe 1", "🟢", ["Excelente qualidade"], parâmetros_preenchidos
    elif classe == 2:
        return "Classe 2", "🟡", ["Qualidade boa, requer tratamento convencional"], parâmetros_preenchidos
    elif classe == 3:
        return "Classe 3", "🟠", ["Qualidade regular, requer tratamento avançado"], parâmetros_preenchidos
    else:
        return "Classe 4", "🔴", ["Qualidade ruim, restrição de usos"], parâmetros_preenchidos


# ============================================================
# ABA 1 - CADASTRO
# ============================================================

def aba_cadastro():
    st.header("📋 1. Cadastro")
    
    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Nome completo *")
        email = st.text_input("E-mail *")
        telefone = st.text_input("Telefone")
    with col2:
        fazenda = st.text_input("Nome da Fazenda *")
        fazenda_lat = st.number_input("Latitude", format="%.6f", value=-15.0)
        fazenda_lon = st.number_input("Longitude", format="%.6f", value=-45.0)
        corpo_hidrico = st.text_input("Nome do Rio/Lago/Represa *")
    
    st.divider()
    if st.button("💾 Salvar Cadastro", type="primary"):
        st.session_state.dados_app["cadastro"] = {
            "nome": nome, "email": email, "telefone": telefone,
            "fazenda": fazenda, "lat": fazenda_lat, "lon": fazenda_lon,
            "corpo_hidrico": corpo_hidrico
        }
        if nome and email and fazenda and corpo_hidrico:
            st.session_state.cadastro_completo = True
            st.success("✅ Cadastro completo! Abas liberadas.")
            st.balloons()
        else:
            st.warning("⚠️ Preencha todos os campos com *")


# ============================================================
# ABA 2 - ANÁLISES (TODOS OS PARÂMETROS)
# ============================================================

def aba_analises():
    st.header("🧪 2. Análises de Qualidade da Água")
    st.caption("Preencha os parâmetros disponíveis. Quanto mais dados, melhor a classificação.")
    
    num_pontos = len(st.session_state.analises_temp)
    if num_pontos == 0:
        num_pontos = 1
        st.session_state.analises_temp = [{}]
    
    for i in range(num_pontos):
        with st.expander(f"📌 Ponto {i+1}", expanded=(i == num_pontos-1)):
            
            # Identificação do ponto
            col_id1, col_id2, col_id3 = st.columns(3)
            with col_id1:
                nome = st.text_input(f"ID do Ponto", key=f"nome_{i}", value=st.session_state.analises_temp[i].get("nome", f"P{i+1}"))
            with col_id2:
                lat = st.number_input(f"Latitude", key=f"lat_{i}", format="%.6f", value=float(st.session_state.analises_temp[i].get("lat", -15.0)))
            with col_id3:
                lon = st.number_input(f"Longitude", key=f"lon_{i}", format="%.6f", value=float(st.session_state.analises_temp[i].get("lon", -45.0)))
            
            st.markdown("---")
            
            # PARÂMETROS FÍSICO-QUÍMICOS BÁSICOS
            st.markdown("### 🌊 Parâmetros Físico-Químicos Básicos")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                temperatura = st.number_input(f"Temperatura (°C)", key=f"temp_{i}", value=float(st.session_state.analises_temp[i].get("temperatura", 25.0)), step=0.1, format="%.1f")
            with col2:
                ph = st.number_input(f"pH", key=f"ph_{i}", value=float(st.session_state.analises_temp[i].get("ph", 7.0)), step=0.1, format="%.1f")
            with col3:
                condutividade = st.number_input(f"Condutividade (µS/cm)", key=f"cond_{i}", value=float(st.session_state.analises_temp[i].get("condutividade", 100.0)), step=10.0, format="%.1f")
            with col4:
                turbidez = st.number_input(f"Turbidez (NTU)", key=f"turb_{i}", value=float(st.session_state.analises_temp[i].get("turbidez", 5.0)), step=0.1, format="%.1f")
            with col5:
                salinidade = st.number_input(f"Salinidade (PSU)", key=f"salin_{i}", value=float(st.session_state.analises_temp[i].get("salinidade", 0.0)), step=0.1, format="%.1f")
            
            col6, col7, col8, col9, col10 = st.columns(5)
            with col6:
                cor_aparente = st.number_input(f"Cor Aparente (mg/L Pt-Co)", key=f"cor_ap_{i}", value=int(st.session_state.analises_temp[i].get("cor_aparente", 10)), step=5)
            with col7:
                cor_verdadeira = st.number_input(f"Cor Verdadeira (mg/L Pt-Co)", key=f"cor_vd_{i}", value=int(st.session_state.analises_temp[i].get("cor_verdadeira", 5)), step=5)
            with col8:
                std = st.number_input(f"STD (mg/L)", key=f"std_{i}", value=int(st.session_state.analises_temp[i].get("std", 200)), step=10)
            with col9:
                sst = st.number_input(f"SST (mg/L)", key=f"sst_{i}", value=int(st.session_state.analises_temp[i].get("sst", 50)), step=10)
            with col10:
                orp = st.number_input(f"ORP (mV)", key=f"orp_{i}", value=int(st.session_state.analises_temp[i].get("orp", 0)), step=10)
            
            st.markdown("---")
            
            # OXIGÊNIO E DEMANDA
            st.markdown("### 💨 Oxigênio e Demanda")
            col11, col12, col13 = st.columns(3)
            with col11:
                od = st.number_input(f"OD (mg/L)", key=f"od_{i}", value=float(st.session_state.analises_temp[i].get("od", 7.0)), step=0.1, format="%.1f")
            with col12:
                dbo = st.number_input(f"DBO₅,₂₀ (mg/L)", key=f"dbo_{i}", value=float(st.session_state.analises_temp[i].get("dbo", 2.0)), step=0.1, format="%.1f")
            with col13:
                dqo = st.number_input(f"DQO (mg/L)", key=f"dqo_{i}", value=float(st.session_state.analises_temp[i].get("dqo", 10.0)), step=1.0, format="%.1f")
            
            st.markdown("---")
            
            # NUTRIENTES
            st.markdown("### 🧫 Nutrientes")
            col14, col15, col16, col17, col18, col19 = st.columns(6)
            with col14:
                n_amoniacal = st.number_input(f"N-Amoniacal (mg/L)", key=f"nam_{i}", value=float(st.session_state.analises_temp[i].get("n_amoniacal", 0.5)), step=0.1, format="%.2f")
            with col15:
                nitrato = st.number_input(f"Nitrato (mg/L)", key=f"nit_{i}", value=float(st.session_state.analises_temp[i].get("nitrato", 1.0)), step=0.1, format="%.2f")
            with col16:
                nitrito = st.number_input(f"Nitrito (mg/L)", key=f"nitri_{i}", value=float(st.session_state.analises_temp[i].get("nitrito", 0.05)), step=0.01, format="%.3f")
            with col17:
                n_total = st.number_input(f"N-Total (mg/L)", key=f"nt_{i}", value=float(st.session_state.analises_temp[i].get("n_total", 1.0)), step=0.1, format="%.2f")
            with col18:
                p_total = st.number_input(f"P-Total (mg/L)", key=f"pt_{i}", value=float(st.session_state.analises_temp[i].get("p_total", 0.03)), step=0.01, format="%.4f")
            with col19:
                fosfato = st.number_input(f"Fosfato (mg/L)", key=f"fos_{i}", value=float(st.session_state.analises_temp[i].get("fosfato", 0.1)), step=0.01, format="%.3f")
            
            st.markdown("---")
            
            # INDICADORES BIOLÓGICOS
            st.markdown("### 🦠 Indicadores Biológicos")
            col20, col21, col22, col23, col24 = st.columns(5)
            with col20:
                coliformes = st.number_input(f"Coliformes (NMP/100mL)", key=f"col_{i}", value=int(st.session_state.analises_temp[i].get("coliformes", 50)), step=10)
            with col21:
                e_coli = st.number_input(f"E. coli (NMP/100mL)", key=f"ec_{i}", value=int(st.session_state.analises_temp[i].get("e_coli", 50)), step=10)
            with col22:
                enterococos = st.number_input(f"Enterococos (NMP/100mL)", key=f"ent_{i}", value=int(st.session_state.analises_temp[i].get("enterococos", 0)), step=10)
            with col23:
                clorofila = st.number_input(f"Clorofila-a (µg/L)", key=f"cl_{i}", value=float(st.session_state.analises_temp[i].get("clorofila", 5.0)), step=1.0, format="%.1f")
            with col24:
                cianobacterias = st.number_input(f"Cianobactérias (cel/mL)", key=f"cia_{i}", value=float(st.session_state.analises_temp[i].get("cianobacterias", 0)), step=100.0, format="%.0f")
            
            st.markdown("---")
            
            # METAIS PESADOS
            st.markdown("### 🔬 Metais Pesados e Tóxicos")
            col25, col26, col27, col28, col29, col30 = st.columns(6)
            with col25:
                ferro = st.number_input(f"Ferro (mg/L)", key=f"fe_{i}", value=float(st.session_state.analises_temp[i].get("ferro", 0.3)), step=0.1, format="%.3f")
            with col26:
                manganes = st.number_input(f"Manganês (mg/L)", key=f"mn_{i}", value=float(st.session_state.analises_temp[i].get("manganes", 0.1)), step=0.05, format="%.3f")
            with col27:
                aluminio = st.number_input(f"Alumínio (mg/L)", key=f"al_{i}", value=float(st.session_state.analises_temp[i].get("aluminio", 0.1)), step=0.05, format="%.3f")
            with col28:
                zinco = st.number_input(f"Zinco (mg/L)", key=f"zn_{i}", value=float(st.session_state.analises_temp[i].get("zinco", 0.05)), step=0.01, format="%.3f")
            with col29:
                cobre = st.number_input(f"Cobre (mg/L)", key=f"cu_{i}", value=float(st.session_state.analises_temp[i].get("cobre", 0.01)), step=0.01, format="%.3f")
            with col30:
                chumbo = st.number_input(f"Chumbo (mg/L)", key=f"pb_{i}", value=float(st.session_state.analises_temp[i].get("chumbo", 0.001)), step=0.001, format="%.4f")
            
            col31, col32, col33, col34, col35, col36 = st.columns(6)
            with col31:
                cadmio = st.number_input(f"Cádmio (mg/L)", key=f"cd_{i}", value=float(st.session_state.analises_temp[i].get("cadmio", 0.0005)), step=0.0005, format="%.4f")
            with col32:
                mercurio = st.number_input(f"Mercúrio (mg/L)", key=f"hg_{i}", value=float(st.session_state.analises_temp[i].get("mercurio", 0.0001)), step=0.0001, format="%.4f")
            with col33:
                arsenio = st.number_input(f"Arsênio (mg/L)", key=f"as_{i}", value=float(st.session_state.analises_temp[i].get("arsenio", 0.001)), step=0.001, format="%.4f")
            with col34:
                cromo = st.number_input(f"Cromo (mg/L)", key=f"cr_{i}", value=float(st.session_state.analises_temp[i].get("cromo", 0.01)), step=0.01, format="%.3f")
            with col35:
                niquel = st.number_input(f"Níquel (mg/L)", key=f"ni_{i}", value=float(st.session_state.analises_temp[i].get("niquel", 0.005)), step=0.005, format="%.4f")
            with col36:
                selenio = st.number_input(f"Selênio (mg/L)", key=f"se_{i}", value=float(st.session_state.analises_temp[i].get("selenio", 0.001)), step=0.001, format="%.4f")
            
            col37, col38, col39 = st.columns(3)
            with col37:
                bario = st.number_input(f"Bário (mg/L)", key=f"ba_{i}", value=float(st.session_state.analises_temp[i].get("bario", 0.1)), step=0.05, format="%.3f")
            with col38:
                boro = st.number_input(f"Boro (mg/L)", key=f"bo_{i}", value=float(st.session_state.analises_temp[i].get("boro", 0.1)), step=0.05, format="%.3f")
            with col39:
                prata = st.number_input(f"Prata (mg/L)", key=f"ag_{i}", value=float(st.session_state.analises_temp[i].get("prata", 0.0005)), step=0.0005, format="%.4f")
            
            st.markdown("---")
            
            # ÂNIONS
            st.markdown("### 🧪 Ânions")
            col40, col41, col42, col43 = st.columns(4)
            with col40:
                sulfatos = st.number_input(f"Sulfatos (mg/L)", key=f"sulf_{i}", value=float(st.session_state.analises_temp[i].get("sulfatos", 50.0)), step=10.0, format="%.1f")
            with col41:
                fluoreto = st.number_input(f"Fluoreto (mg/L)", key=f"flu_{i}", value=float(st.session_state.analises_temp[i].get("fluoreto", 0.5)), step=0.1, format="%.2f")
            with col42:
                cianeto = st.number_input(f"Cianeto (mg/L)", key=f"cian_{i}", value=float(st.session_state.analises_temp[i].get("cianeto", 0.0)), step=0.01, format="%.3f")
            with col43:
                cloreto = st.number_input(f"Cloretos (mg/L)", key=f"cl_{i}", value=float(st.session_state.analises_temp[i].get("cloretos", 50.0)), step=10.0, format="%.1f")
            
            st.markdown("---")
            
            # ALCALINIDADE E DUREZA
            st.markdown("### 💧 Alcalinidade e Dureza")
            col44, col45 = st.columns(2)
            with col44:
                alcalinidade = st.number_input(f"Alcalinidade (mg/L CaCO₃)", key=f"alc_{i}", value=float(st.session_state.analises_temp[i].get("alcalinidade", 50.0)), step=10.0, format="%.1f")
            with col45:
                dureza = st.number_input(f"Dureza Total (mg/L CaCO₃)", key=f"dur_{i}", value=float(st.session_state.analises_temp[i].get("dureza", 100.0)), step=10.0, format="%.1f")
            
            st.markdown("---")
            
            # COMPOSTOS ORGÂNICOS
            st.markdown("### 🧴 Compostos Orgânicos")
            col46, col47, col48, col49 = st.columns(4)
            with col46:
                oleos = st.number_input(f"Óleos e Graxas (mg/L)", key=f"oleo_{i}", value=float(st.session_state.analises_temp[i].get("oleos", 0.0)), step=0.5, format="%.1f")
            with col47:
                fenoIs = st.number_input(f"Fenóis (mg/L)", key=f"fen_{i}", value=float(st.session_state.analises_temp[i].get("fenois", 0.0)), step=0.001, format="%.4f")
            with col48:
                surfactantes = st.number_input(f"Surfactantes (mg/L)", key=f"surf_{i}", value=float(st.session_state.analises_temp[i].get("surfactantes", 0.0)), step=0.1, format="%.2f")
            with col49:
                cot = st.number_input(f"COT (mg/L)", key=f"cot_{i}", value=float(st.session_state.analises_temp[i].get("cot", 5.0)), step=1.0, format="%.1f")
            
            col50, col51, col52, col53 = st.columns(4)
            with col50:
                benzeno = st.number_input(f"Benzeno (µg/L)", key=f"benz_{i}", value=float(st.session_state.analises_temp[i].get("benzeno", 0.0)), step=1.0, format="%.1f")
            with col51:
                tolueno = st.number_input(f"Tolueno (µg/L)", key=f"tol_{i}", value=float(st.session_state.analises_temp[i].get("tolueno", 0.0)), step=1.0, format="%.1f")
            with col52:
                xileno = st.number_input(f"Xileno (µg/L)", key=f"xil_{i}", value=float(st.session_state.analises_temp[i].get("xileno", 0.0)), step=1.0, format="%.1f")
            with col53:
                thm = st.number_input(f"Trihalometanos (µg/L)", key=f"thm_{i}", value=float(st.session_state.analises_temp[i].get("thm", 0.0)), step=1.0, format="%.1f")
            
            col54, col55 = st.columns(2)
            with col54:
                pesticidas = st.text_input(f"Pesticidas (especificar)", key=f"pest_{i}", value=st.session_state.analises_temp[i].get("pesticidas", "Não detectado"))
            with col55:
                herbicidas = st.text_input(f"Herbicidas (especificar)", key=f"herb_{i}", value=st.session_state.analises_temp[i].get("herbicidas", "Não detectado"))
            
            st.markdown("---")
            
            # TOXICIDADE E ÍNDICES
            st.markdown("### 📊 Toxicidade e Índices")
            col56, col57, col58, col59 = st.columns(4)
            with col56:
                tox_aguda = st.selectbox(f"Toxicidade Aguda", ["Não analisado", "Não detectada", "Detectada"], key=f"toxag_{i}")
            with col57:
                tox_cronica = st.selectbox(f"Toxicidade Crônica", ["Não analisado", "Não detectada", "Detectada"], key=f"toxc_{i}")
            with col58:
                iqa = st.number_input(f"IQA (0-100)", key=f"iqa_{i}", value=float(st.session_state.analises_temp[i].get("iqa", 70.0)), step=1.0, min_value=0.0, max_value=100.0)
            with col59:
                iet = st.selectbox(f"IET", ["Não calculado", "Ultraoligotrófico", "Oligotrófico", "Mesotrófico", "Eutrófico", "Hipereutrófico"], key=f"iet_{i}")
            
            # Salvar todos os dados do ponto
            st.session_state.analises_temp[i] = {
                "nome": nome, "lat": lat, "lon": lon,
                "temperatura": temperatura, "ph": ph, "condutividade": condutividade,
                "turbidez": turbidez, "salinidade": salinidade,
                "cor_aparente": cor_aparente, "cor_verdadeira": cor_verdadeira,
                "std": std, "sst": sst, "orp": orp,
                "od": od, "dbo": dbo, "dqo": dqo,
                "n_amoniacal": n_amoniacal, "nitrato": nitrato, "nitrito": nitrito,
                "n_total": n_total, "p_total": p_total, "fosfato": fosfato,
                "coliformes": coliformes, "e_coli": e_coli, "enterococos": enterococos,
                "clorofila": clorofila, "cianobacterias": cianobacterias,
                "ferro": ferro, "manganes": manganes, "aluminio": aluminio,
                "zinco": zinco, "cobre": cobre, "chumbo": chumbo,
                "cadmio": cadmio, "mercurio": mercurio, "arsenio": arsenio,
                "cromo": cromo, "niquel": niquel, "selenio": selenio,
                "bario": bario, "boro": boro, "prata": prata,
                "sulfatos": sulfatos, "fluoreto": fluoreto, "cianeto": cianeto,
                "cloretos": cloreto, "alcalinidade": alcalinidade, "dureza": dureza,
                "oleos": oleos, "fenois": fenoIs, "surfactantes": surfactantes,
                "cot": cot, "benzeno": benzeno, "tolueno": tolueno,
                "xileno": xileno, "thm": thm,
                "pesticidas": pesticidas, "herbicidas": herbicidas,
                "toxicidade_aguda": tox_aguda, "toxicidade_cronica": tox_cronica,
                "iqa": iqa, "iet": iet, "data": str(datetime.now())
            }
    
    # Botões de adicionar/remover pontos
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Adicionar outro ponto de coleta"):
            st.session_state.analises_temp.append({})
            st.rerun()
    with col_btn2:
        if len(st.session_state.analises_temp) > 1 and st.button("➖ Remover último ponto"):
            st.session_state.analises_temp.pop()
            st.rerun()
    
    st.divider()
    if st.button("💾 Salvar todas as análises", type="primary"):
        st.session_state.dados_app["analises"] = st.session_state.analises_temp
        st.success(f"✅ {len(st.session_state.analises_temp)} ponto(s) salvo(s)!")
        st.info("📌 A classificação será atualizada na aba 'Relatório'.")


# ============================================================
# ABA 3 - LEVANTAMENTO AMBIENTAL
# ============================================================

def aba_levantamento():
    st.header("🌍 3. Levantamento Ambiental")
    
    cad = st.session_state.dados_app.get("cadastro", {})
    lat = cad.get("lat", -15.0)
    lon = cad.get("lon", -45.0)
    
    if lat and lon and lat != -15.0:
        st.info(f"📍 Estimando características para coordenadas: {lat}, {lon}")
        relevo_estimado = estimar_relevo_por_coordenadas(lat, lon)
        st.write(f"**Relevo estimado:** {relevo_estimado}")
    
    col1, col2 = st.columns(2)
    with col1:
        cobertura = st.selectbox("Cobertura do solo", ["Florestada", "Pastagem", "Agricultura", "Urbana", "Mista", "Não sei"])
        tipo_solo = st.selectbox("Tipo de solo", ["Argiloso", "Arenoso", "Siltoso", "Latossolo", "Não sei"])
        relevo = st.selectbox("Relevo", ["Plano", "Suave ondulado", "Ondulado", "Montanhoso", "Não sei"])
    with col2:
        fontes = st.multiselect("Fontes de poluição", ["Esgoto", "Agropecuária", "Indústria", "Mineração", "Resíduos sólidos", "Não identificado"])
        observacoes = st.text_area("Observações", height=100)
    
    if st.button("💾 Salvar Levantamento", type="primary"):
        st.session_state.dados_app["levantamento"] = {
            "cobertura": cobertura, "tipo_solo": tipo_solo, "relevo": relevo,
            "fontes": fontes, "observacoes": observacoes
        }
        st.success("✅ Levantamento salvo!")


# ============================================================
# ABA 4 - RELATÓRIO
# ============================================================

def aba_relatorio():
    st.header("📊 4. Relatório de Classificação")
    
    analises = st.session_state.dados_app.get("analises", [])
    cad = st.session_state.dados_app.get("cadastro", {})
    lev = st.session_state.dados_app.get("levantamento", {})
    
    if not analises:
        st.warning("Nenhuma análise cadastrada.")
        return
    
    st.subheader(f"📍 {cad.get('corpo_hidrico', 'Corpo Hídrico')} - {cad.get('fazenda', 'Fazenda')}")
    
    for i, ponto in enumerate(analises):
        classe, cor, recomendacoes, params_preenchidos = classificar_ponto_adaptativo(ponto)
        
        with st.expander(f"{cor} Ponto {ponto.get('nome', i+1)} - {classe}", expanded=True):
            st.markdown(f"**Parâmetros preenchidos:** {len(params_preenchidos)}")
            
            if classe == "Dados insuficientes":
                st.warning("⚠️ Dados insuficientes para classificação precisa. Adicione mais parâmetros (mínimo 3).")
            else:
                st.success(f"**Classificação:** {classe} {cor}")
                st.info(f"**Recomendação:** {recomendacoes[0]}")
            
            # Mostrar valores preenchidos
            st.markdown("**Valores medidos:**")
            valores = {k: v for k, v in ponto.items() if v not in [None, "", 0] and k not in ['nome', 'lat', 'lon', 'data']}
            if valores:
                df_valores = pd.DataFrame(list(valores.items()), columns=["Parâmetro", "Valor"])
                st.dataframe(df_valores, use_container_width=True, hide_index=True)
    
    # Recomendações de Manejo
    st.subheader("🌱 Recomendações de Manejo")
    
    if lev:
        if lev.get("cobertura") == "Agricultura":
            st.write("🌾 **Agricultura**: Implementar faixas de amortecimento com vegetação nativa entre a lavoura e o corpo d'água.")
        if lev.get("cobertura") == "Pastagem":
            st.write("🐄 **Pastagem**: Evitar o acesso direto do gado à água, cercar nascentes e implantar sistemas silvipastoris.")
        if "Esgoto" in lev.get("fontes", []):
            st.write("🏠 **Esgoto**: Investir em saneamento básico e tratamento de efluentes antes do lançamento.")
        if "Agropecuária" in lev.get("fontes", []):
            st.write("🧪 **Agroquímicos**: Reduzir uso de fertilizantes e defensivos, adotar manejo integrado de pragas.")
        if "Indústria" in lev.get("fontes", []):
            st.write("🏭 **Indústria**: Exigir tratamento de efluentes industriais antes do lançamento nos corpos d'água.")
        if "Mineração" in lev.get("fontes", []):
            st.write("⛏️ **Mineração**: Implementar sistemas de contenção de rejeitos e monitoramento constante da qualidade da água.")
    else:
        st.info("📌 Complete o Levantamento Ambiental para receber recomendações personalizadas.")


# ============================================================
# ABA 5 - MAPA
# ============================================================

def aba_mapa():
    st.header("🗺️ 5. Mapa de Localização")
    
    cad = st.session_state.dados_app.get("cadastro", {})
    analises = st.session_state.dados_app.get("analises", [])
    
    lat = cad.get("lat", -15.0)
    lon = cad.get("lon", -45.0)
    
    if lat == -15.0 and lon == -45.0:
        st.warning("⚠️ Configure as coordenadas da fazenda na aba 'Cadastro' para visualizar o mapa.")
        return
    
    m = folium.Map(location=[lat, lon], zoom_start=13, control_scale=True)
    
    # Marcador da fazenda
    folium.Marker(
        [lat, lon], 
        popup=f"🏠 {cad.get('fazenda', 'Fazenda')}",
        icon=folium.Icon(color="green", icon="home", prefix='fa')
    ).add_to(m)
    
    # Pontos de coleta
    for ponto in analises:
        if ponto.get("lat") and ponto.get("lon") and ponto.get("lat") != -15.0:
            folium.Marker(
                [ponto["lat"], ponto["lon"]], 
                popup=f"📌 {ponto.get('nome', 'Ponto')}<br>Data: {ponto.get('data', 'N/A')}",
                icon=folium.Icon(color="blue", icon="water", prefix='fa')
            ).add_to(m)
    
    # Adicionar Google Maps se tiver chave
    if CHAVE_API_GOOGLE and CHAVE_API_GOOGLE.strip():
        try:
            folium.TileLayer(
                f"https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}&key={CHAVE_API_GOOGLE}",
                attr="Google Maps",
                name="Google Maps",
                control=True
            ).add_to(m)
            folium.TileLayer(
                f"https://mt1.google.com/vt/lyrs=s&x={{x}}&y={{y}}&z={{z}}&key={CHAVE_API_GOOGLE}",
                attr="Google Satélite",
                name="Google Satélite",
                control=True
            ).add_to(m)
        except Exception as e:
            pass
    
    folium.LayerControl().add_to(m)
    st_folium(m, width=900, height=500)
    
    # Estatísticas
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📍 Pontos de Coleta", len(analises))
    with col2:
        st.metric("🏠 Fazenda", cad.get("fazenda", "Não cadastrada"))


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def main():
    st.sidebar.title("💧 Sistema de Qualidade da Água")
    st.sidebar.markdown("---")
    
    # Informação da chave API
    if not CHAVE_API_GOOGLE:
        st.sidebar.warning("🔑 **Chave API não configurada!**")
        st.sidebar.caption("Para usar o mapa com Google Maps e estimar relevo, insira sua chave na variável `CHAVE_API_GOOGLE` no início do código.")
    
    if not st.session_state.cadastro_completo:
        st.sidebar.warning("⚠️ Complete o cadastro primeiro!")
        abas = ["📋 Cadastro"]
    else:
        abas = ["📋 Cadastro", "🧪 Análises", "🌍 Levantamento", "📊 Relatório", "🗺️ Mapa"]
    
    aba = st.sidebar.radio("📌 Navegação", abas)
    
    if aba == "📋 Cadastro":
        aba_cadastro()
    elif aba == "🧪 Análises":
        aba_analises()
    elif aba == "🌍 Levantamento":
        aba_levantamento()
    elif aba == "📊 Relatório":
        aba_relatorio()
    elif aba == "🗺️ Mapa":
        aba_mapa()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("📜 **Legislação aplicável:**")
    st.sidebar.caption("- CONAMA 357/2005")
    st.sidebar.caption("- Portaria 888/2021")
    st.sidebar.caption("- Lei 9.433/1997")


if __name__ == "__main__":
    main()
