import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from datetime import datetime
import requests
import json
import time

st.set_page_config(page_title="Sistema de Qualidade da Água", page_icon="💧", layout="wide")

# ============================================================
# 🔑 CONFIGURAÇÕES - ÚNICO LUGAR QUE VOCÊ PRECISA ALTERAR
# ============================================================
CHAVE_API_GOOGLE = "AIzaSyCbBzrvMUD8EZLO7v9EoYM9jiTmDDvDs9I"  # COLE SUA CHAVE DO GOOGLE MAPS AQUI (opcional)
USAR_OPEN_TOPODATA = True  # API gratuita para elevação (recomendado)
# ============================================================

# ============================================================================
# FUNÇÕES PARA CONVERSÃO DE COORDENADAS (GRAUS DECIMAIS <-> GMS)
# ============================================================================

def decimal_para_gms(valor_decimal):
    """Converte coordenadas de graus decimais para Graus, Minutos e Segundos"""
    if valor_decimal is None:
        return (0, 0, 0.0)
    
    valor_abs = abs(valor_decimal)
    graus = int(valor_abs)
    minutos_restantes = (valor_abs - graus) * 60
    minutos = int(minutos_restantes)
    segundos = (minutos_restantes - minutos) * 60
    segundos = round(segundos, 2)
    
    return (graus, minutos, segundos)


def gms_para_decimal(graus, minutos, segundos, direcao):
    """Converte coordenadas de GMS para graus decimais"""
    valor_decimal = graus + (minutos / 60) + (segundos / 3600)
    if direcao in ["S", "O", "W"]:
        valor_decimal = -valor_decimal
    return valor_decimal


# ============================================================================
# INICIALIZAÇÃO DA SESSÃO
# ============================================================================

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
# FUNÇÕES DE ESTIMATIVA DE RELEVO E COBERTURA DO SOLO
# ============================================================

def estimar_elevacao_opentopodata(lat, lon):
    """Estima a elevação usando API OpenTopoData (gratuita, sem chave)"""
    try:
        url = f"https://api.opentopodata.org/v1/srtm90m?locations={lat},{lon}"
        response = requests.get(url, timeout=10)
        dados = response.json()
        
        if dados.get("status") == "OK":
            elevacao = dados["results"][0]["elevation"]
            if elevacao is not None:
                return elevacao
        return None
    except Exception as e:
        st.warning(f"Erro ao acessar OpenTopoData: {e}")
        return None

def estimar_elevacao_google(lat, lon):
    """Estima a elevação usando Google Elevation API (requer chave)"""
    if not CHAVE_API_GOOGLE:
        return None
    try:
        url = f"https://maps.googleapis.com/maps/api/elevation/json?locations={lat},{lon}&key={CHAVE_API_GOOGLE}"
        resp = requests.get(url, timeout=10).json()
        if resp['status'] == 'OK':
            return resp['results'][0]['elevation']
    except:
        return None
    return None

def estimar_relevo_por_coordenadas(lat, lon):
    """Estima o tipo de relevo baseado na elevação"""
    elevacao = None
    
    if USAR_OPEN_TOPODATA:
        elevacao = estimar_elevacao_opentopodata(lat, lon)
    
    if elevacao is None and CHAVE_API_GOOGLE:
        elevacao = estimar_elevacao_google(lat, lon)
    
    if elevacao is None:
        return "Não disponível", None
    
    if elevacao < 100:
        return "Plano/Baixada", elevacao
    elif elevacao < 300:
        return "Suave ondulado", elevacao
    elif elevacao < 700:
        return "Ondulado", elevacao
    else:
        return "Montanhoso", elevacao

def estimar_cobertura_solo_por_coordenadas(lat, lon):
    """
    Estimativa aproximada de cobertura do solo baseada em biomas brasileiros
    (MapBiomas simplificado - sem chave)
    """
    if -33 < lat < -4 and -74 < lon < -34:
        if lat < -15 and lon < -45:
            return "Campo/Agricultura (Região Sul)"
        elif lat > -10:
            return "Floresta Amazônica"
        elif -20 < lat < -10:
            if lon < -50:
                return "Cerrado (Savana)"
            else:
                return "Mata Atlântica"
        else:
            return "Pastagem/Agricultura"
    else:
        return "Informação baseada em bioma regional"

def classificar_classe_textural_solo(tipo_solo):
    """Classifica o solo e dá recomendações"""
    classes = {
        "Argiloso": "Alta retenção de água, risco de erosão em encostas",
        "Arenoso": "Baixa retenção de água, alto risco de lixiviação",
        "Siltoso": "Média retenção, suscetível a erosão hídrica",
        "Latossolo": "Boa drenagem, baixo risco de erosão",
        "Não sei": "Realize análise de solo para melhor diagnóstico"
    }
    return classes.get(tipo_solo, "Realize análise de solo")


# ============================================================
# FUNÇÕES DE CLASSIFICAÇÃO DA QUALIDADE DA ÁGUA
# ============================================================

