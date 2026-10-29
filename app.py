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
            valor_recebido REAL,
            valor_repasse REAL,
            total_recebido REAL,
            total_repasse REAL,
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
            veiculo TEXT,
            tarifa_repasse REAL,
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
    conn.execute(text("ALTER TABLE entregas ADD COLUMN IF NOT EXISTS valor_recebido REAL DEFAULT 0.0;"))
    conn.execute(text("ALTER TABLE entregas ADD COLUMN IF NOT EXISTS valor_repasse REAL DEFAULT 0.0;"))
    conn.execute(text("ALTER TABLE entregas ADD COLUMN IF NOT EXISTS total_recebido REAL DEFAULT 0.0;"))
    conn.execute(text("ALTER TABLE entregas ADD COLUMN IF NOT EXISTS total_repasse REAL DEFAULT 0.0;"))
    
    conn.execute(text("ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS veiculo TEXT;"))
    conn.execute(text("ALTER TABLE motoristas ADD COLUMN IF NOT EXISTS tarifa_repasse REAL DEFAULT 0.0;"))
    
    conn.execute(text("ALTER TABLE devolucoes ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Ativo';"))
    conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Ativo';"))
    conn.execute(text("ALTER TABLE cargas ADD COLUMN IF NOT EXISTS rota TEXT;"))

# 4. Funções Auxiliares e KPIs
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

