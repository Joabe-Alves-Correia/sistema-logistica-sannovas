import os
import gradio as gr
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# 1. Conexão Segura com o Supabase
DEFAULT_DB_URL = "postgresql+psycopg2://postgres.hbwzwbgmgkbebxqzzboo:Sannovaslog2026@aws-1-us-west-2.pooler.supabase.com:6543/postgres"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)

engine = create_engine(DATABASE_URL)

# 2. Configuração de Credenciais de Acesso (Login / Senha)
USUARIO_ADMIN = os.environ.get("APP_USER", "admin")
SENHA_ADMIN = os.environ.get("APP_PASS", "Sannovas2026!")

# 3. Inicialização e Migração do Banco de Dados
with engine.begin() as conn:
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS cargas (
            id SERIAL PRIMARY KEY,
            data TEXT,
            motorista TEXT,
            pacotes INTEGER,
            status TEXT DEFAULT 'Ativo'
        )
    '''))
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS entregas (
            id SERIAL PRIMARY KEY,
            data TEXT,
            motorista TEXT,
            bairro TEXT,
            pacotes INTEGER,
            valor_pacote REAL,
            total REAL,
            status TEXT DEFAULT 'Ativo'
        )
    '''))
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS devolucoes (
            id SERIAL PRIMARY KEY,
            data TEXT,
            motorista TEXT,
            bairro TEXT,
            pacotes INTEGER,
            motivo TEXT,
            status TEXT DEFAULT 'Ativo'
        )
    '''))
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS motoristas (
            id SERIAL PRIMARY KEY,
            nome TEXT,
            chave_pix TEXT,
            telefone TEXT
        )
    '''))
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS bairros (
            id SERIAL PRIMARY KEY,
            nome TEXT UNIQUE
        )
    '''))
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS financeiro (
            id SERIAL PRIMARY KEY,
            data TEXT,
            descricao TEXT,
            tipo TEXT,
            valor REAL
        )
    '''))
    conn.execute(text("ALTER TABLE entregas ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Ativo';"))
    conn.execute(text("ALTER TABLE devolucoes ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Ativo';"))
    conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Ativo';"))

# 4. Funções Auxiliares, KPIs e Gráficos
def carregar_tabela(nome_tabela):
    return pd.read_sql_query(f"SELECT * FROM {nome_tabela} ORDER BY id DESC", engine)

def listar_motoristas():
    try:
        df = pd.read_sql_query("SELECT nome FROM motoristas ORDER BY nome ASC", engine)
        nomes = df['nome'].dropna().unique().tolist()
        return nomes if nomes else ["Nenhum motorista cadastrado"]
    except:
        return ["Nenhum motorista cadastrado"]

def listar_bairros():
    try:
        df = pd.read_sql_query("SELECT nome FROM bairros ORDER BY nome ASC", engine)
        nomes = df['nome'].dropna().unique().tolist()
        return nomes if nomes else ["Nenhum bairro cadastrado"]
    except:
        return ["Nenhum bairro cadastrado"]