def classificar_ponto_basico(analise):
    """Classifica baseado nos parâmetros da CONAMA 357/2005"""
    params_preenchidos = [k for k, v in analise.items() if v not in [None, "", 0] and k not in ['nome', 'lat', 'lon', 'data']]
    
    if len(params_preenchidos) < 3:
        return "Dados insuficientes", "⚪", ["Adicione mais parâmetros para classificação (mínimo 3)"], params_preenchidos
    
    classe = 1
    violacoes = []
    
    # OD - Oxigênio Dissolvido
    if 'od' in analise and analise['od']:
        od = analise['od']
        if od < 4.0:
            classe = max(classe, 4)
            violacoes.append(f"OD muito baixo: {od} mg/L (Classe 4)")
        elif od < 5.0:
            classe = max(classe, 3)
            violacoes.append(f"OD abaixo: {od} mg/L (Classe 3)")
        elif od < 6.0:
            classe = max(classe, 2)
            violacoes.append(f"OD: {od} mg/L (Classe 2)")
    
    # pH
    if 'ph' in analise and analise['ph']:
        ph = analise['ph']
        if ph < 6.0 or ph > 9.0:
            classe = max(classe, 4)
            violacoes.append(f"pH fora do padrão: {ph}")
        elif ph < 6.5 or ph > 8.5:
            classe = max(classe, 3)
            violacoes.append(f"pH: {ph} (faixa da Classe 3)")
    
    # DBO
    if 'dbo' in analise and analise['dbo']:
        dbo = analise['dbo']
        if dbo > 10.0:
            classe = max(classe, 4)
            violacoes.append(f"DBO alta: {dbo} mg/L (Classe 4)")
        elif dbo > 5.0:
            classe = max(classe, 3)
            violacoes.append(f"DBO: {dbo} mg/L (Classe 3)")
        elif dbo > 3.0:
            classe = max(classe, 2)
            violacoes.append(f"DBO: {dbo} mg/L (Classe 2)")
    
    # Turbidez
    if 'turbidez' in analise and analise['turbidez']:
        turb = analise['turbidez']
        if turb > 100:
            classe = max(classe, 4)
        elif turb > 40:
            classe = max(classe, 3)
        elif turb > 10:
            classe = max(classe, 2)
    
    # Coliformes/E. coli
    if 'coliformes' in analise and analise['coliformes']:
        col = analise['coliformes']
        if col > 4000:
            classe = max(classe, 4)
            violacoes.append(f"Coliformes altos: {col} NMP/100mL")
        elif col > 1000:
            classe = max(classe, 3)
            violacoes.append(f"Coliformes: {col} NMP/100mL (Classe 3)")
        elif col > 200:
            classe = max(classe, 2)
            violacoes.append(f"Coliformes: {col} NMP/100mL (Classe 2)")
    
    # Fósforo Total
    if 'p_total' in analise and analise['p_total']:
        p = analise['p_total']
        if p > 0.15:
            classe = max(classe, 3)
            violacoes.append(f"Fósforo alto: {p} mg/L")
        elif p > 0.05:
            classe = max(classe, 2)
    
    # Nitrogênio Total
    if 'n_total' in analise and analise['n_total']:
        n = analise['n_total']
        if n > 3.7:
            classe = max(classe, 3)
            violacoes.append(f"Nitrogênio alto: {n} mg/L")
        elif n > 2.0:
            classe = max(classe, 2)
    
    # Metais
    metais = ['chumbo', 'cadmio', 'mercurio', 'arsenio', 'cromo', 'cobre', 'zinco', 'ferro']
    for metal in metais:
        if metal in analise and analise[metal] and analise[metal] > 0.01:
            classe = max(classe, 3)
            violacoes.append(f"{metal.capitalize()} detectado: {analise[metal]} mg/L")
    
    # Classificação final
    classes = {
        1: ("Classe 1", "🟢", ["Excelente qualidade - adequado para todos os usos", "Abastecimento com desinfecção simples", "Preservação da vida aquática"]),
        2: ("Classe 2", "🟡", ["Qualidade boa - requer tratamento convencional", "Abastecimento após tratamento", "Irrigação e recreação"]),
        3: ("Classe 3", "🟠", ["Qualidade regular - requer tratamento avançado", "Abastecimento após tratamento convencional", "Irrigação de culturas arbóreas"]),
        4: ("Classe 4", "🔴", ["Qualidade ruim - restrição de usos", "Apenas navegação e harmonia paisagística", "Necessita intervenção prioritária"])
    }
    
    classe_texto, cor, recomendacoes = classes.get(classe, ("Classe 4", "🔴", ["Usos restritos"]))
    
    return classe_texto, cor, recomendacoes, params_preenchidos, violacoes


def classificar_ponto_avancado(analise):
    """Classificação para parâmetros avançados (metais, toxicidade)"""
    status = "Atende"
    alertas = []
    
    # Limites de referência para água doce (CONAMA 357/2005)
    limites = {
        "ferro": 0.3, "manganes": 0.1, "aluminio": 0.1, "zinco": 0.18,
        "cobre": 0.009, "chumbo": 0.01, "cadmio": 0.001, "mercurio": 0.0002,
        "arsenio": 0.01, "cromo": 0.05, "niquel": 0.025, "selenio": 0.01,
        "cianeto": 0.005, "fenois": 0.003, "benzeno": 0.005
    }
    
    for param, limite in limites.items():
        if param in analise and analise[param] and analise[param] > limite:
            alertas.append(f"{param}: {analise[param]} mg/L (limite: {limite})")
            status = "Atenção necessária"
    
    if alertas:
        return "Fora dos padrões", "🔴", alertas
    return "Dentro dos padrões", "🟢", ["Todos os parâmetros dentro dos limites CONAMA 357/2005"]


# ============================================================
# FUNÇÕES DE RECOMENDAÇÕES DE MANEJO
# ============================================================

def gerar_recomendacoes_manejo(levantamento, classificacao, analises):
    recomendacoes = []
    
    # Baseado na cobertura do solo
    cobertura = levantamento.get('cobertura', '')
    if cobertura == "Agricultura":
        recomendacoes.append({
            "titulo": "🌾 Práticas Agrícolas Sustentáveis",
            "descricao": "Implementar plantio direto, curvas de nível e faixas de amortecimento (buffers) com vegetação nativa entre a lavoura e o corpo d'água.",
            "prioridade": "Alta"
        })
    elif cobertura == "Pastagem":
        recomendacoes.append({
            "titulo": "🐄 Manejo da Pastagem",
            "descricao": "Evitar acesso direto do gado à água, cercar nascentes, implantar sistemas silvipastoris e recuperar áreas degradadas.",
            "prioridade": "Alta"
        })
    elif cobertura == "Urbana":
        recomendacoes.append({
            "titulo": "🏙️ Gestão de Águas Urbanas",
            "descricao": "Investir em saneamento básico, tratamento de esgoto e sistemas de drenagem sustentável (biorretenção, pavimentos permeáveis).",
            "prioridade": "Muito Alta"
        })
    elif cobertura == "Florestada":
        recomendacoes.append({
            "titulo": "🌳 Conservação da Vegetação Nativa",
            "descricao": "Manter a mata ciliar, evitar desmatamento e monitorar possíveis focos de queimada.",
            "prioridade": "Média"
        })
    
    # Baseado nas fontes de poluição
    fontes = levantamento.get('fontes', [])
    if "Esgoto" in fontes:
        recomendacoes.append({
            "titulo": "🏠 Tratamento de Esgoto",
            "descricao": "Implementar ou ampliar sistemas de tratamento de esgoto. Evitar lançamento in natura. Considerar wetlands construídos.",
            "prioridade": "Muito Alta"
        })
    if "Agropecuária" in fontes:
        recomendacoes.append({
            "titulo": "🧪 Manejo de Agroquímicos",
            "descricao": "Reduzir uso de fertilizantes nitrogenados e fosfatados. Adotar manejo integrado de pragas. Respeitar faixas de proteção.",
            "prioridade": "Alta"
        })
    if "Indústria" in fontes:
        recomendacoes.append({
            "titulo": "🏭 Controle Industrial",
            "descricao": "Exigir tratamento de efluentes industriais, monitoramento constante e licenciamento ambiental.",
            "prioridade": "Muito Alta"
        })
    if "Mineração" in fontes:
        recomendacoes.append({
            "titulo": "⛏️ Gestão de Mineração",
            "descricao": "Implementar sistemas de contenção de rejeitos, tratamento de drenagem ácida e recuperação de áreas degradadas.",
            "prioridade": "Muito Alta"
        })
    if "Resíduos sólidos" in fontes:
        recomendacoes.append({
            "titulo": "🗑️ Gestão de Resíduos",
            "descricao": "Implementar coleta seletiva, destinar resíduos para aterros sanitários e combater lixões a céu aberto.",
            "prioridade": "Alta"
        })
    
    # Baseado na classificação da água
    if "Classe 3" in classificacao or "Classe 4" in classificacao:
        recomendacoes.append({
            "titulo": "🔄 Tratamento da Água",
            "descricao": "Adotar tratamento convencional (coagulação, floculação, decantação, filtração e desinfecção) antes do consumo.",
            "prioridade": "Muito Alta"
        })
    
    if not recomendacoes:
        recomendacoes.append({
            "titulo": "✅ Boas Práticas de Conservação",
            "descricao": "Manter a mata ciliar preservada, monitorar a qualidade periodicamente e evitar atividades potencialmente poluidoras.",
            "prioridade": "Média"
        })
    
    return recomendacoes


