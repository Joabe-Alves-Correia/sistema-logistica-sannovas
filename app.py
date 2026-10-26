import os
import gradio as gr
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# 1. Conexão Segura com o Supabase (Lê do Render ou usa fallback)
DEFAULT_DB_URL = "postgresql+psycopg2://postgres.hbwzwbgmgkbebxqzzboo:Sannovaslog2026@aws-1-us-west-2.pooler.supabase.com:6543/postgres"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)

engine = create_engine(DATABASE_URL)

# 2. Inicialização e Migração do Banco de Dados
with engine.begin() as conn:
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
        CREATE TABLE IF NOT EXISTS motoristas (
            id SERIAL PRIMARY KEY,
            nome TEXT,
            chave_pix TEXT,
            telefone TEXT
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
    # Garante a coluna status em bancos criados anteriormente
    conn.execute(text("ALTER TABLE entregas ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Ativo';"))

# 3. Funções Auxiliares e Métricas (KPIs)
def carregar_tabela(nome_tabela):
    return pd.read_sql_query(f"SELECT * FROM {nome_tabela} ORDER BY id DESC", engine)

def listar_motoristas():
    try:
        df = pd.read_sql_query("SELECT nome FROM motoristas ORDER BY nome ASC", engine)
        nomes = df['nome'].dropna().unique().tolist()
        return nomes if nomes else ["Nenhum motorista cadastrado"]
    except:
        return ["Nenhum motorista cadastrado"]

def calcular_kpis():
    df_entregas = carregar_tabela('entregas')
    df_fin = carregar_tabela('financeiro')
    
    # Filtra entregas ativas
    if not df_entregas.empty and 'status' in df_entregas.columns:
        df_entregas = df_entregas[df_entregas['status'] != 'Cancelado']
    
    total_pacotes = int(df_entregas['pacotes'].sum()) if not df_entregas.empty else 0
    total_repasse = float(df_entregas['total'].sum()) if not df_entregas.empty else 0.0
    
    entradas = float(df_fin[df_fin['tipo'] == 'Entrada']['valor'].sum()) if not df_fin.empty else 0.0
    saidas = float(df_fin[df_fin['tipo'] == 'Saída']['valor'].sum()) if not df_fin.empty else 0.0
    saldo = entradas - saidas
    
    kpi_texto = f"""
    ### 📊 Indicadores Gerais
    * **Total de Pacotes Registrados:** {total_pacotes}
    * **Total Acumulado em Repasses:** R$ {total_repasse:.2f}
    * **Saldo de Caixa (Entradas - Saídas):** R$ {saldo:.2f}
    """
    return kpi_texto

# 4. Operações de Banco de Dados
def registrar_entrega(data, motorista, bairro, pacotes, valor_pacote):
    if not motorista or motorista == "Nenhum motorista cadastrado":
        return carregar_tabela('entregas'), "❌ Selecione ou cadastre um motorista válido!", calcular_kpis()
        
    if not data:
        data = datetime.now().strftime("%d/%m/%Y")
    total = pacotes * valor_pacote
    
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO entregas (data, motorista, bairro, pacotes, valor_pacote, total, status)
            VALUES (:data, :mot, :bai, :pac, :val, :tot, 'Ativo')
        '''), {"data": data, "mot": motorista, "bai": bairro, "pac": pacotes, "val": valor_pacote, "tot": total})
    
    return carregar_tabela('entregas'), f"✅ Salvo! Total Repasse: R$ {total:.2f}", calcular_kpis()

def cadastrar_motorista(nome, pix, telefone):
    if not nome:
        return carregar_tabela('motoristas'), "❌ Informe o nome do motorista!", gr.update()
        
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO motoristas (nome, chave_pix, telefone)
            VALUES (:nome, :pix, :tel)
        '''), {"nome": nome, "pix": pix, "tel": telefone})
    
    novos_motoristas = listar_motoristas()
    return carregar_tabela('motoristas'), "✅ Motorista cadastrado com sucesso!", gr.update(choices=novos_motoristas)