def calcular_kpis():
    df_cargas = carregar_tabela('cargas')
    df_entregas = carregar_tabela('entregas')
    df_devolucoes = carregar_tabela('devolucoes')
    df_fin = carregar_tabela('financeiro')
    
    if not df_cargas.empty and 'status' in df_cargas.columns:
        df_cargas = df_cargas[df_cargas['status'] != 'Cancelado']
    if not df_entregas.empty and 'status' in df_entregas.columns:
        df_entregas = df_entregas[df_entregas['status'] != 'Cancelado']
    if not df_devolucoes.empty and 'status' in df_devolucoes.columns:
        df_devolucoes = df_devolucoes[df_devolucoes['status'] != 'Cancelado']
    
    total_saida = int(df_cargas['pacotes'].sum()) if not df_cargas.empty else 0
    total_entregue = int(df_entregas['pacotes'].sum()) if not df_entregas.empty else 0
    total_devolvido = int(df_devolucoes['pacotes'].sum()) if not df_devolucoes.empty else 0
    total_repasse = float(df_entregas['total'].sum()) if not df_entregas.empty else 0.0
    
    entradas = float(df_fin[df_fin['tipo'] == 'Entrada']['valor'].sum()) if not df_fin.empty else 0.0
    saidas = float(df_fin[df_fin['tipo'] == 'Saída']['valor'].sum()) if not df_fin.empty else 0.0
    saldo = entradas - saidas
    
    kpi_texto = f"""
    ### 📊 Indicadores Gerais
    * **Carga Total Saída (Romaneios):** {total_saida} pacotes
    * **Total Entregue:** {total_entregue} pacotes | **Total Devolvido:** {total_devolvido} pacotes
    * **Total em Repasses:** R$ {total_repasse:.2f}
    * **Saldo de Caixa (Entradas - Saídas):** R$ {saldo:.2f}
    """
    return kpi_texto

def gerar_grafico_bairros():
    try:
        df = carregar_tabela('entregas')
        if df.empty or 'status' not in df.columns:
            return pd.DataFrame({'bairro': [], 'pacotes': []})
        df_ativa = df[df['status'] != 'Cancelado']
        if df_ativa.empty:
            return pd.DataFrame({'bairro': [], 'pacotes': []})
        return df_ativa.groupby('bairro', as_index=False)['pacotes'].sum()
    except:
        return pd.DataFrame({'bairro': [], 'pacotes': []})

def obter_data_hoje():
    return datetime.now().strftime("%d/%m/%Y")

def obter_mes_atual():
    return datetime.now().strftime("/%m/%Y")

# 5. Operações de Banco de Dados
def registrar_carga(data, motorista, pacotes):
    if not motorista or motorista == "Nenhum motorista cadastrado":
        return carregar_tabela('cargas'), "❌ Selecione um motorista válido!", calcular_kpis()
    if not data:
        data = obter_data_hoje()
        
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO cargas (data, motorista, pacotes, status)
            VALUES (:data, :mot, :pac, 'Ativo')
        '''), {"data": data, "mot": motorista, "pac": int(pacotes)})
        
    return carregar_tabela('cargas'), f"✅ Saída de {pacotes} pacotes registrada para {motorista}!", calcular_kpis()

def registrar_entrega(data, motorista, bairro, pacotes, valor_pacote):
    if not motorista or motorista == "Nenhum motorista cadastrado":
        return carregar_tabela('entregas'), "❌ Selecione ou cadastre um motorista válido!", calcular_kpis(), gerar_grafico_bairros()
        
    if not bairro or bairro == "Nenhum bairro cadastrado":
        return carregar_tabela('entregas'), "❌ Selecione ou cadastre um bairro válido!", calcular_kpis(), gerar_grafico_bairros()

    if not data:
        data = obter_data_hoje()
    total = pacotes * valor_pacote
    
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO entregas (data, motorista, bairro, pacotes, valor_pacote, total, status)
            VALUES (:data, :mot, :bai, :pac, :val, :tot, 'Ativo')
        '''), {"data": data, "mot": motorista, "bai": bairro, "pac": pacotes, "val": valor_pacote, "tot": total})
    
    return carregar_tabela('entregas'), f"✅ Salvo! Total Repasse: R$ {total:.2f}", calcular_kpis(), gerar_grafico_bairros()