# ============================================================================
# ABA 1 - CADASTRO
# ============================================================================

def aba_cadastro():
    st.header("📋 1. Cadastro de Usuário e Propriedade")
    st.markdown("**⚠️ Campos com * são obrigatórios para liberar as demais abas.**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👤 Dados do Usuário")
        nome = st.text_input("Nome completo *", value=st.session_state.dados_app.get("usuario", {}).get("nome", ""))
        email = st.text_input("E-mail *", value=st.session_state.dados_app.get("usuario", {}).get("email", ""))
        telefone = st.text_input("Telefone", value=st.session_state.dados_app.get("usuario", {}).get("telefone", ""))
        
        st.subheader("📍 Endereço")
        endereco = st.text_input("Logradouro", value=st.session_state.dados_app.get("usuario", {}).get("endereco", ""))
        cidade = st.text_input("Cidade", value=st.session_state.dados_app.get("usuario", {}).get("cidade", ""))
        estado = st.text_input("Estado (UF)", value=st.session_state.dados_app.get("usuario", {}).get("estado", ""))
    
    with col2:
        st.subheader("🏠 Localização da Fazenda")
        fazenda_nome = st.text_input("Nome da Fazenda *", value=st.session_state.dados_app.get("cadastro", {}).get("fazenda_nome", ""))
        
        # ========== COORDENADAS EM GRAUS, MINUTOS E SEGUNDOS ==========
        st.markdown("**🗺️ Coordenadas Geográficas (Graus, Minutos, Segundos)**")
        
        # Recuperar valores existentes ou usar padrão
        lat_decimal = float(st.session_state.dados_app.get("cadastro", {}).get("fazenda_lat", -15.0))
        lon_decimal = float(st.session_state.dados_app.get("cadastro", {}).get("fazenda_lon", -45.0))
        
        # Converter para GMS
        lat_graus, lat_minutos, lat_segundos = decimal_para_gms(lat_decimal)
        lon_graus, lon_minutos, lon_segundos = decimal_para_gms(lon_decimal)
        
        # Latitude
        st.markdown("**Latitude:**")
        col_lat1, col_lat2, col_lat3, col_lat4 = st.columns([1, 1, 1, 1])
        with col_lat1:
            lat_graus_input = st.number_input("Graus", min_value=0, max_value=90, value=lat_graus, step=1)
        with col_lat2:
            lat_minutos_input = st.number_input("Minutos", min_value=0, max_value=59, value=lat_minutos, step=1)
        with col_lat3:
            lat_segundos_input = st.number_input("Segundos", min_value=0.0, max_value=59.99, value=float(lat_segundos), step=0.01, format="%.2f")
        with col_lat4:
            lat_direcao = st.selectbox("Direção", ["S", "N"], index=0 if lat_decimal < 0 else 1)
        
        # Longitude
        st.markdown("**Longitude:**")
        col_lon1, col_lon2, col_lon3, col_lon4 = st.columns([1, 1, 1, 1])
        with col_lon1:
            lon_graus_input = st.number_input("Graus", min_value=0, max_value=180, value=lon_graus, step=1)
        with col_lon2:
            lon_minutos_input = st.number_input("Minutos", min_value=0, max_value=59, value=lon_minutos, step=1)
        with col_lon3:
            lon_segundos_input = st.number_input("Segundos", min_value=0.0, max_value=59.99, value=float(lon_segundos), step=0.01, format="%.2f")
        with col_lon4:
            lon_direcao = st.selectbox("Direção", ["O", "L"], index=0 if lon_decimal < 0 else 1)
        
        # Converter GMS de volta para decimal para salvar
        fazenda_lat = gms_para_decimal(lat_graus_input, lat_minutos_input, lat_segundos_input, lat_direcao)
        fazenda_lon = gms_para_decimal(lon_graus_input, lon_minutos_input, lon_segundos_input, lon_direcao)
        
        # Exibir coordenadas decimais para referência
        st.caption(f"📍 Coordenadas decimais: {fazenda_lat:.6f}, {fazenda_lon:.6f}")
        
        st.subheader("💧 Corpo Hídrico")
        corpo_nome = st.text_input("Nome do Rio/Lago/Represa *", value=st.session_state.dados_app.get("cadastro", {}).get("corpo_nome", ""))
        corpo_tipo = st.selectbox("Tipo de corpo hídrico", ["Rio", "Lago", "Represa", "Córrego", "Outro"], 
                                  index=["Rio", "Lago", "Represa", "Córrego", "Outro"].index(
                                      st.session_state.dados_app.get("cadastro", {}).get("corpo_tipo", "Rio")))
    
    st.divider()
    
    # Status do cadastro
    if st.session_state.cadastro_completo:
        st.success("✅ **Cadastro já realizado!** Você tem acesso a todas as abas.")
        if st.button("📝 Atualizar dados do cadastro", type="secondary"):
            st.session_state.cadastro_completo = False
            st.rerun()
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
    with col_btn2:
        if st.button("💾 Salvar Cadastro", type="primary"):
            st.session_state.dados_app["usuario"] = {
                "nome": nome, "email": email, "telefone": telefone,
                "endereco": endereco, "cidade": cidade, "estado": estado
            }
            st.session_state.dados_app["cadastro"] = {
                "fazenda_nome": fazenda_nome, 
                "fazenda_lat": fazenda_lat, 
                "fazenda_lon": fazenda_lon,
                "corpo_nome": corpo_nome, 
                "corpo_tipo": corpo_tipo
            }
            
            if nome and email and fazenda_nome and corpo_nome:
                st.session_state.cadastro_completo = True
                st.success("✅ **CADASTRO REALIZADO COM SUCESSO!**")
                st.balloons()
                st.info("📌 **Agora você pode acessar todas as abas do sistema.**")
                st.rerun()
            else:
                st.session_state.cadastro_completo = False
                st.warning("⚠️ **Cadastro incompleto!** Preencha todos os campos com *.")