def buscar_tarifa_motorista(motorista_nome):
    try:
        df = pd.read_sql_query("SELECT tarifa_repasse FROM motoristas WHERE nome = :nome", engine, params={"nome": motorista_nome})
        if not df.empty and pd.notna(df['tarifa_repasse'].iloc[0]):
            return float(df['tarifa_repasse'].iloc[0])
    except:
        pass
    return 0.0

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
    
    col_repasse = 'total_repasse' if 'total_repasse' in df_entregas.columns else 'total'
    col_recebido = 'total_recebido' if 'total_recebido' in df_entregas.columns else 'total'
    
    total_repasse = float(df_entregas[col_repasse].sum()) if not df_entregas.empty else 0.0
    total_recebido = float(df_entregas[col_recebido].sum()) if not df_entregas.empty else 0.0
    lucro_bruto = total_recebido - total_repasse
    
    entradas = float(df_fin[df_fin['tipo'] == 'Entrada']['valor'].sum()) if not df_fin.empty else 0.0
    saidas = float(df_fin[df_fin['tipo'] == 'Saída']['valor'].sum()) if not df_fin.empty else 0.0
    saldo = entradas - saidas
    
    kpi_texto = f"""
    ### 📊 Indicadores Gerais
    * **Carga Total Saída:** {total_saida} pacotes | **Entregues:** {total_entregue} | **Devolvidos:** {total_devolvido}
    * **Total Recebido (Cliente):** R$ {total_recebido:.2f} | **Total Repasse (Motoristas):** R$ {total_repasse:.2f}
    * **Lucro Bruto Estimado:** R$ {lucro_bruto:.2f}
    * **Saldo de Caixa Atual:** R$ {saldo:.2f}
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

def registrar_entrega(data, motorista, bairro, pacotes, valor_recebido):
    if not motorista or motorista == "Nenhum motorista cadastrado":
        return carregar_tabela('entregas'), "❌ Selecione ou cadastre um motorista válido!", calcular_kpis(), gerar_grafico_bairros()
        
    if not bairro or bairro == "Nenhum bairro cadastrado":
        return carregar_tabela('entregas'), "❌ Selecione ou cadastre um bairro válido!", calcular_kpis(), gerar_grafico_bairros()

    if not data:
        data = obter_data_hoje()
        
    tarifa_repasse = buscar_tarifa_motorista(motorista)
    total_recebido = pacotes * valor_recebido
    total_repasse = pacotes * tarifa_repasse
    
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO entregas (data, motorista, bairro, pacotes, valor_recebido, valor_repasse, total_recebido, total_repasse, status)
            VALUES (:data, :mot, :bai, :pac, :val_rec, :val_rep, :tot_rec, :tot_rep, 'Ativo')
        '''), {
            "data": data, "mot": motorista, "bai": bairro, "pac": pacotes, 
            "val_rec": valor_recebido, "val_rep": tarifa_repasse, 
            "tot_rec": total_recebido, "tot_rep": total_repasse
        })
    
    return carregar_tabela('entregas'), f"✅ Salvo! Recebido: R$ {total_recebido:.2f} | Repasse (R$ {tarifa_repasse:.2f}/un): R$ {total_repasse:.2f}", calcular_kpis(), gerar_grafico_bairros()

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

def cadastrar_motorista(nome, veiculo, tarifa_repasse, pix, telefone):
    if not nome:
        return carregar_tabela('motoristas'), "❌ Informe o nome do motorista!", gr.update(), gr.update(), gr.update(), gr.update()
        
    nome_limpo = nome.strip()
    with engine.begin() as conn:
        # Verifica se já existe
        existe = conn.execute(text("SELECT id FROM motoristas WHERE nome ILIKE :nome"), {"nome": nome_limpo}).fetchone()
        if existe:
            conn.execute(text('''
                UPDATE motoristas SET veiculo = :veiculo, tarifa_repasse = :tarifa, chave_pix = :pix, telefone = :tel
                WHERE nome ILIKE :nome
            '''), {"nome": nome_limpo, "veiculo": veiculo, "tarifa": float(tarifa_repasse), "pix": pix, "tel": telefone})
            msg = f"✅ Motorista '{nome_limpo}' atualizado com sucesso!"
        else:
            conn.execute(text('''
                INSERT INTO motoristas (nome, veiculo, tarifa_repasse, chave_pix, telefone)
                VALUES (:nome, :veiculo, :tarifa, :pix, :tel)
            '''), {"nome": nome_limpo, "veiculo": veiculo, "tarifa": float(tarifa_repasse), "pix": pix, "tel": telefone})
            msg = f"✅ Motorista '{nome_limpo}' cadastrado com sucesso!"
    
    novos_motoristas = listar_motoristas()
    return carregar_tabela('motoristas'), msg, gr.update(choices=novos_motoristas), gr.update(choices=novos_motoristas), gr.update(choices=novos_motoristas), gr.update(choices=["Todos"] + novos_motoristas)

def apagar_motorista(id_motorista):
    if not id_motorista:
        return carregar_tabela('motoristas'), "❌ Informe o ID do motorista para apagar!", gr.update(), gr.update(), gr.update(), gr.update()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM motoristas WHERE id = :id"), {"id": int(id_motorista)})
        novos_motoristas = listar_motoristas()
        return carregar_tabela('motoristas'), f"🗑️ Motorista #{id_motorista} apagado com sucesso!", gr.update(choices=novos_motoristas), gr.update(choices=novos_motoristas), gr.update(choices=novos_motoristas), gr.update(choices=["Todos"] + novos_motoristas)
    except Exception as e:
        return carregar_tabela('motoristas'), f"❌ Erro ao apagar: {e}", gr.update(), gr.update(), gr.update(), gr.update()

def cadastrar_bairro(nome):
    if not nome:
        return carregar_tabela('bairros'), "❌ Informe o nome do bairro!", gr.update(), gr.update()
        
    nome_limpo = nome.strip()
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO bairros (nome) VALUES (:nome)
            ON CONFLICT (nome) DO NOTHING
        '''), {"nome": nome_limpo})
    
    novos_bairros = listar_bairros()
    return carregar_tabela('bairros'), f"✅ Bairro '{nome_limpo}' registado com sucesso!", gr.update(choices=novos_bairros), gr.update(choices=novos_bairros)

def registrar_financeiro(descricao, tipo, valor):
    data = obter_data_hoje()
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO financeiro (data, descricao, tipo, valor)
            VALUES (:data, :desc, :tipo, :val)
        '''), {"data": data, "desc": descricao, "tipo": tipo, "val": valor})
    
    return carregar_tabela('financeiro'), "✅ Lançamento salvo!", calcular_kpis()

def pagar_motorista_automatico(motorista_nome, data_consulta):
    if not motorista_nome or motorista_nome == "Todos":
        return "❌ Selecione um motorista específico para efetuar o pagamento."
    if not data_consulta:
        data_consulta = obter_data_hoje()
        
    df_resumo, _, _ = obter_dados_unificados(motorista_nome, data_consulta)
    if df_resumo.empty:
        return f"❌ Nenhuma entrega encontrada para {motorista_nome} na data {data_consulta}."
        
    total_repasse = float(df_resumo['Repasse Total (R$)'].sum())
    if total_repasse <= 0:
        return f"❌ O valor de repasse para {motorista_nome} nesta data é R$ 0.00."

    descricao = f"Repasse Logístico - {motorista_nome} - {data_consulta}"
    
    with engine.begin() as conn:
        conn.execute(text('''
            INSERT INTO financeiro (data, descricao, tipo, valor)
            VALUES (:data, :desc, 'Saída', :val)
        '''), {"data": data_consulta, "desc": descricao, "val": total_repasse})
        
    return f"✅ Pagamento de R$ {total_repasse:.2f} registado com sucesso no Fluxo de Caixa!"

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

# 6. Unificação e Exportações
def obter_dados_unificados(motorista_filtro, data_filtro):
    cond = "status != 'Cancelado'"
    params = {}
    if motorista_filtro and motorista_filtro != "Todos":
        cond += " AND motorista ILIKE :mot"
        params['mot'] = f"%{motorista_filtro}%"
    if data_filtro:
        cond += " AND data LIKE :data"
        params['data'] = f"%{data_filtro}%"

    df_c = pd.read_sql_query(text(f"SELECT data, motorista, rota as bairro, pacotes, '1 - Carga (Saída)' as tipo FROM cargas WHERE {cond}"), engine, params=params)
    df_e = pd.read_sql_query(text(f"SELECT data, motorista, bairro, pacotes, total_recebido, total_repasse, '2 - Entrega' as tipo FROM entregas WHERE {cond}"), engine, params=params)
    df_d = pd.read_sql_query(text(f"SELECT data, motorista, bairro, pacotes, motivo, '3 - Devolução' as tipo FROM devolucoes WHERE {cond}"), engine, params=params)

    list_dfs = []
    if not df_c.empty:
        temp_c = df_c.copy()
        temp_c['detalhe'] = ""
        list_dfs.append(temp_c[['data', 'motorista', 'tipo', 'bairro', 'pacotes', 'detalhe']])
    if not df_e.empty:
        temp_e = df_e.copy()
        temp_e['detalhe'] = "Rec: R$ " + temp_e['total_recebido'].astype(str) + " | Rep: R$ " + temp_e['total_repasse'].astype(str)
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

    g_c = df_c.groupby(['data', 'motorista'], as_index=False)['pacotes'].sum() if not df_c.empty else pd.DataFrame(columns=['data', 'motorista', 'pacotes'])
    g_e = df_e.groupby(['data', 'motorista'], as_index=False)[['pacotes', 'total_recebido', 'total_repasse']].sum() if not df_e.empty else pd.DataFrame(columns=['data', 'motorista', 'pacotes', 'total_recebido', 'total_repasse'])
    g_d = df_d.groupby(['data', 'motorista'], as_index=False)['pacotes'].sum() if not df_d.empty else pd.DataFrame(columns=['data', 'motorista', 'pacotes'])

    dfs_keys = []
    if not g_c.empty: dfs_keys.append(g_c[['data', 'motorista']])
    if not g_e.empty: dfs_keys.append(g_e[['data', 'motorista']])
    if not g_d.empty: dfs_keys.append(g_d[['data', 'motorista']])
    
    if not dfs_keys:
        df_resumo = pd.DataFrame(columns=['Data', 'Motorista', 'Saiu (Carga)', 'Entregues', 'Devolvidos', 'Pendentes', 'Total Recebido (R$)', 'Repasse Total (R$)'])
    else:
        df_resumo = pd.concat(dfs_keys).drop_duplicates()
        if not g_c.empty: df_resumo = pd.merge(df_resumo, g_c.rename(columns={'pacotes':'saida'}), on=['data', 'motorista'], how='left')
        else: df_resumo['saida'] = 0
        
        if not g_e.empty: 
            df_resumo = pd.merge(df_resumo, g_e.rename(columns={'pacotes':'entregues', 'total_recebido':'recebido', 'total_repasse':'repasse'}), on=['data', 'motorista'], how='left')
        else: 
            df_resumo['entregues'] = 0
            df_resumo['recebido'] = 0
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
            'recebido': 'Total Recebido (R$)',
            'repasse': 'Repasse Total (R$)'
        }, inplace=True)

    total_ent = df_resumo['Entregues'].sum() if not df_resumo.empty else 0
    total_dev = df_resumo['Devolvidos'].sum() if not df_resumo.empty else 0
    total_rec = df_resumo['Total Recebido (R$)'].sum() if not df_resumo.empty else 0.0
    total_rep = df_resumo['Repasse Total (R$)'].sum() if not df_resumo.empty else 0.0
    texto_resumo = f"Resumo Global: {total_ent} Entregues | {total_dev} Devolvidos | Recebido: R$ {total_rec:.2f} | Repasse: R$ {total_rep:.2f}"
    
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

def fazer_backup_geral():
    caminho = "backup_geral_sannovas.xlsx"
    with pd.ExcelWriter(caminho) as writer:
        carregar_tabela('cargas').to_excel(writer, sheet_name="Cargas", index=False)
        carregar_tabela('entregas').to_excel(writer, sheet_name="Entregas", index=False)
        carregar_tabela('devolucoes').to_excel(writer, sheet_name="Devolucoes", index=False)
        carregar_tabela('motoristas').to_excel(writer, sheet_name="Motoristas", index=False)
        carregar_tabela('bairros').to_excel(writer, sheet_name="Bairros", index=False)
        carregar_tabela('financeiro').to_excel(writer, sheet_name="Financeiro", index=False)
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
        gr.Markdown("### 📦 Registo de Sucesso")
        with gr.Row():
            data_in = gr.Textbox(label="Data (DD/MM/AAAA) - Vazio para hoje")
            motorista_in = gr.Dropdown(choices=listar_motoristas(), label="Motorista")
            bairro_in = gr.Dropdown(choices=listar_bairros(), label="Bairro")
        with gr.Row():
            pacotes_in = gr.Number(label="Quantidade de Pacotes Entregues", value=1, minimum=1)
            valor_recebido_in = gr.Number(label="Valor Recebido por Pacote do Cliente (R$)", value=0.0)
        
        btn_entrega = gr.Button("Salvar Registo de Entrega", variant="primary")
        msg_entrega = gr.Textbox(label="Status", interactive=False)
        tabela_entregas = gr.Dataframe(value=carregar_tabela('entregas'), interactive=False, label="Histórico de Entregas")
        
        with gr.Row():
            id_cancelar_in = gr.Number(label="ID do Registo para Cancelar", precision=0)
            btn_cancelar = gr.Button("⚠️ Cancelar Entrega por ID", variant="stop")
            
        btn_entrega.click(registrar_entrega, inputs=[data_in, motorista_in, bairro_in, pacotes_in, valor_recebido_in], outputs=[tabela_entregas, msg_entrega, kpi_box, gr.BarPlot()])
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
        
        tabela_resumo = gr.Dataframe(label="📊 Resumo Consolidado", interactive=False)
        tabela_detalhada = gr.Dataframe(label="📝 Histórico Detalhado Unificado", interactive=False)
        
        gr.Markdown("### 📈 Volume de Pacotes por Bairro (Apenas Sucessos)")
        grafico_out = gr.BarPlot(
            value=grafico_bairros := gerar_grafico_bairros(),
            x="bairro",
            y="pacotes",
            title="Pacotes Entregues por Bairro",
            tooltip=["bairro", "pacotes"],
            height=300
        )
        
        with gr.Row():
            btn_exportar_excel_r = gr.Button("📊 Baixar Fechamento (.xlsx)")
            btn_exportar_excel_d = gr.Button("📊 Baixar Histórico (.xlsx)")
            btn_wa = gr.Button("📲 Gerar Resumo WhatsApp", variant="secondary")
            
        with gr.Row():
            btn_pagar_caixa = gr.Button("💰 Lançar Pagamento do Repasse no Caixa (Automático)", variant="primary")
            msg_pagamento = gr.Textbox(label="Status do Pagamento no Caixa", interactive=False)
            
        arquivo_download = gr.File(label="Ficheiro Gerado")
        texto_wa_out = gr.TextArea(label="Demonstrativo / Prestação de Contas WhatsApp", interactive=False)
        
        btn_hoje.click(obter_data_hoje, outputs=[filtro_data])
        btn_mes.click(obter_mes_atual, outputs=[filtro_data])
        btn_filtrar.click(obter_dados_unificados, inputs=[filtro_mot, filtro_data], outputs=[tabela_resumo, tabela_detalhada, resumo_filtro])
        
        btn_exportar_excel_r.click(exportar_excel_resumo, inputs=[filtro_mot, filtro_data], outputs=[arquivo_download])
        btn_exportar_excel_d.click(exportar_excel_detalhado, inputs=[filtro_mot, filtro_data], outputs=[arquivo_download])
        btn_wa.click(gerar_comprovante_whatsapp, inputs=[filtro_mot, filtro_data], outputs=[texto_wa_out])
        btn_pagar_caixa.click(pagar_motorista_automatico, inputs=[filtro_mot, filtro_data], outputs=[msg_pagamento])

    with gr.Tab("Cadastro de Motoristas"):
        gr.Markdown("### 👤 Cadastrar / Atualizar / Apagar Motoristas")
        with gr.Row():
            nome_in = gr.Textbox(label="Nome Completo")
            veiculo_in = gr.Dropdown(choices=["Carro", "Moto", "Bicicleta", "Outro"], value="Moto", label="Tipo de Veículo")
            tarifa_in = gr.Number(label="Tarifa de Repasse por Pacote (R$)", value=2.0)
        with gr.Row():
            pix_in = gr.Textbox(label="Chave PIX")
            tel_in = gr.Textbox(label="Telefone / WhatsApp")
        
        with gr.Row():
            btn_mot = gr.Button("Guardar / Atualizar Motorista", variant="primary")
            
        with gr.Row():
            id_apagar_mot_in = gr.Number(label="ID do Motorista para Apagar", precision=0)
            btn_apagar_mot = gr.Button("🗑️ Apagar Motorista por ID", variant="stop")
            
        msg_mot = gr.Textbox(label="Status", interactive=False)
        tabela_mot = gr.Dataframe(value=carregar_tabela('motoristas'), interactive=False, label="Motoristas Cadastrados (Veja o ID aqui)")
        
        btn_mot.click(cadastrar_motorista, inputs=[nome_in, veiculo_in, tarifa_in, pix_in, tel_in], outputs=[tabela_mot, msg_mot, motorista_carga_in, motorista_in, motorista_dev_in, filtro_mot])
        btn_apagar_mot.click(apagar_motorista, inputs=[id_apagar_mot_in], outputs=[tabela_mot, msg_mot, motorista_carga_in, motorista_in, motorista_dev_in, filtro_mot])

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
        
        with gr.Row():
            btn_fin = gr.Button("Salvar Lançamento", variant="primary")
            btn_backup = gr.Button("📥 Baixar Backup Geral (Todas as Tabelas)", variant="secondary")
            
        msg_fin = gr.Textbox(label="Status", interactive=False)
        tabela_fin = gr.Dataframe(value=carregar_tabela('financeiro'), interactive=False, label="Fluxo de Caixa")
        
        arquivo_backup = gr.File(label="Ficheiro de Backup Gerado")
        
        btn_fin.click(registrar_financeiro, inputs=[desc_in, tipo_in, valor_fin_in], outputs=[tabela_fin, msg_fin, kpi_box])
        btn_backup.click(fazer_backup_geral, outputs=[arquivo_backup])

# 8. Lançar a aplicação com Autenticação Nativa (Login/Senha)
app.launch(
    server_name="0.0.0.0", 
    server_port=7860, 
    auth=(USUARIO_ADMIN, SENHA_ADMIN)
)
