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
            rota TEXT,
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
    conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS rota TEXT;"))

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
def registrar_carga(data, motorista, pacotes, rota):
    if not motorista or motorista == "Nenhum motorista cadastrado":
        return carregar_tabela('cargas'), "❌ Selecione um motorista válido!", calcular_kpis()
    if not data:
        data = obter_data_hoje()
        
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO cargas (data, motorista, pacotes, rota, status)
            VALUES (:data, :mot, :pac, :rota, 'Ativo')
        '''), {"data": data, "mot": motorista, "pac": int(pacotes), "rota": rota})
        
    return carregar_tabela('cargas'), f"✅ Saída de {pacotes} pacotes registada para {motorista}!", calcular_kpis()

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
    
    return carregar_tabela('devolucoes'), f"✅ Devolução registada ({pacotes} pacotes)!", calcular_kpis()

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
    return carregar_tabela('bairros'), "✅ Bairro cadastrado com sucesso!", gr.update(choices=novos_bairros), gr.update(choices=novos_bairros)

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
    return carregar_tabela('entregas'), f"⚠️ Registo #{id_registro} marcado como Cancelado.", calcular_kpis(), gerar_grafico_bairros()

def cancelar_devolucao(id_registro):
    if not id_registro:
        return carregar_tabela('devolucoes'), "❌ Informe o ID da devolução!", calcular_kpis()
    with engine.begin() as conn:
        conn.execute(text("UPDATE devolucoes SET status = 'Cancelado' WHERE id = :id"), {"id": int(id_registro)})
    return carregar_tabela('devolucoes'), f"⚠️ Devolução #{id_registro} marcada como Cancelada.", calcular_kpis()

# 6. Unificação e Exportação (O GRANDE AJUSTE)
def obter_dados_unificados(motorista_filtro, data_filtro):
    cond = "status != 'Cancelado'"
    params = {}
    if motorista_filtro and motorista_filtro != "Todos":
        cond += " AND motorista ILIKE :mot"
        params['mot'] = f"%{motorista_filtro}%"
    if data_filtro:
        cond += " AND data LIKE :data"
        params['data'] = f"%{data_filtro}%"

    # Busca as três bases de dados
    df_c = pd.read_sql_query(text(f"SELECT data, motorista, rota as bairro, pacotes, '1 - Carga (Saída)' as tipo FROM cargas WHERE {cond}"), engine, params=params)
    df_e = pd.read_sql_query(text(f"SELECT data, motorista, bairro, pacotes, total, '2 - Entrega' as tipo FROM entregas WHERE {cond}"), engine, params=params)
    df_d = pd.read_sql_query(text(f"SELECT data, motorista, bairro, pacotes, motivo, '3 - Devolução' as tipo FROM devolucoes WHERE {cond}"), engine, params=params)

    # --- TABELA 1: DETALHADA UNIFICADA (Tudo na mesma lista) ---
    list_dfs = []
    if not df_c.empty:
        temp_c = df_c.copy()
        temp_c['detalhe'] = ""
        list_dfs.append(temp_c[['data', 'motorista', 'tipo', 'bairro', 'pacotes', 'detalhe']])
    if not df_e.empty:
        temp_e = df_e.copy()
        temp_e['detalhe'] = "R$ " + temp_e['total'].astype(str)
        list_dfs.append(temp_e[['data', 'motorista', 'tipo', 'bairro', 'pacotes', 'detalhe']])
    if not df_d.empty:
        temp_d = df_d.copy()
        temp_d['detalhe'] = temp_d['motivo']
        list_dfs.append(temp_d[['data', 'motorista', 'tipo', 'bairro', 'pacotes', 'detalhe']])
        
    if list_dfs:
        df_uni = pd.concat(list_dfs, ignore_index=True)
        df_uni.sort_values(by=['data', 'motorista', 'tipo'], inplace=True)
        df_uni.columns = ['Data', 'Motorista', 'Operação', 'Bairro/Rota', 'Pacotes', 'Info Adicional']
    else:
        df_uni = pd.DataFrame(columns=['Data', 'Motorista', 'Operação', 'Bairro/Rota', 'Pacotes', 'Info Adicional'])

    # --- TABELA 2: RESUMO CONSOLIDADO (Saiu, Entregue, Devolvido na mesma linha) ---
    g_c = df_c.groupby(['data', 'motorista'], as_index=False)['pacotes'].sum() if not df_c.empty else pd.DataFrame(columns=['data', 'motorista', 'pacotes'])
    g_e = df_e.groupby(['data', 'motorista'], as_index=False)[['pacotes', 'total']].sum() if not df_e.empty else pd.DataFrame(columns=['data', 'motorista', 'pacotes', 'total'])
    g_d = df_d.groupby(['data', 'motorista'], as_index=False)['pacotes'].sum() if not df_d.empty else pd.DataFrame(columns=['data', 'motorista', 'pacotes'])

    dfs_keys = []
    if not g_c.empty: dfs_keys.append(g_c[['data', 'motorista']])
    if not g_e.empty: dfs_keys.append(g_e[['data', 'motorista']])
    if not g_d.empty: dfs_keys.append(g_d[['data', 'motorista']])
    
    if not dfs_keys:
        df_resumo = pd.DataFrame(columns=['Data', 'Motorista', 'Saiu (Carga)', 'Entregues', 'Devolvidos', 'Pendentes', 'Repasse Total (R$)'])
    else:
        df_resumo = pd.concat(dfs_keys).drop_duplicates()
        
        # Junta todas as contas na mesma linha
        if not g_c.empty: df_resumo = pd.merge(df_resumo, g_c.rename(columns={'pacotes':'saida'}), on=['data', 'motorista'], how='left')
        else: df_resumo['saida'] = 0
        
        if not g_e.empty: df_resumo = pd.merge(df_resumo, g_e.rename(columns={'pacotes':'entregues', 'total':'repasse'}), on=['data', 'motorista'], how='left')
        else: 
            df_resumo['entregues'] = 0
            df_resumo['repasse'] = 0
            
        if not g_d.empty: df_resumo = pd.merge(df_resumo, g_d.rename(columns={'pacotes':'devolvidos'}), on=['data', 'motorista'], how='left')
        else: df_resumo['devolvidos'] = 0

        df_resumo.fillna(0, inplace=True)
        df_resumo['pendentes'] = df_resumo['saida'] - (df_resumo['entregues'] + df_resumo['devolvidos'])
        
        df_resumo.rename(columns={
            'data': 'Data',
            'motorista': 'Motorista',
            'saida': 'Saiu (Carga)',
            'entregues': 'Entregues',
            'devolvidos': 'Devolvidos',
            'pendentes': 'Pendentes',
            'repasse': 'Repasse Total (R$)'
        }, inplace=True)

    # Texto de resumo
    total_ent = df_resumo['Entregues'].sum() if not df_resumo.empty else 0
    total_dev = df_resumo['Devolvidos'].sum() if not df_resumo.empty else 0
    total_rep = df_resumo['Repasse Total (R$)'].sum() if not df_resumo.empty else 0.0
    texto_resumo = f"Resumo Global do Filtro: {total_ent} Entregues | {total_dev} Devolvidos | Repasse Total R$ {total_rep:.2f}"
    
    return df_resumo, df_uni, texto_resumo

def exportar_excel_resumo(motorista_filtro, data_filtro):
    df_resumo, _, _ = obter_dados_unificados(motorista_filtro, data_filtro)
    caminho = "fechamento_consolidado.xlsx"
    df_resumo.to_excel(caminho, index=False)
    return caminho

def exportar_excel_detalhado(motorista_filtro, data_filtro):
    _, df_uni, _ = obter_dados_unificados(motorista_filtro, data_filtro)
    caminho = "historico_detalhado.xlsx"
    df_uni.to_excel(caminho, index=False)
    return caminho

def gerar_comprovante_whatsapp(motorista_nome, data_consulta):
    if not motorista_nome or motorista_nome == "Todos":
        return "Selecione um motorista específico para gerar o fechamento."
    if not data_consulta:
        data_consulta = obter_data_hoje()
        
    df_resumo, _, _ = obter_dados_unificados(motorista_nome, data_consulta)
    
    if df_resumo.empty:
        return f"Nenhuma movimentação encontrada para {motorista_nome} na data {data_consulta}."

    total_saida = df_resumo['Saiu (Carga)'].sum()
    total_entregue = df_resumo['Entregues'].sum()
    total_devolucoes = df_resumo['Devolvidos'].sum()
    pendentes = df_resumo['Pendentes'].sum()
    total_repasse = df_resumo['Repasse Total (R$)'].sum()
    
    status_balanco = "✅ Fechamento OK" if pendentes == 0 else f"⚠️ Divergência de {int(pendentes)} pacote(s)"
    if total_saida == 0:
        status_balanco = "ℹ️ Carga Inicial não registada no sistema"

    df_mot = pd.read_sql_query(text("SELECT chave_pix FROM motoristas WHERE nome = :nome"), engine, params={"nome": motorista_nome})
    chave_pix = df_mot['chave_pix'].iloc[0] if not df_mot.empty else "Não cadastrada"
    
    texto_whatsapp = f"""📲 *FECHAMENTO DE ROTA DE ENTREGA*
👤 *Motorista:* {motorista_nome}
📅 *Data:* {data_consulta}

📦 *Carga Inicial (Saída):* {int(total_saida)} pacotes
✅ *Pacotes Entregues:* {int(total_entregue)} pacotes
🔄 *Pacotes Devolvidos:* {int(total_devolucoes)} pacotes
⚖️ *Status do Balanço:* {status_balanco}

💰 *Valor Total Repasse:* R$ {total_repasse:.2f}
🔑 *Chave PIX:* {chave_pix}

_Conferido pelo Sistema SanNovas._"""
    return texto_whatsapp

# 7. Interface Gráfica (Gradio)
with gr.Blocks(theme=gr.themes.Soft()) as app:
    gr.Markdown("# 📦 SanNovas - Controle")
    
    kpi_box = gr.Markdown(value=calcular_kpis())
    
    with gr.Tab("Carga Inicial (Romaneio)"):
        gr.Markdown("### 🚚 Registar Saída de Carga do Galpão")
        with gr.Row():
            data_carga_in = gr.Textbox(label="Data (DD/MM/AAAA) - Vazio para hoje")
            motorista_carga_in = gr.Dropdown(choices=listar_motoristas(), label="Motorista")
            pacotes_carga_in = gr.Number(label="Quantidade Total de Pacotes", value=1, minimum=1)
        with gr.Row():
            rota_carga_in = gr.Textbox(label="Rota / Observação (Opcional) - Ex: Zona Norte")
        
        btn_carga = gr.Button("Registar Saída de Carga", variant="primary")
        msg_carga = gr.Textbox(label="Status", interactive=False)
        tabela_cargas = gr.Dataframe(value=carregar_tabela('cargas'), interactive=False, label="Histórico de Saídas")
        
        with gr.Row():
            id_cancelar_carga_in = gr.Number(label="ID do Registo de Carga para Cancelar", precision=0)
            btn_cancelar_carga = gr.Button("⚠️ Cancelar Carga por ID", variant="stop")
            
        btn_carga.click(registrar_carga, inputs=[data_carga_in, motorista_carga_in, pacotes_carga_in, rota_carga_in], outputs=[tabela_cargas, msg_carga, kpi_box])
        btn_cancelar_carga.click(cancelar_carga, inputs=[id_cancelar_carga_in], outputs=[tabela_cargas, msg_carga, kpi_box])

    with gr.Tab("Controle de Entregas"):
        with gr.Row():
            data_in = gr.Textbox(label="Data (DD/MM/AAAA) - Vazio para hoje")
            motorista_in = gr.Dropdown(choices=listar_motoristas(), label="Motorista")
            bairro_in = gr.Dropdown(choices=listar_bairros(), label="Bairro")
        with gr.Row():
            pacotes_in = gr.Number(label="Quantidade de Pacotes Entregues", value=1, minimum=1)
            valor_in = gr.Number(label="Valor por Pacote (R$)", value=0.0)
        
        btn_entrega = gr.Button("Salvar Registo de Entrega", variant="primary")
        msg_entrega = gr.Textbox(label="Status", interactive=False)
        tabela_entregas = gr.Dataframe(value=carregar_tabela('entregas'), interactive=False, label="Histórico de Entregas")
        
        with gr.Row():
            id_cancelar_in = gr.Number(label="ID do Registo para Cancelar", precision=0)
            btn_cancelar = gr.Button("⚠️ Cancelar Entrega por ID", variant="stop")
            
        btn_entrega.click(registrar_entrega, inputs=[data_in, motorista_in, bairro_in, pacotes_in, valor_in], outputs=[tabela_entregas, msg_entrega, kpi_box, gr.BarPlot()])
        btn_cancelar.click(cancelar_registro, inputs=[id_cancelar_in], outputs=[tabela_entregas, msg_entrega, kpi_box, gr.BarPlot()])

    with gr.Tab("Controle de Devoluções"):
        with gr.Row():
            data_dev_in = gr.Textbox(label="Data (DD/MM/AAAA) - Vazio para hoje")
            motorista_dev_in = gr.Dropdown(choices=listar_motoristas(), label="Motorista")
            bairro_dev_in = gr.Dropdown(choices=listar_bairros(), label="Bairro")
        with gr.Row():
            pacotes_dev_in = gr.Number(label="Quantidade Devolvida", value=1, minimum=1)
            motivo_dev_in = gr.Dropdown(
                choices=["Cliente Ausente", "Endereço Não Encontrado", "Recusado pelo Cliente", "Endereço Incompleto", "Outros"],
                value="Cliente Ausente",
                label="Motivo da Devolução"
            )
        
        btn_devolucao = gr.Button("Registar Devolução", variant="primary")
        msg_devolucao = gr.Textbox(label="Status", interactive=False)
        tabela_devolucoes = gr.Dataframe(value=carregar_tabela('devolucoes'), interactive=False, label="Histórico de Devoluções")
        
        with gr.Row():
            id_cancelar_dev_in = gr.Number(label="ID da Devolução para Cancelar", precision=0)
            btn_cancelar_dev = gr.Button("⚠️ Cancelar Devolução por ID", variant="stop")
            
        btn_devolucao.click(registrar_devolucao, inputs=[data_dev_in, motorista_dev_in, bairro_dev_in, pacotes_dev_in, motivo_dev_in], outputs=[tabela_devolucoes, msg_devolucao, kpi_box])
        btn_cancelar_dev.click(cancelar_devolucao, inputs=[id_cancelar_dev_in], outputs=[tabela_devolucoes, msg_devolucao, kpi_box])

    with gr.Tab("Relatórios & Fechamento"):
        with gr.Row():
            filtro_data = gr.Textbox(label="Data (DD/MM/AAAA)")
            filtro_mot = gr.Dropdown(choices=["Todos"] + listar_motoristas(), value="Todos", label="Motorista")
        
        with gr.Row():
            btn_hoje = gr.Button("📅 Data de Hoje", variant="secondary")
            btn_mes = gr.Button("📅 Mês Atual", variant="secondary")
            btn_filtrar = gr.Button("🔍 Gerar Fechamento Consolidado", variant="primary")
            
        resumo_filtro = gr.Textbox(label="Resultado", interactive=False)
        
        # As duas novas tabelas unificadas
        tabela_resumo = gr.Dataframe(label="📊 Resumo Consolidado (Tudo na mesma linha)", interactive=False)
        tabela_detalhada = gr.Dataframe(label="📝 Histórico Detalhado Unificado", interactive=False)
        
        gr.Markdown("### 📈 Volume de Pacotes por Bairro (Apenas Sucessos)")
        grafico_out = gr.BarPlot(
            value=gerar_grafico_bairros(),
            x="bairro",
            y="pacotes",
            title="Pacotes Entregues por Bairro",
            tooltip=["bairro", "pacotes"],
            height=300
        )
        
        # Botões de Excel novos
        with gr.Row():
            btn_exportar_excel_r = gr.Button("📊 Baixar Fechamento Consolidado (.xlsx)")
            btn_exportar_excel_d = gr.Button("📊 Baixar Histórico Detalhado (.xlsx)")
            btn_wa = gr.Button("📲 Gerar Resumo WhatsApp", variant="secondary")
            
        arquivo_download = gr.File(label="Ficheiro Gerado")
        texto_wa_out = gr.TextArea(label="Demonstrativo / Prestação de Contas WhatsApp", interactive=False)
        
        btn_hoje.click(obter_data_hoje, outputs=[filtro_data])
        btn_mes.click(obter_mes_atual, outputs=[filtro_data])
        btn_filtrar.click(obter_dados_unificados, inputs=[filtro_mot, filtro_data], outputs=[tabela_resumo, tabela_detalhada, resumo_filtro])
        
        btn_exportar_excel_r.click(exportar_excel_resumo, inputs=[filtro_mot, filtro_data], outputs=[arquivo_download])
        btn_exportar_excel_d.click(exportar_excel_detalhado, inputs=[filtro_mot, filtro_data], outputs=[arquivo_download])
        btn_wa.click(gerar_comprovante_whatsapp, inputs=[filtro_mot, filtro_data], outputs=[texto_wa_out])

    with gr.Tab("Cadastro de Motoristas"):
        with gr.Row():
            nome_in = gr.Textbox(label="Nome Completo")
            pix_in = gr.Textbox(label="Chave PIX")
            tel_in = gr.Textbox(label="Telefone / WhatsApp")
        
        btn_mot = gr.Button("Cadastrar Motorista", variant="primary")
        msg_mot = gr.Textbox(label="Status", interactive=False)
        tabela_mot = gr.Dataframe(value=carregar_tabela('motoristas'), interactive=False, label="Motoristas Cadastrados")
        
        btn_mot.click(cadastrar_motorista, inputs=[nome_in, pix_in, tel_in], outputs=[tabela_mot, msg_mot, motorista_carga_in, motorista_in, motorista_dev_in, filtro_mot])

    with gr.Tab("Cadastro de Bairros"):
        with gr.Row():
            nome_bairro_in = gr.Textbox(label="Nome do Bairro")
        
        btn_bairro = gr.Button("Cadastrar Bairro", variant="primary")
        msg_bairro = gr.Textbox(label="Status", interactive=False)
        tabela_bairros = gr.Dataframe(value=carregar_tabela('bairros'), interactive=False, label="Bairros Cadastrados")
        
        btn_bairro.click(cadastrar_bairro, inputs=[nome_bairro_in], outputs=[tabela_bairros, msg_bairro, bairro_in, bairro_dev_in])

    with gr.Tab("Financeiro"):
        with gr.Row():
            desc_in = gr.Textbox(label="Descrição do Lançamento")
            tipo_in = gr.Dropdown(choices=["Entrada", "Saída"], label="Tipo de Fluxo")
            valor_fin_in = gr.Number(label="Valor (R$)", value=0.0)
        
        btn_fin = gr.Button("Salvar Lançamento", variant="primary")
        msg_fin = gr.Textbox(label="Status", interactive=False)
        tabela_fin = gr.Dataframe(value=carregar_tabela('financeiro'), interactive=False, label="Fluxo de Caixa")
        
        btn_fin.click(registrar_financeiro, inputs=[desc_in, tipo_in, valor_fin_in], outputs=[tabela_fin, msg_fin, kpi_box])

# 8. Lançar a aplicação com Autenticação Nativa (Login/Senha)
app.launch(
    server_name="0.0.0.0", 
    server_port=7860, 
    auth=(USUARIO_ADMIN, SENHA_ADMIN)
)