# ============================================================
# ABA 2 - ANÁLISES BÁSICAS
# ============================================================

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
                st.markdown("**📍 Identificação do Ponto**")
                ponto_nome = st.text_input(f"Nome/ID do ponto", key=f"nome_{i}", 
                                           value=st.session_state.analises_temp[i].get("nome", f"Ponto {i+1}"))
                ponto_lat = st.number_input(f"Latitude (graus decimais)", key=f"lat_{i}", format="%.6f",
                                            value=float(st.session_state.analises_temp[i].get("lat", st.session_state.dados_app.get("cadastro", {}).get("fazenda_lat", -15.0))))
                ponto_lon = st.number_input(f"Longitude (graus decimais)", key=f"lon_{i}", format="%.6f",
                                            value=float(st.session_state.analises_temp[i].get("lon", st.session_state.dados_app.get("cadastro", {}).get("fazenda_lon", -45.0))))
                data_coleta = st.date_input(f"Data da coleta", key=f"data_{i}", value=datetime.now())
            
            with col2:
                st.markdown("**📊 Parâmetros Físico-Químicos**")
                temperatura = st.number_input(f"Temperatura (°C)", key=f"temp_{i}", value=float(st.session_state.analises_temp[i].get("temperatura", 25.0)), step=0.1, format="%.1f")
                ph = st.number_input(f"pH", key=f"ph_{i}", value=float(st.session_state.analises_temp[i].get("ph", 7.0)), step=0.1, format="%.1f")
                condutividade = st.number_input(f"Condutividade Elétrica (µS/cm)", key=f"cond_{i}", value=float(st.session_state.analises_temp[i].get("condutividade", 100.0)), step=10.0, format="%.1f")
                turbidez = st.number_input(f"Turbidez (NTU)", key=f"turb_{i}", value=float(st.session_state.analises_temp[i].get("turbidez", 5.0)), step=0.1, format="%.1f")
                cor_aparente = st.number_input(f"Cor Aparente (mg/L Pt-Co)", key=f"cor_{i}", value=int(st.session_state.analises_temp[i].get("cor_aparente", 10)), step=5)
                
                st.markdown("**💨 Oxigênio e Demanda**")
                od = st.number_input(f"Oxigênio Dissolvido - OD (mg/L)", key=f"od_{i}", value=float(st.session_state.analises_temp[i].get("od", 7.0)), step=0.1, format="%.1f")
                dbo = st.number_input(f"DBO₅,₂₀ (mg/L)", key=f"dbo_{i}", value=float(st.session_state.analises_temp[i].get("dbo", 2.0)), step=0.1, format="%.1f")
                dqo = st.number_input(f"DQO (mg/L)", key=f"dqo_{i}", value=float(st.session_state.analises_temp[i].get("dqo", 10.0)), step=1.0, format="%.1f")
                
                st.markdown("**🧫 Nutrientes**")
                n_amoniacal = st.number_input(f"Nitrogênio Amoniacal (mg/L)", key=f"nam_{i}", value=float(st.session_state.analises_temp[i].get("n_amoniacal", 0.5)), step=0.1, format="%.2f")
                nitrato = st.number_input(f"Nitrato (mg/L N)", key=f"nit_{i}", value=float(st.session_state.analises_temp[i].get("nitrato", 1.0)), step=0.1, format="%.2f")
                nitrito = st.number_input(f"Nitrito (mg/L N)", key=f"nito_{i}", value=float(st.session_state.analises_temp[i].get("nitrito", 0.05)), step=0.01, format="%.3f")
                n_total = st.number_input(f"Nitrogênio Total (mg/L N)", key=f"nt_{i}", value=float(st.session_state.analises_temp[i].get("n_total", 1.0)), step=0.1, format="%.2f")
                p_total = st.number_input(f"Fósforo Total (mg/L P)", key=f"pt_{i}", value=float(st.session_state.analises_temp[i].get("p_total", 0.03)), step=0.01, format="%.4f")
                fosfato = st.number_input(f"Fosfato Total (mg/L)", key=f"fos_{i}", value=float(st.session_state.analises_temp[i].get("fosfato", 0.1)), step=0.01, format="%.3f")
                
                st.markdown("**🦠 Indicadores Biológicos**")
                coliformes = st.number_input(f"Coliformes Termotolerantes (NMP/100mL)", key=f"col_{i}", value=int(st.session_state.analises_temp[i].get("coliformes", 50)), step=10)
                e_coli = st.number_input(f"E. coli (NMP/100mL)", key=f"ec_{i}", value=int(st.session_state.analises_temp[i].get("e_coli", 50)), step=10)
                clorofila = st.number_input(f"Clorofila-a (µg/L)", key=f"cl_{i}", value=float(st.session_state.analises_temp[i].get("clorofila", 5.0)), step=1.0, format="%.1f")
            
            # Salvar
            st.session_state.analises_temp[i] = {
                "nome": ponto_nome, "lat": ponto_lat, "lon": ponto_lon, "data": str(data_coleta),
                "temperatura": temperatura, "ph": ph, "condutividade": condutividade,
                "turbidez": turbidez, "cor_aparente": cor_aparente,
                "od": od, "dbo": dbo, "dqo": dqo,
                "n_amoniacal": n_amoniacal, "nitrato": nitrato, "nitrito": nitrito,
                "n_total": n_total, "p_total": p_total, "fosfato": fosfato,
                "coliformes": coliformes, "e_coli": e_coli, "clorofila": clorofila
            }
    
    col_b1, col_b2 = st.columns(2)
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
        st.success(f"✅ {len(st.session_state.analises_temp)} ponto(s) de coleta salvos com sucesso!")
        st.info("📌 Estes dados serão usados para classificar a qualidade da água e gerar o relatório.")


# ============================================================
# ABA 3 - ANÁLISES AVANÇADAS
# ============================================================