def registrar_devolucao(data, motorista, bairro, pacotes, motivo):
    if not motorista or motorista == "Nenhum motorista cadastrado":
        return carregar_tabela('devolucoes'), "❌ Selecione ou cadastre um motorista válido!", calcular_kpis()
        
    if not bairro or bairro == "Nenhum bairro cadastrado":
        return carregar_tabela('devolucoes'), "❌ Selecione ou cadastre um bairro válido!", calcular_kpis()

    if not data:
        data = obter_data_hoje()
    
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO devolucoes (data, motorista, bairro, pacotes, motivo, status)
            VALUES (:data, :mot, :bai, :pac, :motivo, 'Ativo')
        '''), {"data": data, "mot": motorista, "bai": bairro, "pac": pacotes, "motivo": motivo})
    
    return carregar_tabela('devolucoes'), f"✅ Devolução registrada ({pacotes} pacotes)!", calcular_kpis()

def cadastrar_motorista(nome, pix, telefone):
    if not nome:
        return carregar_tabela('motoristas'), "❌ Informe o nome do motorista!", gr.update(), gr.update(), gr.update(), gr.update()
        
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO motoristas (nome, chave_pix, telefone)
            VALUES (:nome, :pix, :tel)
        '''), {"nome": nome, "pix": pix, "tel": telefone})
    
    novos_motoristas = listar_motoristas()
    return carregar_tabela('motoristas'), "✅ Motorista cadastrado com sucesso!", gr.update(choices=novos_motoristas), gr.update(choices=novos_motoristas), gr.update(choices=novos_motoristas), gr.update(choices=["Todos"] + novos_motoristas)

def cadastrar_bairro(nome):
    if not nome:
        return carregar_tabela('bairros'), "❌ Informe o nome do bairro!", gr.update(), gr.update(), gr.update()
        
    nome_limpo = nome.strip()
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO bairros (nome) VALUES (:nome)
            ON CONFLICT (nome) DO NOTHING
        '''), {"nome": nome_limpo})
    
    novos_bairros = listar_bairros()
    return carregar_tabela('bairros'), "✅ Bairro cadastrado com sucesso!", gr.update(choices=novos_bairros), gr.update(choices=novos_bairros), gr.update(choices=["Todos"] + novos_bairros)

def registrar_financeiro(descricao, tipo, valor):
    data = obter_data_hoje()
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO financeiro (data, descricao, tipo, valor)
            VALUES (:data, :desc, :tipo, :val)
        '''), {"data": data, "desc": descricao, "tipo": tipo, "val": valor})
    
    return carregar_tabela('financeiro'), "✅ Lançamento salvo!", calcular_kpis()

def cancelar_carga(id_registro):
    if not id_registro:
        return carregar_tabela('cargas'), "❌ Informe o ID!", calcular_kpis()
    with engine.begin() as conn:
        conn.execute(text("UPDATE cargas SET status = 'Cancelado' WHERE id = :id"), {"id": int(id_registro)})
    return carregar_tabela('cargas'), f"⚠️ Carga #{id_registro} marcada como Cancelada.", calcular_kpis()

def cancelar_registro(id_registro):
    if not id_registro:
        return carregar_tabela('entregas'), "❌ Informe o ID da entrega!", calcular_kpis(), gerar_grafico_bairros()
    with engine.begin() as conn:
        conn.execute(text("UPDATE entregas SET status = 'Cancelado' WHERE id = :id"), {"id": int(id_registro)})
    return carregar_tabela('entregas'), f"⚠️ Registro #{id_registro} marcado como Cancelado.", calcular_kpis(), gerar_grafico_bairros()

def cancelar_devolucao(id_registro):
    if not id_registro:
        return carregar_tabela('devolucoes'), "❌ Informe o ID da devolução!", calcular_kpis()
    with engine.begin() as conn:
        conn.execute(text("UPDATE devolucoes SET status = 'Cancelado' WHERE id = :id"), {"id": int(id_registro)})
    return carregar_tabela('devolucoes'), f"⚠️ Devolução #{id_registro} marcada como Cancelada.", calcular_kpis()