def registrar_financeiro(descricao, tipo, valor):
    data = datetime.now().strftime("%d/%m/%Y")
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO financeiro (data, descricao, tipo, valor)
            VALUES (:data, :desc, :tipo, :val)
        '''), {"data": data, "desc": descricao, "tipo": tipo, "val": valor})
    
    return carregar_tabela('financeiro'), "✅ Lançamento salvo!", calcular_kpis()

def cancelar_registro(id_registro):
    if not id_registro:
        return carregar_tabela('entregas'), "❌ Informe o ID da entrega!", calcular_kpis()
    
    with engine.begin() as conn:
        conn.execute(text("UPDATE entregas SET status = 'Cancelado' WHERE id = :id"), {"id": int(id_registro)})
    
    return carregar_tabela('entregas'), f"⚠️ Registro #{id_registro} marcado como Cancelado.", calcular_kpis()

def filtrar_dados(motorista_filtro, bairro_filtro, data_filtro):
    query = "SELECT * FROM entregas WHERE status != 'Cancelado'"
    params = {}
    
    if motorista_filtro and motorista_filtro != "Todos":
        query += " AND motorista ILIKE :mot" 
        params["mot"] = f"%{motorista_filtro}%"
    if bairro_filtro:
        query += " AND bairro ILIKE :bai"
        params["bai"] = f"%{bairro_filtro}%"
    if data_filtro:
        query += " AND data LIKE :data"
        params["data"] = f"%{data_filtro}%"
        
    df_filtrado = pd.read_sql_query(text(query), engine, params=params)
    
    total_pacotes = df_filtrado["pacotes"].sum() if not df_filtrado.empty else 0
    total_pago = df_filtrado["total"].sum() if not df_filtrado.empty else 0
    
    resumo = f"Filtro Aplicado: {total_pacotes} Pacotes | Repasse Total: R$ {total_pago:.2f}"
    return df_filtrado, resumo

# 5. Exportação e Gerador WhatsApp
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
        return "Selecione um motorista específico para gerar o comprovante."
    
    if not data_consulta:
        data_consulta = datetime.now().strftime("%d/%m/%Y")
        
    df_entregas, _ = filtrar_dados(motorista_nome, "", data_consulta)
    
    # Busca dados do motorista
    df_mot = pd.read_sql_query(text("SELECT chave_pix, telefone FROM motoristas WHERE nome = :nome"), engine, params={"nome": motorista_nome})
    chave_pix = df_mot['chave_pix'].iloc[0] if not df_mot.empty else "Não cadastrada"
    
    if df_entregas.empty:
        return f"Nenhuma entrega ativa encontrada para {motorista_nome} na data {data_consulta}."
    
    total_pacotes = df_entregas['pacotes'].sum()
    total_repasse = df_entregas['total'].sum()
    
    texto_whatsapp = f"""📲 *DEMONSTRATIVO DE REPASSE*
👤 *Motorista:* {motorista_nome}
📅 *Data:* {data_consulta}
📦 *Total de Pacotes:* {total_pacotes}
💰 *Valor a Receber:* R$ {total_repasse:.2f}
🔑 *Chave PIX:* {chave_pix}

_Conferido pelo Sistema Logístico._"""
    return texto_whatsapp

# 6. Interface Gráfica (Gradio)
with gr.Blocks(theme=gr.themes.Soft()) as app:
    gr.Markdown("# 📦 Sistema de Controle Logístico e Financeiro")
    
    kpi_box = gr.Markdown(value=calcular_kpis())
    
    with gr.Tab("Controle de Entregas"):
        with gr.Row():
            data_in = gr.Textbox(label="Data (DD/MM/AAAA) - Vazio para hoje")
            motorista_in = gr.Dropdown(choices=listar_motoristas(), label="Motorista")
            bairro_in = gr.Textbox(label="Bairro")
        with gr.Row():
            pacotes_in = gr.Number(label="Quantidade de Pacotes", value=1, minimum=1)
            valor_in = gr.Number(label="Valor por Pacote (R$)", value=0.0)
        
        btn_entrega = gr.Button("Salvar Registro", variant="primary")
        msg_entrega = gr.Textbox(label="Status", interactive=False)
        tabela_entregas = gr.Dataframe(value=carregar_tabela('entregas'), interactive=False, label="Histórico de Entregas")
        
        with gr.Row():
            id_cancelar_in = gr.Number(label="ID do Registro para Cancelar", precision=0)
            btn_cancelar = gr.Button("⚠️ Cancelar Entrega por ID", variant="stop")
            
        btn_entrega.click(registrar_entrega, inputs=[data_in, motorista_in, bairro_in, pacotes_in, valor_in], outputs=[tabela_entregas, msg_entrega, kpi_box])
        btn_cancelar.click(cancelar_registro, inputs=[id_cancelar_in], outputs=[tabela_entregas, msg_entrega, kpi_box])

    with gr.Tab("Relatórios & WhatsApp"):
        with gr.Row():
            filtro_data = gr.Textbox(label="Data (DD/MM/AAAA)")
            filtro_mot = gr.Dropdown(choices=["Todos"] + listar_motoristas(), value="Todos", label="Motorista")
            filtro_bairro = gr.Textbox(label="Bairro")
            
        btn_filtrar = gr.Button("🔍 Aplicar Filtros", variant="primary")
        resumo_filtro = gr.Textbox(label="Resumo do Filtro", interactive=False)
        tabela_filtrada = gr.Dataframe(label="Resultados", interactive=False)
        
        with gr.Row():
            btn_exportar_excel = gr.Button("📊 Baixar Excel (.xlsx)")
            btn_exportar_csv = gr.Button("📄 Baixar CSV (.csv)")
            btn_wa = gr.Button("📲 Gerar Resumo para WhatsApp", variant="secondary")
            
        arquivo_download = gr.File(label="Arquivo Gerado")
        texto_wa_out = gr.TextArea(label="Texto Prontinho para Copiar no WhatsApp", interactive=False)
        
        btn_filtrar.click(filtrar_dados, inputs=[filtro_mot, filtro_bairro, filtro_data], outputs=[tabela_filtrada, resumo_filtro])
        btn_exportar_excel.click(exportar_excel, inputs=[filtro_mot, filtro_bairro, filtro_data], outputs=[arquivo_download])
        btn_exportar_csv.click(exportar_csv, inputs=[filtro_mot, filtro_bairro, filtro_data], outputs=[arquivo_download])
        btn_wa.click(gerar_comprovante_whatsapp, inputs=[filtro_mot, filtro_data], outputs=[texto_wa_out])

    with gr.Tab("Cadastro de Motoristas"):
        with gr.Row():
            nome_in = gr.Textbox(label="Nome Completo")
            pix_in = gr.Textbox(label="Chave PIX")
            tel_in = gr.Textbox(label="Telefone / WhatsApp")
        
        btn_mot = gr.Button("Cadastrar Motorista", variant="primary")
        msg_mot = gr.Textbox(label="Status", interactive=False)
        tabela_mot = gr.Dataframe(value=carregar_tabela('motoristas'), interactive=False, label="Motoristas Cadastrados")
        
        btn_mot.click(cadastrar_motorista, inputs=[nome_in, pix_in, tel_in], outputs=[tabela_mot, msg_mot, motorista_in])

    with gr.Tab("Financeiro"):
        with gr.Row():
            desc_in = gr.Textbox(label="Descrição do Lançamento")
            tipo_in = gr.Dropdown(choices=["Entrada", "Saída"], label="Tipo de Fluxo")
            valor_fin_in = gr.Number(label="Valor (R$)", value=0.0)
        
        btn_fin = gr.Button("Salvar Lançamento", variant="primary")
        msg_fin = gr.Textbox(label="Status", interactive=False)
        tabela_fin = gr.Dataframe(value=carregar_tabela('financeiro'), interactive=False, label="Fluxo de Caixa")
        
        btn_fin.click(registrar_financeiro, inputs=[desc_in, tipo_in, valor_fin_in], outputs=[tabela_fin, msg_fin, kpi_box])

app.launch(server_name="0.0.0.0", server_port=7860)