def aba_analises_avancadas():
    st.header("🔬 3. Análises Avançadas de Qualidade da Água")
    st.caption("Parâmetros complementares - Metais Pesados, Toxicidade, Microcontaminantes (CONAMA 357/2005 e Portaria 888/2021)")
    
    num_pontos = len(st.session_state.analises_avancadas_temp)
    if num_pontos == 0:
        num_pontos = 1
        st.session_state.analises_avancadas_temp = [{}]
    
    for i in range(num_pontos):
        with st.expander(f"🔬 Parâmetros Avançados - Ponto {i+1}", expanded=(i == num_pontos-1)):
            
            ponto_ref = st.text_input(f"Referência do ponto (nome/ID)", key=f"ref_av_{i}",
                                      value=st.session_state.analises_avancadas_temp[i].get("ponto_ref", f"Ponto {i+1}"))
            
            st.markdown("---")
            st.markdown("### 🦠 Indicadores Microbiológicos Avançados")
            col1, col2 = st.columns(2)
            with col1:
                enterococos = st.number_input(f"Enterococos (NMP/100mL)", key=f"ent_{i}", value=int(st.session_state.analises_avancadas_temp[i].get("enterococos", 0)), step=10)
                cianobacterias = st.number_input(f"Cianobactérias (cel/mL)", key=f"cia_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cianobacterias", 0)), step=100.0, format="%.0f")
            with col2:
                toxicidade_aguda = st.selectbox(f"Toxicidade Aguda", ["Não analisado", "Não detectada", "Detectada"], key=f"toxag_{i}")
                toxicidade_cronica = st.selectbox(f"Toxicidade Crônica", ["Não analisado", "Não detectada", "Detectada"], key=f"toxc_{i}")
            
            st.markdown("---")
            st.markdown("### 🔬 Metais Pesados e Tóxicos")
            col3, col4 = st.columns(2)
            with col3:
                ferro = st.number_input(f"Ferro Total (mg/L)", key=f"fe_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("ferro", 0.3)), step=0.1, format="%.3f")
                manganes = st.number_input(f"Manganês (mg/L)", key=f"mn_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("manganes", 0.1)), step=0.05, format="%.3f")
                aluminio = st.number_input(f"Alumínio (mg/L)", key=f"al_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("aluminio", 0.1)), step=0.05, format="%.3f")
                zinco = st.number_input(f"Zinco (mg/L)", key=f"zn_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("zinco", 0.05)), step=0.01, format="%.3f")
                cobre = st.number_input(f"Cobre (mg/L)", key=f"cu_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cobre", 0.01)), step=0.01, format="%.3f")
            with col4:
                chumbo = st.number_input(f"Chumbo (mg/L)", key=f"pb_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("chumbo", 0.001)), step=0.001, format="%.4f")
                cadmio = st.number_input(f"Cádmio (mg/L)", key=f"cd_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cadmio", 0.0005)), step=0.0005, format="%.4f")
                mercurio = st.number_input(f"Mercúrio (mg/L)", key=f"hg_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("mercurio", 0.0001)), step=0.0001, format="%.4f")
                arsenio = st.number_input(f"Arsênio (mg/L)", key=f"as_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("arsenio", 0.001)), step=0.001, format="%.4f")
                cromo = st.number_input(f"Cromo Total (mg/L)", key=f"cr_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cromo", 0.01)), step=0.01, format="%.3f")
            
            st.markdown("---")
            st.markdown("### 🧪 Ânions e Outros Parâmetros")
            col5, col6 = st.columns(2)
            with col5:
                sulfatos = st.number_input(f"Sulfatos (mg/L)", key=f"sulf_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("sulfatos", 50.0)), step=10.0, format="%.1f")
                fluoreto = st.number_input(f"Fluoreto (mg/L)", key=f"flu_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("fluoreto", 0.5)), step=0.1, format="%.2f")
                cianeto = st.number_input(f"Cianeto (mg/L)", key=f"cn_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("cianeto", 0.0)), step=0.01, format="%.3f")
            with col6:
                fenois = st.number_input(f"Fenóis (mg/L)", key=f"fen_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("fenois", 0.0)), step=0.001, format="%.4f")
                benzeno = st.number_input(f"Benzeno (µg/L)", key=f"benz_{i}", value=float(st.session_state.analises_avancadas_temp[i].get("benzeno", 0.0)), step=1.0, format="%.1f")
                pesticidas = st.text_input(f"Pesticidas (especificar)", key=f"pest_{i}", value=st.session_state.analises_avancadas_temp[i].get("pesticidas", "Não detectado"))
            
            st.session_state.analises_avancadas_temp[i] = {
                "ponto_ref": ponto_ref,
                "enterococos": enterococos, "cianobacterias": cianobacterias,
                "toxicidade_aguda": toxicidade_aguda, "toxicidade_cronica": toxicidade_cronica,
                "ferro": ferro, "manganes": manganes, "aluminio": aluminio,
                "zinco": zinco, "cobre": cobre, "chumbo": chumbo,
                "cadmio": cadmio, "mercurio": mercurio, "arsenio": arsenio, "cromo": cromo,
                "sulfatos": sulfatos, "fluoreto": fluoreto, "cianeto": cianeto,
                "fenois": fenois, "benzeno": benzeno, "pesticidas": pesticidas
            }
    
    col_b1, col_b2 = st.columns(2)
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
        st.success(f"✅ {len(st.session_state.analises_avancadas_temp)} ponto(s) de análise avançada salvos com sucesso!")
        st.info("📌 Estes dados complementares ajudam na avaliação detalhada da qualidade da água.")


# ============================================================
# ABA 4 - LEVANTAMENTO AMBIENTAL
# ============================================================

def aba_levantamento():
    st.header("🌍 4. Levantamento de Causas Ambientais")
    st.caption("Identifique as características da bacia hidrográfica e possíveis fontes de poluição.")
    
    cad = st.session_state.dados_app.get("cadastro", {})
    lat = cad.get("fazenda_lat", -15.0)
    lon = cad.get("fazenda_lon", -45.0)
    
    lev = st.session_state.dados_app.get("levantamento", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏞️ Características da Bacia")
        cobertura_solo = st.selectbox("Cobertura do solo predominante", 
                                      ["Florestada", "Pastagem", "Agricultura", "Urbana", "Área degradada", "Mista"],
                                      index=["Florestada", "Pastagem", "Agricultura", "Urbana", "Área degradada", "Mista"].index(lev.get("cobertura_solo", "Florestada")))
        
        tipo_solo = st.selectbox("Tipo de solo predominante",
                                 ["Argiloso", "Arenoso", "Siltoso", "Orgânico", "Latossolo", "Outro"],
                                 index=["Argiloso", "Arenoso", "Siltoso", "Orgânico", "Latossolo", "Outro"].index(lev.get("tipo_solo", "Argiloso")))
        
        relevo = st.selectbox("Relevo da região",
                              ["Plano", "Suave ondulado", "Ondulado", "Fortemente ondulado", "Montanhoso"],
                              index=["Plano", "Suave ondulado", "Ondulado", "Fortemente ondulado", "Montanhoso"].index(lev.get("relevo", "Plano")))
    
    with col2:
        st.subheader("⚠️ Atividades e Impactos")
        uso_ocupacao = st.multiselect("Uso e ocupação do solo na bacia",
                                      ["Desmatamento", "Urbanização", "Pastagem extensiva", "Agricultura intensiva", "Mineração", "Silvicultura"],
                                      default=lev.get("uso_ocupacao", []))
        
        fontes_poluicao = st.multiselect("Fontes de poluição/degradação identificadas",
                                         ["Esgoto doméstico", "Efluente industrial", "Agrotóxicos/fertilizantes", "Resíduos sólidos", "Mineração", "Dragagem", "Queimadas", "Assoreamento"],
                                         default=lev.get("fontes_poluicao", []))
        
        alteracoes = st.multiselect("Alterações no regime hidrológico",
                                   ["Barragens", "Retirada de mata ciliar", "Canalização", "Drenagem de várzeas"],
                                   default=lev.get("alteracoes", []))
    
    st.subheader("📝 Informações Complementares")
    eventos_extremos = st.selectbox("Ocorrência de eventos extremos recentes",
                                   ["Não", "Enxurradas", "Secas prolongadas", "Queimadas", "Ventos fortes"],
                                   index=["Não", "Enxurradas", "Secas prolongadas", "Queimadas", "Ventos fortes"].index(lev.get("eventos_extremos", "Não")))
    
    observacoes = st.text_area("Observações adicionais (ex: afloramento rochoso com metais, histórico de contaminação)", 
                               value=lev.get("observacoes", ""), height=100)
    
    # Estimativa de relevo por coordenadas
    if lat and lon and lat != -15.0:
        with st.expander("📍 Estimativa de Relevo por Coordenadas (API OpenTopoData)"):
            with st.spinner("Consultando API de elevação..."):
                relevo_estimado, elevacao = estimar_relevo_por_coordenadas(lat, lon)
                if elevacao:
                    st.success(f"**Elevação estimada:** {elevacao:.1f} metros")
                    st.info(f"**Relevo estimado:** {relevo_estimado}")
                    st.caption("💡 Esta estimativa usa a API gratuita OpenTopoData (SRTM 90m).")
                else:
                    st.warning("Não foi possível estimar o relevo. Verifique sua conexão com a internet.")
    
    st.divider()
    if st.button("💾 Salvar Levantamento Ambiental", type="primary"):
        st.session_state.dados_app["levantamento"] = {
            "cobertura_solo": cobertura_solo, "tipo_solo": tipo_solo, "relevo": relevo,
            "uso_ocupacao": uso_ocupacao, "fontes_poluicao": fontes_poluicao,
            "alteracoes": alteracoes, "eventos_extremos": eventos_extremos,
            "observacoes": observacoes
        }
        st.success("✅ Levantamento ambiental salvo com sucesso!")
        st.info("📌 Estas informações serão usadas para gerar recomendações de manejo personalizadas.")


# ============================================================
# ABA 5 - RELATÓRIO DE CLASSIFICAÇÃO
# ============================================================

def aba_relatorio():
    st.header("📊 5. Relatório de Classificação da Qualidade da Água")
    st.caption("Análise baseada na Resolução CONAMA 357/2005")
    
    analises = st.session_state.dados_app.get("analises", [])
    analises_avancadas = st.session_state.dados_app.get("analises_avancadas", [])
    cad = st.session_state.dados_app.get("cadastro", {})
    lev = st.session_state.dados_app.get("levantamento", {})
    
    if not analises:
        st.warning("⚠️ Nenhuma análise cadastrada. Vá até a aba 'Análises Básicas' e cadastre os pontos de coleta.")
        return
    
    # Cabeçalho do relatório
    st.subheader(f"📌 Relatório do Trecho Monitorado")
    st.markdown(f"**Corpo Hídrico:** {cad.get('corpo_nome', 'Não informado')} | **Fazenda:** {cad.get('fazenda_nome', 'Não informada')}")
    st.markdown(f"**Data do relatório:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Resumo dos pontos
    st.subheader("📋 Classificação por Ponto de Coleta")
    
    classificacoes = []
    for i, ponto in enumerate(analises):
        classe, cor, recomendacoes, params_preenchidos, violacoes = classificar_ponto_basico(ponto)
        classificacoes.append(classe)
        
        with st.expander(f"{cor} {ponto.get('nome', f'Ponto {i+1}')} - {classe}", expanded=(i == 0)):
            col_metric1, col_metric2, col_metric3 = st.columns(3)
            with col_metric1:
                st.metric("Parâmetros medidos", len(params_preenchidos))
            with col_metric2:
                st.metric("Data da coleta", ponto.get("data", "N/A"))
            with col_metric3:
                st.metric("Classificação", classe)
            
            if classe == "Dados insuficientes":
                st.warning(f"⚠️ {recomendacoes[0]}")
                st.info("💡 Adicione pelo menos 3 parâmetros (ex: OD, pH, DBO, Coliformes) para uma classificação confiável.")
            else:
                st.success(f"**Classificação:** {classe} {cor}")
                for rec in recomendacoes[:2]:
                    st.info(f"📌 {rec}")
                
                if violacoes:
                    st.warning("**⚠️ Parâmetros fora do padrão:**")
                    for v in violacoes[:4]:
                        st.write(f"- {v}")
            
            # Mostrar valores medidos
            st.markdown("**📊 Valores medidos no ponto:**")
            valores = {k: v for k, v in ponto.items() if v not in [None, "", 0] and k not in ['nome', 'lat', 'lon', 'data']}
            if valores:
                df_valores = pd.DataFrame(list(valores.items()), columns=["Parâmetro", "Valor"])
                st.dataframe(df_valores, use_container_width=True, hide_index=True)
    
    # Análises avançadas
    if analises_avancadas:
        st.subheader("🔬 Análises Avançadas")
        for i, avancada in enumerate(analises_avancadas):
            status, cor, alertas = classificar_ponto_avancado(avancada)
            with st.expander(f"{cor} {avancada.get('ponto_ref', f'Ponto {i+1}')} - {status}"):
                if alertas:
                    for alerta in alertas[:5]:
                        if "Dentro dos padrões" in alerta:
                            st.success(alerta)
                        else:
                            st.warning(alerta)
    
    # Avaliação geral do trecho
    st.subheader("📊 Avaliação Geral do Trecho")
    
    if classificacoes:
        classes_ordem = {"Classe 1": 1, "Classe 2": 2, "Classe 3": 3, "Classe 4": 4, "Dados insuficientes": 5}
        pior_classe = max(classificacoes, key=lambda x: classes_ordem.get(x, 5))
        
        if pior_classe == "Classe 1":
            status_geral = "Excelente"
            cor_geral = "🟢"
            cor_bg = "#d4edda"
        elif pior_classe == "Classe 2":
            status_geral = "Boa"
            cor_geral = "🟡"
            cor_bg = "#fff3cd"
        elif pior_classe == "Classe 3":
            status_geral = "Regular"
            cor_geral = "🟠"
            cor_bg = "#ffe5b4"
        elif pior_classe == "Classe 4":
            status_geral = "Ruim"
            cor_geral = "🔴"
            cor_bg = "#f8d7da"
        else:
            status_geral = "Não classificável"
            cor_geral = "⚪"
            cor_bg = "#e9ecef"
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown(f"""
            <div style='text-align: center; background-color: {cor_bg}; padding: 20px; border-radius: 10px;'>
                <h1>{cor_geral} {status_geral}</h1>
                <p><b>Classificação geral do trecho baseada no pior ponto</b></p>
            </div>
            """, unsafe_allow_html=True)
    
    # Base legal
    with st.expander("📜 Base Legal Utilizada (Resolução CONAMA 357/2005)"):
        st.markdown("""
        **Classificação das águas doces segundo a Resolução CONAMA nº 357/2005:**
        
        | Classe | OD (mg/L) | DBO (mg/L) | pH | E. coli (NMP/100mL) | Turbidez (NTU) |
        |--------|-----------|------------|-----|---------------------|----------------|
        | **Classe 1** | ≥ 6 | ≤ 3 | 6-9 | ≤ 200 | ≤ 10 |
        | **Classe 2** | ≥ 5 | ≤ 5 | 6-9 | ≤ 1000 | ≤ 40 |
        | **Classe 3** | ≥ 4 | ≤ 10 | 6-9 | ≤ 4000 | ≤ 100 |
        | **Classe 4** | ≥ 2 | - | 6-9 | - | - |
        
        **Outras normas aplicáveis:**
        - Lei 9.433/1997 - Política Nacional de Recursos Hídricos
        - Portaria GM/MS 888/2021 - Potabilidade da água para consumo humano
        - Lei 11.445/2007 - Diretrizes Nacionais para Saneamento Básico
        - Lei 6.938/1981 - Política Nacional do Meio Ambiente
        - Decreto 8.468/1976 - Padrões de emissão (São Paulo)
        """)


# ============================================================
# ABA 6 - MANEJOS E USOS POSSÍVEIS
# ============================================================

def aba_manejos():
    st.header("🌱 6. Possíveis Manejos e Usos da Água")
    st.caption("Recomendações baseadas na classificação da qualidade da água e nas características da bacia.")
    
    analises = st.session_state.dados_app.get("analises", [])
    levantamento = st.session_state.dados_app.get("levantamento", {})
    
    if not analises:
        st.warning("⚠️ Nenhuma análise cadastrada. Vá até a aba 'Análises Básicas' e cadastre os pontos de coleta.")
        return
    
    # Classificar pontos para base das recomendações
    classificacoes = []
    for ponto in analises:
        classe, _, _, _, _ = classificar_ponto_basico(ponto)
        classificacoes.append(classe)
    
    pior_classe = "Classe 1"
    classes_ordem = {"Classe 1": 1, "Classe 2": 2, "Classe 3": 3, "Classe 4": 4}
    for c in classificacoes:
        if c in classes_ordem and classes_ordem.get(c, 1) > classes_ordem.get(pior_classe, 1):
            pior_classe = c
    
    # Gerar recomendações
    recomendacoes = gerar_recomendacoes_manejo(levantamento, pior_classe, analises)
    
    st.subheader("🛠️ Recomendações de Manejo para Melhoria da Qualidade")
    
    for rec in recomendacoes:
        with st.container():
            if rec["prioridade"] == "Muito Alta":
                st.error(f"🔴 **{rec['titulo']}** (Prioridade: {rec['prioridade']})")
            elif rec["prioridade"] == "Alta":
                st.warning(f"🟠 **{rec['titulo']}** (Prioridade: {rec['prioridade']})")
            else:
                st.info(f"🟢 **{rec['titulo']}** (Prioridade: {rec['prioridade']})")
            st.write(rec["descricao"])
            st.markdown("---")
    
    st.divider()
    
    # Usos possíveis da água
    st.subheader("💧 Usos Possíveis da Água por Classe")
    
    usos_por_classe = {
        "Classe 1": [
            "✅ **Abastecimento doméstico** - Após desinfecção simples",
            "✅ **Proteção da vida aquática** - Preservação de ecossistemas",
            "✅ **Irrigação** - De hortaliças e plantas frutíferas",
            "✅ **Recreação** - Contato primário (natação, mergulho)",
            "✅ **Aquicultura** - Criação de organismos aquáticos"
        ],
        "Classe 2": [
            "✅ **Abastecimento doméstico** - Após tratamento convencional",
            "✅ **Proteção da vida aquática** - Moderada",
            "✅ **Irrigação** - De hortaliças com cautela",
            "✅ **Recreação** - Contato primário (com cuidados)",
            "✅ **Pecuária** - Dessedentação de animais"
        ],
        "Classe 3": [
            "⚠️ **Abastecimento doméstico** - Após tratamento convencional avançado",
            "✅ **Irrigação** - De culturas arbóreas e forrageiras",
            "✅ **Dessedentação de animais**",
            "✅ **Recreação** - Contato secundário (remo, pesca)",
            "❌ **Natação** - Não recomendado"
        ],
        "Classe 4": [
            "✅ **Navegação**",
            "✅ **Harmonia paisagística**",
            "❌ **Abastecimento humano** - Direto ou indireto",
            "❌ **Irrigação** - De hortaliças ou plantas de consumo",
            "❌ **Contato primário** - Recreação"
        ],
        "Dados insuficientes": [
            "❓ **Não é possível determinar usos** - Adicione mais parâmetros para classificação"
        ]
    }
    
    usos = usos_por_classe.get(pior_classe, usos_por_classe["Classe 4"])
    st.markdown(f"**Com base na classificação geral do trecho ({pior_classe}):**")
    for uso in usos:
        st.write(uso)
    
    # Sugestão de tratamento por classe
    st.divider()
    st.subheader("🧪 Sugestões de Tratamento por Classe")
    
    tratamentos = {
        "Classe 1": "🟢 **Desinfecção simples** (cloração, ozônio ou UV) - Água de excelente qualidade.",
        "Classe 2": "🟡 **Tratamento convencional** (coagulação, floculação, decantação, filtração e desinfecção).",
        "Classe 3": "🟠 **Tratamento avançado** (convencional + carvão ativado ou membranas).",
        "Classe 4": "🔴 **Não recomendado para consumo humano** - Necessita remediação da fonte."
    }
    
    st.info(tratamentos.get(pior_classe, tratamentos["Classe 4"]))


# ============================================================
# ABA 7 - MAPA DE LOCALIZAÇÃO
# ============================================================

def aba_mapa():
    st.header("🗺️ 7. Mapa de Localização")
    st.caption("Visualize a localização da fazenda, corpo hídrico e pontos de coleta.")
    
    cad = st.session_state.dados_app.get("cadastro", {})
    analises = st.session_state.dados_app.get("analises", [])
    
    lat = cad.get("fazenda_lat", -15.0)
    lon = cad.get("fazenda_lon", -45.0)
    fazenda_nome = cad.get("fazenda_nome", "Fazenda")
    corpo_nome = cad.get("corpo_nome", "Corpo Hídrico")
    
    if lat == -15.0 and lon == -45.0:
        st.warning("⚠️ Configure as coordenadas da fazenda na aba 'Cadastro' para visualizar o mapa.")
        return
    
    # Informação sobre APIs
    if not CHAVE_API_GOOGLE:
        st.info("ℹ️ **Mapa usando OpenStreetMap.** Para usar Google Maps, insira sua chave na variável `CHAVE_API_GOOGLE` no início do código.")
    
    # Criar mapa
    m = folium.Map(location=[lat, lon], zoom_start=13, control_scale=True)
    
    # Marcador da Fazenda
    folium.Marker(
        [lat, lon],
        popup=f"🏠 <b>{fazenda_nome}</b><br>📍 Propriedade rural",
        icon=folium.Icon(color="green", icon="home", prefix='fa'),
        tooltip="Clique para detalhes"
    ).add_to(m)
    
    # Marcador do Corpo Hídrico
    folium.Marker(
        [lat + 0.002, lon + 0.003],
        popup=f"💧 <b>{corpo_nome}</b><br>🌊 Corpo hídrico monitorado",
        icon=folium.Icon(color="blue", icon="tint", prefix='fa'),
        tooltip="Corpo hídrico"
    ).add_to(m)
    
    # Pontos de coleta
    pontos_no_mapa = 0
    for ponto in analises:
        p_lat = ponto.get("lat")
        p_lon = ponto.get("lon")
        if p_lat and p_lon and p_lat != -15.0:
            classe, cor, _, _, _ = classificar_ponto_basico(ponto)
            cor_icon = "darkgreen" if "Classe 1" in classe else "orange" if "Classe 2" in classe else "red" if "Classe 3" in classe else "gray"
            
            popup_text = f"""
            <div style="min-width: 200px;">
                <b>📌 {ponto.get('nome', 'Ponto')}</b><br>
                📅 {ponto.get('data', 'N/A')}<br>
                🏷️ {classe}<br>
                ━━━━━━━━━━━━━━━━━<br>
                📊 Principais parâmetros:<br>
                • OD: {ponto.get('od', 'N/A')} mg/L<br>
                • pH: {ponto.get('ph', 'N/A')}<br>
                • DBO: {ponto.get('dbo', 'N/A')} mg/L<br>
                • E. coli: {ponto.get('coliformes', 'N/A')} NMP/100mL
            </div>
            """
            
            folium.Marker(
                [p_lat, p_lon],
                popup=folium.Popup(popup_text, max_width=300),
                icon=folium.Icon(color=cor_icon, icon="water", prefix='fa'),
                tooltip=f"{ponto.get('nome')} - {classe}"
            ).add_to(m)
            pontos_no_mapa += 1
    
    # Adicionar Google Maps se tiver chave
    if CHAVE_API_GOOGLE and CHAVE_API_GOOGLE.strip():
        try:
            folium.TileLayer(
                f"https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}&key={CHAVE_API_GOOGLE}",
                attr="Google Maps",
                name="Google Maps - Mapa",
                control=True
            ).add_to(m)
            folium.TileLayer(
                f"https://mt1.google.com/vt/lyrs=s&x={{x}}&y={{y}}&z={{z}}&key={CHAVE_API_GOOGLE}",
                attr="Google Satélite",
                name="Google Maps - Satélite",
                control=True
            ).add_to(m)
        except Exception:
            pass
    
    folium.LayerControl().add_to(m)
    st_folium(m, width=900, height=500)
    
    # Estatísticas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📍 Pontos de Coleta", len(analises))
    with col2:
        st.metric("🗺️ Pontos no Mapa", pontos_no_mapa)
    with col3:
        st.metric("🏠 Fazenda", fazenda_nome[:20] if fazenda_nome else "N/A")
    with col4:
        st.metric("💧 Corpo Hídrico", corpo_nome[:20] if corpo_nome else "N/A")
    
    if pontos_no_mapa < len(analises):
        st.warning(f"⚠️ {len(analises) - pontos_no_mapa} ponto(s) não possuem coordenadas válidas e não foram exibidos no mapa.")
    
    # Tabela de coordenadas
    if analises:
        with st.expander("📋 Tabela de Coordenadas dos Pontos de Coleta"):
            df_pontos = pd.DataFrame([{
                "Ponto": p.get("nome", f"P{i+1}"),
                "Latitude": p.get("lat", "N/A"),
                "Longitude": p.get("lon", "N/A"),
                "Data": p.get("data", "N/A")
            } for i, p in enumerate(analises) if p.get("lat") and p.get("lat") != -15.0])
            if not df_pontos.empty:
                st.dataframe(df_pontos, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum ponto com coordenadas válidas.")


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def main():
    st.sidebar.title("💧 Sistema de Qualidade da Água")
    st.sidebar.markdown("---")
    
    # Informação da chave API
    if not CHAVE_API_GOOGLE:
        st.sidebar.info("🔑 **Chave Google Maps não configurada**\n\nO mapa usará OpenStreetMap (gratuito). Para usar Google Maps, insira sua chave na variável `CHAVE_API_GOOGLE`.")
    else:
        st.sidebar.success("✅ Google Maps configurado!")
    
    # Verificar cadastro para liberar abas
    if not st.session_state.cadastro_completo:
        st.sidebar.warning("⚠️ **Complete o cadastro primeiro!**")
        st.sidebar.caption("Preencha todos os campos com * na aba **Cadastro** para liberar as demais funcionalidades.")
        abas_disponiveis = ["📋 Cadastro"]
    else:
        st.sidebar.success("✅ Cadastro completo!")
        abas_disponiveis = ["📋 Cadastro", "🧪 Análises Básicas", "🔬 Análises Avançadas", "🌍 Levantamento", "📊 Relatório", "🌱 Manejos e Usos", "🗺️ Mapa"]
    
    # Menu de navegação
    aba_selecionada = st.sidebar.radio("📌 Navegação", abas_disponiveis)
    
    # Chamar a aba selecionada
    if aba_selecionada == "📋 Cadastro":
        aba_cadastro()
    elif aba_selecionada == "🧪 Análises Básicas":
        aba_analises()
    elif aba_selecionada == "🔬 Análises Avançadas":
        aba_analises_avancadas()
    elif aba_selecionada == "🌍 Levantamento":
        aba_levantamento()
    elif aba_selecionada == "📊 Relatório":
        aba_relatorio()
    elif aba_selecionada == "🌱 Manejos e Usos":
        aba_manejos()
    elif aba_selecionada == "🗺️ Mapa":
        aba_mapa()
    
    # Rodapé da barra lateral
    st.sidebar.markdown("---")
    st.sidebar.caption("📜 **Legislação aplicável:**")
    st.sidebar.caption("- CONAMA 357/2005")
    st.sidebar.caption("- Portaria 888/2021")
    st.sidebar.caption("- Lei 9.433/1997")
    st.sidebar.caption("- Lei 11.445/2007")
    
    # Botão para limpar dados
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ Limpar todos os dados", type="secondary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    # Status dos dados
    st.sidebar.markdown("---")
    st.sidebar.caption("📊 **Status dos dados:**")
    analises_count = len(st.session_state.dados_app.get("analises", []))
    st.sidebar.caption(f"- Pontos de coleta: {analises_count}")
    if st.session_state.dados_app.get("levantamento", {}):
        st.sidebar.caption("- Levantamento: ✅ Salvo")
    else:
        st.sidebar.caption("- Levantamento: ⚠️ Pendente")
    
    # Versão
    st.sidebar.markdown("---")
    st.sidebar.caption("🔄 Versão 2.0 | Dados salvos na sessão")


if __name__ == "__main__":
    main()