def filtrar_dados(motorista_filtro, bairro_filtro, data_filtro):
    query = "SELECT * FROM entregas WHERE status != 'Cancelado'"
    params = {}
    
    if motorista_filtro and motorista_filtro != "Todos":
        query += " AND motorista ILIKE :mot" 
        params["mot"] = f"%{motorista_filtro}%"
    if bairro_filtro and bairro_filtro != "Todos":
        query += " AND bairro ILIKE :bai"
        params["bai"] = f"%{bairro_filtro}%"
    if data_filtro:
        query += " AND data LIKE :data"
        params["data"] = f"%{data_filtro}%"
        
    df_filtrado = pd.read_sql_query(text(query), engine, params=params)
    
    total_pacotes = df_filtrado["pacotes"].sum() if not df_filtrado.empty else 0
    total_pago = df_filtrado["total"].sum() if not df_filtrado.empty else 0
    
    resumo = f"Filtro Aplicado: {total_pacotes} Pacotes Entregues | Repasse Total: R$ {total_pago:.2f}"
    return df_filtrado, resumo

# 6. Exportação e Fechamento WhatsApp
def exportar_excel(motorista_filtro, bairro_filtro, data_filtro):
    df_filtrado, _ = filtrar_dados(motorista_filtro, bairro_filtro, data_filtro)
    caminho = "relatorio_entregas.xlsx"
    df_filtrado.to_excel(caminho, index=False)
    return caminho

def exportar_csv(motorista_filtro, bairro_filtro, data_filtro):
    df_filtrado, _ = filtrar_dados(motorista_filtro, bairro_filtro, data_filtro)
    caminho = "relatorio_entregas.csv"
    df_filtrado.to_csv(caminho, index=False, encoding="utf-8-sig")
    return caminho

def gerar_comprovante_whatsapp(motorista_nome, data_consulta):
    if not motorista_nome or motorista_nome == "Todos":
        return "Selecione um motorista específico para gerar o fechamento."
    
    if not data_consulta:
        data_consulta = obter_data_hoje()
        
    # Busca Carga Inicial (Saída)
    query_carga = "SELECT pacotes FROM cargas WHERE status != 'Cancelado' AND motorista = :mot AND data LIKE :data"
    df_c = pd.read_sql_query(text(query_carga), engine, params={"mot": motorista_nome, "data": f"%{data_consulta}%"})
    total_saida = df_c['pacotes'].sum() if not df_c.empty else 0

    # Busca Entregas
    df_entregas, _ = filtrar_dados(motorista_nome, "Todos", data_consulta)
    total_entregue = df_entregas['pacotes'].sum() if not df_entregas.empty else 0
    total_repasse = df_entregas['total'].sum() if not df_entregas.empty else 0.0

    # Busca Devoluções
    query_dev = "SELECT pacotes FROM devolucoes WHERE status != 'Cancelado' AND motorista = :mot AND data LIKE :data"
    df_dev = pd.read_sql_query(text(query_dev), engine, params={"mot": motorista_nome, "data": f"%{data_consulta}%"})
    total_devolucoes = df_dev['pacotes'].sum() if not df_dev.empty else 0
    
    # Calcula Pendência/Divergência
    pendentes = total_saida - (total_entregue + total_devolucoes)
    status_balanco = "✅ Fechamento OK" if pendentes == 0 else f"⚠️ Divergência de {pendentes} pacote(s)"
    if total_saida == 0:
        status_balanco = "ℹ️ Carga Inicial não registrada no sistema"

    df_mot = pd.read_sql_query(text("SELECT chave_pix, telefone FROM motoristas WHERE nome = :nome"), engine, params={"nome": motorista_nome})
    chave_pix = df_mot['chave_pix'].iloc[0] if not df_mot.empty else "Não cadastrada"
    
    texto_whatsapp = f"""📲 *FECHAMENTO DE ROTA DE ENTREGA*
👤 *Motorista:* {motorista_nome}
📅 *Data:* {data_consulta}

📦 *Carga Inicial (Saída):* {total_saida} pacotes
✅ *Pacotes Entregues:* {total_entregue} pacotes
🔄 *Pacotes Devolvidos:* {total_devolucoes} pacotes
⚖️ *
