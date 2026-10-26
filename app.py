# 1. Instalar as bibliotecas para o PostgreSQL
!pip install gradio pandas sqlalchemy psycopg2-binary

import gradio as gr
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# 2. Ligar ao Supabase (String exata fornecida por si, com a password e o psycopg2)
DATABASE_URL = "postgresql+psycopg2://postgres.hbwzwbgmgkbebxqzzboo:Sannovaslog2026@aws-1-us-west-2.pooler.supabase.com:6543/postgres"

# Ligação à base de dados
engine = create_engine(DATABASE_URL)

# 3. Criar as tabelas no PostgreSQL (se não existirem)
with engine.begin() as conn:
    conn.execute(text('''
        CREATE TABLE IF NOT EXISTS entregas (
            id SERIAL PRIMARY KEY,
            data TEXT,
            motorista TEXT,
            bairro TEXT,
            pacotes INTEGER,
            valor_pacote REAL,
            total REAL
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

# Função auxiliar para ler as tabelas e converter para formato de visualização
def carregar_tabela(nome_tabela):
    return pd.read_sql_query(f"SELECT * FROM {nome_tabela} ORDER BY id DESC", engine)

# 4. Funções de Inserção e Pesquisa
def registrar_entrega(data, motorista, bairro, pacotes, valor_pacote):
    if not data:
        data = datetime.now().strftime("%d/%m/%Y")
    total = pacotes * valor_pacote

    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO entregas (data, motorista, bairro, pacotes, valor_pacote, total)
            VALUES (:data, :mot, :bai, :pac, :val, :tot)
        '''), {"data": data, "mot": motorista, "bai": bairro, "pac": pacotes, "val": valor_pacote, "tot": total})

    return carregar_tabela('entregas'), f"Salvo na nuvem! Total: R$ {total:.2f}"

def cadastrar_motorista(nome, pix, telefone):
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO motoristas (nome, chave_pix, telefone)
            VALUES (:nome, :pix, :tel)
        '''), {"nome": nome, "pix": pix, "tel": telefone})

    return carregar_tabela('motoristas'), "Motorista cadastrado com sucesso!"

def registrar_financeiro(descricao, tipo, valor):
    data = datetime.now().strftime("%d/%m/%Y")
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO financeiro (data, descricao, tipo, valor)
            VALUES (:data, :desc, :tipo, :val)
        '''), {"data": data, "desc": descricao, "tipo": tipo, "val": valor})

    return carregar_tabela('financeiro'), "Lançamento salvo na nuvem!"

def filtrar_dados(motorista_filtro, bairro_filtro, data_filtro):
    query = "SELECT * FROM entregas WHERE 1=1"
    params = {}

    if motorista_filtro:
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

    resumo = f"Filtro: {total_pacotes} Pacotes | Repasse: R$ {total_pago:.2f}"
    return df_filtrado, resumo

# 5. Interface Web
with gr.Blocks(theme=gr.themes.Soft()) as app:
    gr.Markdown("# 📦 Sistema de Controle Logístico e Financeiro (Conectado à Nuvem)")

    with gr.Tab("Controle de Entregas"):
        with gr.Row():
            data_in = gr.Textbox(label="Data (DD/MM/AAAA) - Vazio para hoje")
            motorista_in = gr.Textbox(label="Nome do Motorista")
            bairro_in = gr.Textbox(label="Bairro")
        with gr.Row():
            pacotes_in = gr.Number(label="Quantidade de Pacotes", value=1, minimum=1)
            valor_in = gr.Number(label="Valor por Pacote (R$)", value=0.0)

        btn_entrega = gr.Button("Salvar Registro", variant="primary")
        msg_entrega = gr.Textbox(label="Status", interactive=False)
        tabela_entregas = gr.Dataframe(value=carregar_tabela('entregas'), interactive=False, label="Histórico (Últimos salvos primeiro)")

        btn_entrega.click(registrar_entrega, inputs=[data_in, motorista_in, bairro_in, pacotes_in, valor_in], outputs=[tabela_entregas, msg_entrega])

    with gr.Tab("Relatórios e Filtros"):
        with gr.Row():
            filtro_data = gr.Textbox(label="Data")
            filtro_mot = gr.Textbox(label="Motorista")
            filtro_bairro = gr.Textbox(label="Bairro")

        btn_filtrar = gr.Button("🔍 Aplicar Filtros", variant="primary")
        resumo_filtro = gr.Textbox(label="Resumo", interactive=False)
        tabela_filtrada = gr.Dataframe(label="Resultados", interactive=False)

        btn_filtrar.click(filtrar_dados, inputs=[filtro_mot, filtro_bairro, filtro_data], outputs=[tabela_filtrada, resumo_filtro])

    with gr.Tab("Cadastro de Motoristas"):
        with gr.Row():
            nome_in = gr.Textbox(label="Nome")
            pix_in = gr.Textbox(label="Chave PIX")
            tel_in = gr.Textbox(label="Telefone")

        btn_mot = gr.Button("Cadastrar Motorista", variant="primary")
        msg_mot = gr.Textbox(label="Status", interactive=False)
        tabela_mot = gr.Dataframe(value=carregar_tabela('motoristas'), interactive=False, label="Lista")

        btn_mot.click(cadastrar_motorista, inputs=[nome_in, pix_in, tel_in], outputs=[tabela_mot, msg_mot])

    with gr.Tab("Financeiro"):
        with gr.Row():
            desc_in = gr.Textbox(label="Descrição")
            tipo_in = gr.Dropdown(choices=["Entrada", "Saída"], label="Tipo")
            valor_fin_in = gr.Number(label="Valor (R$)", value=0.0)

        btn_fin = gr.Button("Salvar Lançamento", variant="primary")
        msg_fin = gr.Textbox(label="Status", interactive=False)
        tabela_fin = gr.Dataframe(value=carregar_tabela('financeiro'), interactive=False, label="Fluxo")

        btn_fin.click(registrar_financeiro, inputs=[desc_in, tipo_in, valor_fin_in], outputs=[tabela_fin, msg_fin])

app.launch(share=True, debug=True)
