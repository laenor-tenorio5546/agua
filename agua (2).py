#Bloco 0 - Verificação e instalação automática de dependências
import subprocess
import sys
import importlib

def verificar_e_instalar(pacotes):
    """
    Verifica se os pacotes estão instalados e os instala automaticamente se necessário
    """
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
        print("\n✅ Todos os pacotes foram instalados com sucesso!")
        return True
    else:
        print("\n✅ Todos os pacotes já estão instalados!")
        return False

# Lista de pacotes necessários
pacotes_necessarios = [
    "streamlit",
    "pandas", 
    "numpy",
    "plotly",
    "folium",
    "streamlit-folium"
]

# Verificar e instalar dependências
print("🔍 Verificando dependências do sistema...")
precisa_reiniciar = verificar_e_instalar(pacotes_necessarios)

if precisa_reiniciar:
    print("\n🔄 As dependências foram instaladas. Reiniciando o script...")
    import os
    os.execv(sys.executable, [sys.executable] + sys.argv)

# Agora importar os pacotes (já devem estar disponíveis)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime
import json
import os

# Configuração da página
st.set_page_config(
    page_title="Sistema de Qualidade da Água",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# INICIALIZAÇÃO DOS DADOS NA SESSÃO (SEM PERSISTÊNCIA EM ARQUIVO)
# ============================================================
# Os dados são armazenados apenas na sessão. Ao atualizar a página, tudo é resetado.
if 'cadastro_completo' not in st.session_state:
    st.session_state.cadastro_completo = False

if 'dados_app' not in st.session_state:
    st.session_state.dados_app = {
        "cadastro": {},
        "analises": [],
        "analises_avancadas": [],
        "levantamento": {},
        "usuario": {}
    }

if 'analises_temp' not in st.session_state:
    st.session_state.analises_temp = []

if 'analises_avancadas_temp' not in st.session_state:
    st.session_state.analises_avancadas_temp = []


# ============================================================
# CHAVE API DO GOOGLE MAPS - INSIRA SUA CHAVE AQUI
# ============================================================
# Para obter uma chave gratuita:
# 1. Acesse: https://console.cloud.google.com/
# 2. Crie um projeto ou selecione um existente
# 3. Ative a API: "Maps JavaScript API"
# 4. Vá em "Credenciais" > "Criar credenciais" > "Chave de API"
# 5. Copie a chave e cole entre as aspas abaixo
# ============================================================
CHAVE_API_GOOGLE = "AIzaSyCbBzrvMUD8EZLO7v9EoYM9jiTmDDvDs9I"  # <--- COLE SUA CHAVE AQUI (ex: "AIzaSyD_1234567890...")
# ============================================================


#Bloco 1 - Função de classificação da qualidade da água (baseado na CONAMA 357/2005)
def classificar_ponto(analise):
    """
    Classifica o ponto de acordo com a Resolução CONAMA 357/2005
    Retorna: classe, usos, cor_indicativa
    """
    classe = 1
    motivos = []
    
    # OD - Oxigênio Dissolvido (mg/L)
    if 'od' in analise and analise['od'] is not None:
        od = analise['od']
        if od < 5.0:
            classe = max(classe, 3 if od < 4.0 else 2)
            motivos.append(f"OD baixo ({od} mg/L)")
        elif od < 6.0:
            classe = max(classe, 2)
            motivos.append(f"OD ({od} mg/L) abaixo da Classe 1")
    
    # pH
    if 'ph' in analise and analise['ph'] is not None:
        ph = analise['ph']
        if ph < 6.0 or ph > 9.0:
            classe = max(classe, 4)
            motivos.append(f"pH fora da faixa ({ph})")
        elif ph < 6.5 or ph > 8.5:
            classe = max(classe, 3)
            motivos.append(f"pH ({ph}) fora da faixa Classe 1/2")
    
    # DBO
    if 'dbo' in analise and analise['dbo'] is not None:
        dbo = analise['dbo']
        if dbo > 10.0:
            classe = max(classe, 4)
            motivos.append(f"DBO alta ({dbo} mg/L)")
        elif dbo > 5.0:
            classe = max(classe, 3)
            motivos.append(f"DBO ({dbo} mg/L) acima da Classe 2")
        elif dbo > 3.0:
            classe = max(classe, 2)
            motivos.append(f"DBO ({dbo} mg/L) acima da Classe 1")
    
    # Turbidez
    if 'turbidez' in analise and analise['turbidez'] is not None:
        turb = analise['turbidez']
        if turb > 100:
            classe = max(classe, 4)
        elif turb > 40:
            classe = max(classe, 3)
        elif turb > 10:
            classe = max(classe, 2)
    
    # E. coli
    if 'coliformes' in analise and analise['coliformes'] is not None:
        col = analise['coliformes']
        if col > 4000:
            classe = max(classe, 4)
            motivos.append(f"Coliformes altos ({col} NMP)")
        elif col > 1000:
            classe = max(classe, 3)
        elif col > 200:
            classe = max(classe, 2)
    
    # Fósforo Total
    if 'fosforo_total' in analise and analise['fosforo_total'] is not None:
        p = analise['fosforo_total']
        if p > 0.15:
            classe = max(classe, 3)
        elif p > 0.05:
            classe = max(classe, 2)
    
    # Nitrogênio Total
    if 'nitrogenio_total' in analise and analise['nitrogenio_total'] is not None:
        n = analise['nitrogenio_total']
        if n > 3.7:
            classe = max(classe, 3)
        elif n > 2.0:
            classe = max(classe, 2)
    
    # Definição da classe final
    if classe == 1:
        classe_texto = "Classe 1"
        cor = "🟢"
        usos = ["Abastecimento doméstico com desinfecção simples", "Proteção da vida aquática", "Irrigação"]
    elif classe == 2:
        classe_texto = "Classe 2"
        cor = "🟡"
        usos = ["Abastecimento com tratamento convencional", "Proteção da vida aquática", "Irrigação", "Recreação"]
    elif classe == 3:
        classe_texto = "Classe 3"
        cor = "🟠"
        usos = ["Abastecimento com tratamento convencional", "Irrigação", "Dessedentação de animais"]
    else:
        classe_texto = "Classe 4"
        cor = "🔴"
        usos = ["Navegação", "Harmonia paisagística", "Usos menos exigentes"]
    
    return classe_texto, cor, usos, motivos


def avaliar_trecho(pontos_classificados):
    if not pontos_classificados:
        return "Sem dados", "⚪", []
    
    classes = [c for c, _, _, _ in pontos_classificados]
    indices = {"Classe 1": 1, "Classe 2": 2, "Classe 3": 3, "Classe 4": 4}
    pior = max(classes, key=lambda x: indices.get(x, 4))
    
    if pior == "Classe 1":
        status = "Excelente"
        cor = "🟢"
        recomendacao = "Qualidade preservada. Manter práticas de conservação."
    elif pior == "Classe 2":
        status = "Boa"
        cor = "🟡"
        recomendacao = "Qualidade satisfatória. Monitorar parâmetros críticos."
    elif pior == "Classe 3":
        status = "Regular"
        cor = "🟠"
        recomendacao = "Qualidade comprometida. Necessário tratamento convencional para abastecimento."
    else:
        status = "Ruim"
        cor = "🔴"
        recomendacao = "Qualidade severamente degradada. Intervenção prioritária necessária."
    
    return status, cor, [recomendacao]


def gerar_recomendacoes_manejo(levantamento, classificacao_geral, analises):
    recomendacoes = []
    
    if levantamento:
        cobertura = levantamento.get('cobertura_solo', '').lower()
        
        if 'pastagem' in cobertura or 'agricultura' in cobertura:
            recomendacoes.append("🌾 **Agricultura/Pastagem**: Implementar práticas de conservação do solo, como plantio direto, terraços e faixas de amortecimento com vegetação nativa.")
        
        if 'urbano' in cobertura or 'esgoto' in str(levantamento):
            recomendacoes.append("🏙️ **Área Urbana/Esgoto**: Investir em saneamento básico, tratamento de esgoto e evitar lançamento in natura.")
        
        if 'mineracao' in str(levantamento):
            recomendacoes.append("⛏️ **Mineração**: Controle de drenagem ácida, tratamento de efluentes e recuperação de áreas degradadas.")
        
        if 'queimada' in str(levantamento):
            recomendacoes.append("🔥 **Queimadas**: Desenvolver plano de prevenção e combate a incêndios. Recuperar áreas queimadas.")
    
    if classificacao_geral == "Ruim" or classificacao_geral == "Regular":
        recomendacoes.append("⚠️ **Qualidade da água crítica**: Priorizar ações emergenciais como isolamento da área de captação e fiscalização de fontes poluidoras.")
    
    if analises:
        od_baixo = any(a.get('od', 10) < 5 for a in analises)
        dbo_alto = any(a.get('dbo', 0) > 5 for a in analises)
        
        if od_baixo or dbo_alto:
            recomendacoes.append("💨 **Baixo OD/Alta DBO**: Reduzir lançamento de matéria orgânica (esgoto, efluentes agroindustriais).")
    
    if not recomendacoes:
        recomendacoes.append("✅ **Boas práticas**: Manter a conservação da mata ciliar e monitorar periodicamente.")
    
    return recomendacoes


def usos_possiveis_agua(classificacao_por_ponto):
    usos_por_classe = {
        "Classe 1": ["✅ Abastecimento doméstico com desinfecção simples", "✅ Proteção da vida aquática", "✅ Irrigação", "✅ Recreação"],
        "Classe 2": ["✅ Abastecimento com tratamento convencional", "✅ Proteção da vida aquática", "✅ Irrigação", "✅ Recreação"],
        "Classe 3": ["⚠️ Abastecimento com tratamento convencional avançado", "✅ Irrigação de culturas arbóreas", "✅ Dessedentação de animais"],
        "Classe 4": ["✅ Navegação", "✅ Harmonia paisagística", "❌ Abastecimento humano", "❌ Irrigação de hortaliças"]
    }
    
    resultados = {}
    for ponto, classe, _, _, _ in classificacao_por_ponto:
        resultados[ponto] = usos_por_classe.get(classe, usos_por_classe["Classe 4"])
    
    return resultados


# Função para verificar se o cadastro está completo
def cadastro_esta_completo():
    cad = st.session_state.dados_app.get("cadastro", {})
    usuario = st.session_state.dados_app.get("usuario", {})
    
    campos_obrigatorios_cadastro = ['fazenda_nome', 'corpo_nome']
    campos_obrigatorios_usuario = ['nome', 'email']
    
    cad_ok = all(cad.get(campo) for campo in campos_obrigatorios_cadastro)
    user_ok = all(usuario.get(campo) for campo in campos_obrigatorios_usuario)
    
    return cad_ok and user_ok


#Bloco 2 - Aba 1: Cadastro
def aba_cadastro():
    st.header("📋 1. Cadastro de Usuário e Propriedade")
    st.markdown("**⚠️ O cadastro deve ser preenchido completamente para acessar as demais abas.**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Dados do Usuário")
        nome = st.text_input("Nome completo *", value=st.session_state.dados_app.get("usuario", {}).get("nome", ""))
        email = st.text_input("E-mail *", value=st.session_state.dados_app.get("usuario", {}).get("email", ""))
        telefone = st.text_input("Telefone", value=st.session_state.dados_app.get("usuario", {}).get("telefone", ""))
        
        st.subheader("Endereço")
        endereco = st.text_input("Logradouro", value=st.session_state.dados_app.get("usuario", {}).get("endereco", ""))
        cidade = st.text_input("Cidade", value=st.session_state.dados_app.get("usuario", {}).get("cidade", ""))
        estado = st.text_input("Estado (UF)", value=st.session_state.dados_app.get("usuario", {}).get("estado", ""))
    
    with col2:
        st.subheader("Localização da Fazenda")
        fazenda_nome = st.text_input("Nome da Fazenda *", value=st.session_state.dados_app.get("cadastro", {}).get("fazenda_nome", ""))
        fazenda_lat = st.number_input("Latitude (SIG BR - graus decimais)", value=st.session_state.dados_app.get("cadastro", {}).get("fazenda_lat", -15.0), format="%.6f")
        fazenda_lon = st.number_input("Longitude (SIG BR - graus decimais)", value=st.session_state.dados_app.get("cadastro", {}).get("fazenda_lon", -45.0), format="%.6f")
        
        st.subheader("Corpo Hídrico")
        corpo_nome = st.text_input("Nome do Rio/Lago/Represa *", value=st.session_state.dados_app.get("cadastro", {}).get("corpo_nome", ""))
        corpo_tipo = st.selectbox("Tipo de corpo hídrico", ["Rio", "Lago", "Represa", "Córrego", "Outro"], 
                                  index=["Rio", "Lago", "Represa", "Córrego", "Outro"].index(st.session_state.dados_app.get("cadastro", {}).get("corpo_tipo", "Rio")))
    
    st.divider()
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
    with col_btn2:
        if st.button("💾 Salvar Cadastro", type="primary"):
            st.session_state.dados_app["usuario"] = {
                "nome": nome, "email": email, "telefone": telefone,
                "endereco": endereco, "cidade": cidade, "estado": estado
            }
            st.session_state.dados_app["cadastro"] = {
                "fazenda_nome": fazenda_nome, "fazenda_lat": fazenda_lat, "fazenda_lon": fazenda_lon,
                "corpo_nome": corpo_nome, "corpo_tipo": corpo_tipo
            }
            
            if cadastro_esta_completo():
                st.session_state.cadastro_completo = True
                st.success("✅ Cadastro salvo com sucesso! Agora você pode acessar as outras abas.")
            else:
                st.session_state.cadastro_completo = False
                st.warning("⚠️ Cadastro salvo, mas ainda faltam campos obrigatórios (*). Preencha-os para acessar as demais abas.")


#Bloco 3 - Aba 2: Análises Básicas
def aba_analises():
    st.header("🧪 2. Análises Básicas de Qualidade da Água")
    st.caption("Preencha os parâmetros essenciais para classificação conforme CONAMA 357/2005. Máximo 10 pontos.")
    
    num_pontos = len(st.session_state.analises_temp)
    if num_pontos == 0:
        num_pontos = 1
        st.session_state.analises_temp = [{}]
    
    for i in range(num_pontos):
        with st.expander(f"📌 Ponto de Coleta {i+1}", expanded=(i == num_pontos-1)):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📍 Identificação**")
                ponto_nome = st.text_input(f"Nome/ID", key=f"nome_{i}", 
                                           value=st.session_state.analises_temp[i].get("nome", f"Ponto {i+1}"))
                ponto_lat = st.number_input(f"Latitude", key=f"lat_{i}", format="%.6f",
                                            value=st.session_state.analises_temp[i].get("lat", -15.0))
                ponto_lon = st.number_input(f"Longitude", key=f"lon_{i}", format="%.6f",
                                            value=st.session_state.analises_temp[i].get("lon", -45.0))
                data_coleta = st.date_input(f"Data da coleta", key=f"data_{i}",
                                            value=datetime.now())
            
            with col2:
                st.markdown("**📊 Parâmetros Físico-Químicos**")
                temperatura = st.number_input(f"Temperatura (°C)", key=f"temp_{i}", value=float(st.session_state.analises_temp[i].get("temperatura", 25.0)), step=0.1)
                ph = st.number_input(f"pH", key=f"ph_{i}", value=float(st.session_state.analises_temp[i].get("ph", 7.0)), step=0.1)
                turbidez = st.number_input(f"Turbidez (NTU)", key=f"turbidez_{i}", value=float(st.session_state.analises_temp[i].get("turbidez", 5.0)), step=0.1)
                od = st.number_input(f"Oxigênio Dissolvido - OD (mg/L)", key=f"od_{i}", value=float(st.session_state.analises_temp[i].get("od", 7.0)), step=0.1)
                dbo = st.number_input(f"DBO₅,₂₀ (mg/L)", key=f"dbo_{i}", value=float(st.session_state.analises_temp[i].get("dbo", 2.0)), step=0.1)
                coliformes = st.number_input(f"E. coli/Coliformes (NMP/100mL)", key=f"col_{i}", value=int(st.session_state.analises_temp[i].get("coliformes", 50)), step=10)
                fosforo_total = st.number_input(f"Fósforo Total (mg/L P)", key=f"p_total_{i}", value=float(st.session_state.analises_temp[i].get("fosforo_total", 0.03)), step=0.01, format="%.4f")
                nitrogenio_total = st.number_input(f"Nitrogênio Total (mg/L N)", key=f"n_total_{i}", value=float(st.session_state.analises_temp[i].get("nitrogenio_total", 1.0)), step=0.1)
            
            st.session_state.analises_temp[i] = {
                "nome": ponto_nome, "lat": ponto_lat, "lon": ponto_lon, "data": str(data_coleta),
                "temperatura": temperatura, "ph": ph, "turbidez": turbidez,
                "od": od, "dbo": dbo, "coliformes": coliformes,
                "fosforo_total": fosforo_total, "nitrogenio_total": nitrogenio_total
            }
    
    col_b1, col_b2 = st.columns([1, 1])
    with col_b1:
        if len(st.session_state.analises_temp) < 10 and st.button("➕ Adicionar outro ponto"):
            st.session_state.analises_temp.append({})
            st.rerun()
    with col_b2:
        if len(st.session_state.analises_temp) > 1 and st.button("➖ Remover último ponto"):
            st.session_state.analises_temp.pop()
            st.rerun()
    
    st.divider()
    if st.button("💾 Salvar todas as análises básicas", type="primary"):
        st.session_state.dados_app["analises"] = st.session_state.analises_temp
        st.success(f"{len(st.session_state.analises_temp)} ponto(s) salvo(s) com sucesso!")


#Bloco 4 - Aba 3: Análises Avançadas
def aba_analises_avancadas():
    st.header("🔬 3. Análises Avançadas de Qualidade da Água")
    st.caption("Parâmetros complementares - Metais, Toxicidade, Microcontaminantes (CONAMA 357/2005 e Portaria 888/2021)")
    
    num_pontos = len(st.session_state.analises_avancadas_temp)
    if num_pontos == 0:
        num_pontos = 1
        st.session_state.analises_avancadas_temp = [{}]
    
    for i in range(num_pontos):
        with st.expander(f"🔬 Parâmetros Avançados - Ponto {i+1}", expanded=(i == num_pontos-1)):
            
            ponto_ref = st.text_input(f"Referência do ponto", key=f"ref_av_{i}",
                                      value=st.session_state.analises_avancadas_temp[i].get("ponto_ref", f"Ponto {i+1}"))
            
            st.markdown("---")
            st.markdown("### 🦠 Indicadores Microbiológicos")
            col1, col2 = st.columns(2)
            
            with col1:
                densidade_ciano = st.number_input(f"Densidade de Cianobactérias (cel/mL)", key=f"ciano_{i}",
                                                  value=float(st.session_state.analises_avancadas_temp[i].get("densidade_ciano", 0)), step=100.0)
                enterococos = st.number_input(f"Enterococos (NMP/100mL)", key=f"enter_{i}",
                                             value=int(st.session_state.analises_avancadas_temp[i].get("enterococos", 0)), step=10)
            
            with col2:
                toxicidade_aguda = st.selectbox(f"Toxicidade Aguda", ["Não detectada", "Detectada", "Não analisado"],
                                               key=f"tox_ag_{i}")
                toxicidade_cronica = st.selectbox(f"Toxicidade Crônica", ["Não detectada", "Detectada", "Não analisado"],
                                                 key=f"tox_cr_{i}")
            
            st.markdown("---")
            st.markdown("### 🧪 Ânions e Parâmetros Inorgânicos")
            col3, col4 = st.columns(2)
            
            with col3:
                sulfatos = st.number_input(f"Sulfatos (mg/L SO₄)", key=f"sulf_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("sulfatos", 50.0)), step=10.0)
                fluoreto = st.number_input(f"Fluoreto (mg/L F)", key=f"fluor_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("fluoreto", 0.5)), step=0.1)
                cianeto = st.number_input(f"Cianeto (mg/L CN)", key=f"cn_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cianeto", 0.0)), step=0.01)
            
            with col4:
                cloro_residual = st.number_input(f"Cloro Residual Livre (mg/L Cl)", key=f"cloro_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cloro_residual", 0.0)), step=0.1)
                salinidade = st.number_input(f"Salinidade (PSU)", key=f"salin_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("salinidade", 0.0)), step=0.1)
            
            st.markdown("---")
            st.markdown("### 💧 Metais Pesados e Tóxicos")
            col5, col6 = st.columns(2)
            
            with col5:
                ferro = st.number_input(f"Ferro Total (mg/L Fe)", key=f"fe_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("ferro", 0.3)), step=0.1)
                manganes = st.number_input(f"Manganês (mg/L Mn)", key=f"mn_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("manganes", 0.1)), step=0.05)
                aluminio = st.number_input(f"Alumínio (mg/L Al)", key=f"al_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("aluminio", 0.1)), step=0.05)
                zinco = st.number_input(f"Zinco (mg/L Zn)", key=f"zn_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("zinco", 0.05)), step=0.01)
                cobre = st.number_input(f"Cobre (mg/L Cu)", key=f"cu_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cobre", 0.01)), step=0.01)
            
            with col6:
                chumbo = st.number_input(f"Chumbo (mg/L Pb)", key=f"pb_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("chumbo", 0.001)), step=0.001, format="%.4f")
                cadmio = st.number_input(f"Cádmio (mg/L Cd)", key=f"cd_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cadmio", 0.0005)), step=0.0005, format="%.4f")
                mercurio = st.number_input(f"Mercúrio (mg/L Hg)", key=f"hg_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("mercurio", 0.0001)), step=0.0001, format="%.4f")
                arsenio = st.number_input(f"Arsênio (mg/L As)", key=f"as_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("arsenio", 0.001)), step=0.001, format="%.4f")
                cromo = st.number_input(f"Cromo Total (mg/L Cr)", key=f"cr_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cromo", 0.01)), step=0.01)
            
            st.markdown("---")
            st.markdown("### 🧴 Compostos Orgânicos")
            col7, col8 = st.columns(2)
            
            with col7:
                oleos_graxas = st.number_input(f"Óleos e Graxas (mg/L)", key=f"oleo_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("oleos_graxas", 0.0)), step=0.5)
                benzeno = st.number_input(f"Benzeno (µg/L)", key=f"benz_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("benzeno", 0.0)), step=1.0)
            
            with col8:
                pesticidas = st.text_input(f"Pesticidas", key=f"pest_{i}", 
                                          value=st.session_state.analises_avancadas_temp[i].get("pesticidas", "Não detectado"))
            
            st.markdown("---")
            st.markdown("### 📊 Índices Integradores")
            col9, col10 = st.columns(2)
            
            with col9:
                iqa = st.number_input(f"IQA (0-100)", key=f"iqa_{i}",
                                     value=float(st.session_state.analises_avancadas_temp[i].get("iqa", 70.0)), step=1.0, min_value=0.0, max_value=100.0)
            
            with col10:
                iet = st.selectbox(f"IET", ["Ultraoligotrófico", "Oligotrófico", "Mesotrófico", "Eutrófico", "Hipereutrófico", "Não calculado"],
                                  key=f"iet_{i}")
            
            st.session_state.analises_avancadas_temp[i] = {
                "ponto_ref": ponto_ref,
                "densidade_ciano": densidade_ciano, "enterococos": enterococos,
                "toxicidade_aguda": toxicidade_aguda, "toxicidade_cronica": toxicidade_cronica,
                "sulfatos": sulfatos, "fluoreto": fluoreto, "cianeto": cianeto,
                "cloro_residual": cloro_residual, "salinidade": salinidade,
                "ferro": ferro, "manganes": manganes, "aluminio": aluminio,
                "zinco": zinco, "cobre": cobre, "chumbo": chumbo,
                "cadmio": cadmio, "mercurio": mercurio, "arsenio": arsenio, "cromo": cromo,
                "oleos_graxas": oleos_graxas, "benzeno": benzeno,
                "pesticidas": pesticidas, "iqa": iqa, "iet": iet
            }
    
    col_b1, col_b2 = st.columns([1, 1])
    with col_b1:
        if len(st.session_state.analises_avancadas_temp) < 10 and st.button("➕ Adicionar outro ponto (avançado)"):
            st.session_state.analises_avancadas_temp.append({})
            st.rerun()
    with col_b2:
        if len(st.session_state.analises_avancadas_temp) > 1 and st.button("➖ Remover último ponto (avançado)"):
            st.session_state.analises_avancadas_temp.pop()
            st.rerun()
    
    st.divider()
    if st.button("💾 Salvar análises avançadas", type="primary"):
        st.session_state.dados_app["analises_avancadas"] = st.session_state.analises_avancadas_temp
        st.success(f"{len(st.session_state.analises_avancadas_temp)} ponto(s) de análise avançada salvo(s)!")


#Bloco 5 - Aba 4: Levantamento Ambiental
def aba_levantamento():
    st.header("🌍 4. Levantamento de Causas Ambientais")
    
    lev = st.session_state.dados_app.get("levantamento", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Características da Bacia")
        cobertura_solo = st.selectbox("Cobertura do solo predominante", 
                                      ["Florestada", "Pastagem", "Agricultura", "Urbana", "Mista"],
                                      index=["Florestada", "Pastagem", "Agricultura", "Urbana", "Mista"].index(lev.get("cobertura_solo", "Florestada")))
        
        tipo_solo = st.selectbox("Tipo de solo predominante",
                                 ["Argiloso", "Arenoso", "Siltoso", "Latossolo", "Outro"],
                                 index=["Argiloso", "Arenoso", "Siltoso", "Latossolo", "Outro"].index(lev.get("tipo_solo", "Argiloso")))
        
        relevo = st.selectbox("Relevo da região",
                              ["Plano", "Suave ondulado", "Ondulado", "Montanhoso"],
                              index=["Plano", "Suave ondulado", "Ondulado", "Montanhoso"].index(lev.get("relevo", "Plano")))
    
    with col2:
        st.subheader("Atividades e Impactos")
        fontes_poluicao = st.multiselect("Fontes de poluição identificadas",
                                         ["Esgoto doméstico", "Efluente industrial", "Agrotóxicos", "Mineração", "Queimadas", "Assoreamento"],
                                         default=lev.get("fontes_poluicao", []))
    
    st.subheader("Observações")
    observacoes = st.text_area("Observações adicionais", value=lev.get("observacoes", ""))
    
    st.divider()
    if st.button("💾 Salvar Levantamento", type="primary"):
        st.session_state.dados_app["levantamento"] = {
            "cobertura_solo": cobertura_solo, "tipo_solo": tipo_solo, "relevo": relevo,
            "fontes_poluicao": fontes_poluicao, "observacoes": observacoes
        }
        st.success("Levantamento salvo com sucesso!")


#Bloco 6 - Aba 5: Mapa de Localização
def aba_mapa():
    st.header("🗺️ 5. Mapa de Localização")
    
    st.info("🔑 **Configuração da Chave API Google Maps:** No código, procure por `CHAVE_API_GOOGLE = \"\"` e insira sua chave entre as aspas.")
    
    if CHAVE_API_GOOGLE and CHAVE_API_GOOGLE.strip():
        st.success("✅ Chave do Google Maps configurada! Usando camadas do Google.")
    else:
        st.info("ℹ️ Usando OpenStreetMap. Para usar Google Maps, insira sua chave na variável CHAVE_API_GOOGLE no código.")
    
    cad = st.session_state.dados_app.get("cadastro", {})
    fazenda_coords = (cad.get("fazenda_lat", -15.0), cad.get("fazenda_lon", -45.0))
    fazenda_nome = cad.get("fazenda_nome", "Fazenda")
    corpo_nome = cad.get("corpo_nome", "Corpo hídrico")
    analises = st.session_state.dados_app.get("analises", [])
    
    m = folium.Map(location=[fazenda_coords[0], fazenda_coords[1]], zoom_start=13, control_scale=True)
    
    folium.Marker(location=[fazenda_coords[0], fazenda_coords[1]],
                  popup=f"🏠 {fazenda_nome}", icon=folium.Icon(color="green", icon="home", prefix='fa')).add_to(m)
    
    for i, ponto in enumerate(analises):
        lat = ponto.get("lat")
        lon = ponto.get("lon")
        if lat and lon:
            classe, cor, _, _ = classificar_ponto(ponto)
            cor_icon = "darkgreen" if "Classe 1" in classe else "orange" if "Classe 2" in classe else "red"
            folium.Marker(location=[lat, lon], popup=f"{ponto.get('nome', f'Ponto {i+1}')}<br>Classe: {classe}",
                          icon=folium.Icon(color=cor_icon, icon="water", prefix='fa')).add_to(m)
    
    if CHAVE_API_GOOGLE and CHAVE_API_GOOGLE.strip():
        try:
            folium.TileLayer(tiles=f"https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}&key={CHAVE_API_GOOGLE}",
                             attr="Google Maps", name="Google Maps", control=True).add_to(m)
        except Exception as e:
            st.warning(f"Erro ao adicionar Google Maps: {e}")
    
    folium.LayerControl().add_to(m)
    st_folium(m, width=900, height=500)
    
    if analises:
        df_pontos = pd.DataFrame([{"Ponto": p.get("nome", f"Ponto {i+1}"), "Latitude": p.get("lat"), "Longitude": p.get("lon")} 
                                  for i, p in enumerate(analises) if p.get("lat")])
        st.dataframe(df_pontos, use_container_width=True)


#Bloco 7 - Aba 6: Relatório de Classificação
def aba_relatorio():
    st.header("📊 6. Relatório de Classificação da Qualidade da Água")
    
    analises = st.session_state.dados_app.get("analises", [])
    if not analises:
        st.warning("Nenhuma análise cadastrada.")
        return
    
    pontos_classificados = []
    for ponto in analises:
        classe, cor, usos, motivos = classificar_ponto(ponto)
        pontos_classificados.append((ponto.get("nome", "Ponto"), classe, cor, usos, motivos))
    
    status_geral, cor_geral, _ = avaliar_trecho(pontos_classificados)
    
    st.subheader(f"Classificação Geral - {status_geral} {cor_geral}")
    
    for nome, classe, cor, usos, motivos in pontos_classificados:
        with st.expander(f"{cor} {nome} - {classe}"):
            st.write("**Usos recomendados:**", usos[0] if usos else "N/A")
            if motivos:
                st.write("**Fatores:**", ", ".join(motivos[:2]))


#Bloco 8 - Aba 7: Manejos e Usos
def aba_manejos():
    st.header("🌱 7. Possíveis Manejos e Usos da Água")
    
    analises = st.session_state.dados_app.get("analises", [])
    levantamento = st.session_state.dados_app.get("levantamento", {})
    
    if not analises:
        st.warning("Nenhuma análise cadastrada.")
        return
    
    pontos_classificados = []
    for ponto in analises:
        classe, _, usos, _ = classificar_ponto(ponto)
        pontos_classificados.append((ponto.get("nome", "Ponto"), classe, None, usos, []))
    
    status_geral, _, _ = avaliar_trecho(pontos_classificados)
    recomendacoes = gerar_recomendacoes_manejo(levantamento, status_geral, analises)
    
    st.subheader("Recomendações de Manejo")
    for rec in recomendacoes:
        st.markdown(rec)
    
    st.divider()
    st.subheader("Usos Possíveis por Ponto")
    usos_por_ponto = usos_possiveis_agua(pontos_classificados)
    for ponto, lista_usos in usos_por_ponto.items():
        with st.expander(f"📌 {ponto}"):
            for uso in lista_usos:
                st.write(uso)


#Bloco 9 - Função principal (main)
def main():
    st.sidebar.title("💧 Sistema de Qualidade da Água")
    st.sidebar.markdown("---")
    
    # Verificar cadastro para liberar abas
    if not st.session_state.cadastro_completo and cadastro_esta_completo():
        st.session_state.cadastro_completo = True
    
    if not st.session_state.cadastro_completo:
        st.sidebar.warning("⚠️ Complete o cadastro na aba **Cadastro** para acessar as demais funcionalidades.")
        abas_disponiveis = ["📋 Cadastro"]
    else:
        abas_disponiveis = ["📋 Cadastro", "🧪 Análises Básicas", "🔬 Análises Avançadas", "🌍 Levantamento", "🗺️ Mapa", "📊 Relatório", "🌱 Manejos e Usos"]
    
    aba_selecionada = st.sidebar.radio("Navegação", abas_disponiveis)
    
    if aba_selecionada == "📋 Cadastro":
        aba_cadastro()
    elif aba_selecionada == "🧪 Análises Básicas":
        aba_analises()
    elif aba_selecionada == "🔬 Análises Avançadas":
        aba_analises_avancadas()
    elif aba_selecionada == "🌍 Levantamento":
        aba_levantamento()
    elif aba_selecionada == "🗺️ Mapa":
        aba_mapa()
    elif aba_selecionada == "📊 Relatório":
        aba_relatorio()
    elif aba_selecionada == "🌱 Manejos e Usos":
        aba_manejos()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Leis base: CONAMA 357/2005, Portaria 888/2021")


if __name__ == "__main__":
    main()
