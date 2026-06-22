# streamlit_app.py
import streamlit as st
import pandas as pd
import random
import io
from collections import Counter
from deap import base, creator, tools, algorithms

# =======================
# CONFIG GERAL
# =======================

st.set_page_config(
    page_title="Aplicação para Formação de Cargas - STO Mãe v1 - by: Rafael Góis - 14.Abril.2024",
    layout="wide"
)

st.title("🚚 Gerador de Cargas - STO Mãe v1")
st.write(
    """
    **Desenvolvedor:** Rafael Góis - 14.Abril.2024  
    **Objetivo:** Maximiza a distribuição de paletes em cargas,
    respeitando limites de peso, volume e restrições de remonte.  
    **Descrição:** Esta aplicação utiliza algoritmos genéticos para otimizar a alocação de paletes em cargas,
    garantindo que cada carga atenda às restrições do negócio.
    """
)


# =====================================================
# GUIA RÁPIDO
# =====================================================

st.markdown("---")
st.header("📚 Guia Rápido da Ferramenta")

with st.expander("🚀 Como Utilizar", expanded=False):

    st.markdown("""
### Fluxo Básico

1. Baixe o template padrão.
2. Preencha os SKUs disponíveis.
3. Faça upload do arquivo.
4. Crie uma ou mais cargas.
5. Distribua os paletes entre Base e Remonte.
6. Acompanhe os indicadores.
7. Exporte o planejamento final.

A ferramenta não otimiza automaticamente as cargas.
O usuário possui total liberdade para montar as cargas enquanto o sistema valida as restrições operacionais.
""")

with st.expander("📥 Template e Upload", expanded=False):

    st.markdown("""
### Template

Preencha as colunas obrigatórias:

- SKU
- Paletes a Expedir
- Peso Palete
- M³ Palete
- Peso Remonte

### Upload

Após preencher o Excel:

1. Salve em XLSX.
2. Faça upload na aplicação.
3. Aguarde a validação dos dados.
""")

with st.expander("🚛 Criação e Gestão de Cargas", expanded=False):

    st.markdown("""
### Criar Carga

Clique em **Criar Carga** para gerar um novo card.

### Distribuição

Selecione:

- SKU
- Quantidade
- Carga Destino
- Base ou Remonte

A aplicação atualizará automaticamente:

✓ Saldo disponível

✓ Peso

✓ Cubagem

✓ Ocupação

✓ Restrições
""")

with st.expander("⚙️ Configurações e Perfis", expanded=False):

    st.markdown("""
### Configurações

As configurações definem os limites utilizados na validação das cargas.

Principais parâmetros:

- Peso Máximo da Carga
- Cubagem Máxima
- Máximo de Paletes Base
- Máximo de Paletes Remonte

### Perfis

**Balanceado**
→ Equilíbrio entre ocupação e mix.

**Menor Mix**
→ Prioriza menos SKUs por carga.

**Maior Ocupação**
→ Prioriza melhor aproveitamento do veículo.

**Menor Número de Cargas**
→ Prioriza consolidação.
""")

with st.expander("🚨 Penalidades e Indicadores", expanded=False):

    st.markdown("""
### Penalidades

As penalidades são utilizadas apenas para modos automáticos de planejamento.

Valores maiores tornam determinada restrição mais importante.

Exemplos:

- Peso
- Cubagem
- Mix de SKU
- Dominância de SKU
- Ocupação

### Indicadores

- Peso (%)
- Cubagem (%)
- Base (%)
- Remonte (%)

Quanto mais próximo de 100% sem ultrapassar os limites, melhor o aproveitamento da carga.
""")

with st.expander("🚦 Status da Carga", expanded=False):

    st.markdown("""
🟢 Verde
→ Todas as restrições atendidas.

🟡 Amarelo
→ Algum indicador acima de 90%.

🔴 Vermelho
→ Restrição violada.

Recomenda-se revisar a composição da carga.
""")

with st.expander("📤 Exportação", expanded=False):

    st.markdown("""
Ao finalizar o planejamento:

1. Clique em **Exportar Planejamento**.
2. O sistema gerará um arquivo Excel contendo:

✓ Resumo das Cargas

✓ Detalhamento por SKU

✓ Saldo Final

✓ Indicadores Operacionais
""")

st.markdown("---")
# =======================
# SIDEBAR
# =======================

with st.sidebar:

    perfil = st.selectbox(
        "Perfil",
        ["Balanceado", "Menor Mix", "Maior Ocupação", "Menor Número de Cargas"]
    )

    PERFIS = {
        "Balanceado":              {"max_skus": 5,  "pen_mix": 10000, "dom": 50, "pen_dom": 5000},
        "Menor Mix":               {"max_skus": 3,  "pen_mix": 25000, "dom": 70, "pen_dom": 10000},
        "Maior Ocupação":          {"max_skus": 10, "pen_mix": 3000,  "dom": 40, "pen_dom": 1000},
        "Menor Número de Cargas":  {"max_skus": 20, "pen_mix": 1000,  "dom": 30, "pen_dom": 500},
    }
    p = PERFIS[perfil]

    st.header("⚙️ Configurações")

    with st.expander("Restrições da Carga", expanded=False):
        PESO_MAXIMO_CARGA    = st.number_input("Peso Máximo (kg)",    value=24000)
        CUBAGEM_MAXIMA_CARGA = st.number_input("Cubagem Máxima (m³)", value=90.0)
        PALETES_BASE_MAX     = st.number_input("Máx. Paletes Base",   value=28)
        PALETES_REMONTE_MAX  = st.number_input("Máx. Paletes Remonte",value=28)

    with st.expander("Configurações do Algoritmo Genético", expanded=False):
        POPULACAO  = st.number_input("Tamanho da População", value=300)
        NGEN       = st.number_input("Gerações",             value=1000)
        CXPB       = st.slider("Taxa de Cruzamento", 0.0, 1.0, 0.8)
        MUTPB      = st.slider("Taxa de Mutação",    0.0, 1.0, 0.2)
        TOURNSIZE  = st.number_input("Tournament Size",      value=3)

    with st.expander("📦 Controle de Mix", expanded=False):
        # FIX: usa valores do perfil como default real
        MAX_SKUS_CARGA = st.number_input(
            "Máximo de SKUs por carga",
            value=p["max_skus"]
        )
        PENALIDADE_MIX = st.number_input(
            "Penalidade por SKU excedente",
            value=p["pen_mix"]
        )
        PRIORIZAR_MONOMIX = st.checkbox(
            "Priorizar agrupamento de SKU",
            value=True
        )
        PERCENTUAL_MIN_SKU_DOMINANTE = st.slider(
            "Participação mínima SKU dominante (%)",
            min_value=0, max_value=100,
            value=p["dom"]
        )
        PENALIDADE_SKU_DOMINANTE = st.number_input(
            "Penalidade concentração SKU",
            value=p["pen_dom"]
        )

    with st.expander("🚨 Penalidades", expanded=False):
        PENALIDADE_EXCESSO_PESO      = st.number_input("Peso acima do limite",   value=1000)
        PENALIDADE_EXCESSO_CUBAGEM   = st.number_input("Cubagem acima do limite",value=1000)
        PENALIDADE_REMONTE_INVALIDO  = st.number_input("Remonte inválido",        value=10000)
        PENALIDADE_CARGA_VAZIA       = st.number_input("Carga pouco ocupada",     value=2000)

    with st.expander("📈 Ocupação", expanded=False):
        MIN_PALETES_CARGA   = st.number_input("Mínimo de Paletes",        value=40)
        PENALIDADE_OCUPACAO = st.number_input("Penalidade por pallet faltante", value=2000)

# =======================
# DOWNLOAD DO TEMPLATE
# =======================

template = pd.DataFrame(columns=[
    "SKU", "Paletes a Expedir", "Peso Palete", "M³ Palete", "Peso Remonte"
])
template_buffer = io.BytesIO()
with pd.ExcelWriter(template_buffer, engine="xlsxwriter") as writer:
    template.to_excel(writer, index=False, sheet_name="Template")

st.write("📁 Faça o download do template para preencher os dados dos SKUs:")
st.download_button(
    "📥 Baixar Template",
    data=template_buffer.getvalue(),
    file_name="template_sto_mae.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# =======================
# UPLOAD DO ARQUIVO EXCEL
# =======================

uploaded_file = st.file_uploader(
    "📂 Faça upload do arquivo Excel de SKUs",
    type=["xlsx"]
)

if st.button("🔄 Novo Planejamento"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

# =======================
# LÓGICA PRINCIPAL
# =======================

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file, engine="openpyxl")
    df.columns = df.columns.str.lower().str.strip()

    required_columns = {"sku", "paletes a expedir", "peso palete", "m³ palete", "peso remonte"}
    if not required_columns.issubset(df.columns):
        st.error(f"Arquivo faltando colunas obrigatórias: {required_columns}")
        st.stop()

    df["paletes a expedir"] = df["paletes a expedir"].astype(int)
    df["peso palete"]       = df["peso palete"].astype(float)
    df["m³ palete"]         = df["m³ palete"].astype(float)
    df["peso remonte"]      = df["peso remonte"].astype(float)

    st.success("✅ Arquivo carregado com sucesso!")

    skus              = df["sku"].tolist()
    quantidade_paletes = df["paletes a expedir"].tolist()
    peso_palete_dict   = dict(zip(skus, df["peso palete"]))
    cubagem_palete_dict = dict(zip(skus, df["m³ palete"]))
    peso_remonte_dict  = dict(zip(skus, df["peso remonte"]))
    qtd_paletes_dict   = dict(zip(skus, quantidade_paletes))

    # -------------------------------------------------------
    # FIX: garante que creator não seja redefinido a cada run
    # -------------------------------------------------------
    if "FitnessMin" not in creator.__dict__:
        creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    if "Individual" not in creator.__dict__:
        creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()

    # -------------------------------------------------------
    # GERAÇÃO DE CARGA (heurística construtiva)
    # FIX: aleatoriedade controlada + limite dominante aplicado
    # FIX: remonte tenta todos os candidatos ordenados por peso
    # -------------------------------------------------------

    def gerar_carga(paletes_disponiveis: list) -> dict:
        carga = {"base": [], "remonte": []}
        if not paletes_disponiveis:
            return carga

        contador = Counter(paletes_disponiveis)
        sku_dominante = max(contador, key=contador.get)

        # Limite real aplicado: até 75% da base para o SKU dominante
        limite_dominante = max(1, int(PALETES_BASE_MAX * 0.75))

        # Preenche base com SKU dominante até o limite
        dom_adicionados = 0
        temp_pool = paletes_disponiveis[:]
        for sku in temp_pool:
            if len(carga["base"]) >= PALETES_BASE_MAX:
                break
            if sku == sku_dominante and dom_adicionados < limite_dominante:
                carga["base"].append(sku)
                paletes_disponiveis.remove(sku)
                dom_adicionados += 1

        # Completa base com demais SKUs (aleatoriedade via pop aleatório)
        outros = [s for s in paletes_disponiveis if s != sku_dominante]
        random.shuffle(outros)
        for sku in outros:
            if len(carga["base"]) >= PALETES_BASE_MAX:
                break
            carga["base"].append(sku)
            paletes_disponiveis.remove(sku)

        # Se ainda faltam posições na base, completa com qualquer disponível
        while len(carga["base"]) < PALETES_BASE_MAX and paletes_disponiveis:
            sku = paletes_disponiveis.pop(random.randrange(len(paletes_disponiveis)))
            carga["base"].append(sku)

        # Monta remonte: para cada posição base, tenta o melhor candidato disponível
        # FIX: ordena candidatos por peso desc para maximizar ocupação
        for sku_base in carga["base"]:
            if len(carga["remonte"]) >= PALETES_REMONTE_MAX:
                break
            limite = peso_remonte_dict[sku_base]
            candidatos = sorted(
                [s for s in paletes_disponiveis if peso_palete_dict[s] <= limite],
                key=lambda s: peso_palete_dict[s],
                reverse=True  # prefere paletes mais pesados que cabem
            )
            if candidatos:
                melhor = candidatos[0]
                carga["remonte"].append(melhor)
                paletes_disponiveis.remove(melhor)

        return carga

    # -------------------------------------------------------
    # GERADOR DE INDIVÍDUO
    # FIX: alternância entre modo ordenado e aleatório por geração
    #      garante diversidade sem perder a heurística construtiva
    # -------------------------------------------------------

    def gerar_individuo():
        individuo = []
        paletes_disponiveis = []
        for sku, qtd in zip(skus, quantidade_paletes):
            paletes_disponiveis.extend([sku] * qtd)

        if PRIORIZAR_MONOMIX:
            # 50% chance de ordenar, 50% de embaralhar → diversidade real
            if random.random() < 0.5:
                paletes_disponiveis.sort(key=lambda x: qtd_paletes_dict[x], reverse=True)
            else:
                random.shuffle(paletes_disponiveis)
        else:
            random.shuffle(paletes_disponiveis)

        while paletes_disponiveis:
            carga = gerar_carga(paletes_disponiveis)
            if carga["base"] or carga["remonte"]:
                individuo.append(carga)
            else:
                break  # segurança contra loop infinito

        return individuo

    # -------------------------------------------------------
    # FUNÇÃO DE AVALIAÇÃO (fitness)
    # -------------------------------------------------------

    def avaliar(individuo):
        num_cargas_usadas = len(individuo)
        penalidade = 0.0
        paletes_usados = {sku: 0 for sku in skus}

        for carga in individuo:
            todos = carga["base"] + carga["remonte"]
            if not todos:
                continue

            peso_total    = sum(peso_palete_dict[s]    for s in todos)
            cubagem_total = sum(cubagem_palete_dict[s] for s in todos)

            # Controle de mix
            skus_unicos = len(set(todos))
            if skus_unicos > MAX_SKUS_CARGA:
                penalidade += (skus_unicos - MAX_SKUS_CARGA) * PENALIDADE_MIX

            # Concentração SKU dominante
            contador = Counter(todos)
            if contador:
                qtd_principal = max(contador.values())
                total_paletes = sum(contador.values())
                pct_principal = qtd_principal / total_paletes
                pct_minimo    = PERCENTUAL_MIN_SKU_DOMINANTE / 100
                if pct_principal < pct_minimo:
                    deficit = pct_minimo - pct_principal
                    penalidade += deficit * 100 * PENALIDADE_SKU_DOMINANTE

            # Peso e cubagem
            if peso_total > PESO_MAXIMO_CARGA:
                penalidade += (peso_total - PESO_MAXIMO_CARGA) * PENALIDADE_EXCESSO_PESO
            if cubagem_total > CUBAGEM_MAXIMA_CARGA:
                penalidade += (cubagem_total - CUBAGEM_MAXIMA_CARGA) * PENALIDADE_EXCESSO_CUBAGEM

            # Limites de paletes
            if len(carga["base"]) > PALETES_BASE_MAX or len(carga["remonte"]) > PALETES_REMONTE_MAX:
                penalidade += PENALIDADE_REMONTE_INVALIDO

            # Validade do remonte par-a-par
            for sku_b, sku_r in zip(carga["base"], carga["remonte"]):
                if peso_palete_dict[sku_r] > peso_remonte_dict[sku_b]:
                    penalidade += PENALIDADE_REMONTE_INVALIDO

            # Carga pouco ocupada no remonte
            diff_remonte = PALETES_REMONTE_MAX - len(carga["remonte"])
            if diff_remonte > 0:
                penalidade += diff_remonte * PENALIDADE_CARGA_VAZIA

            # Ocupação mínima total
            total_paletes_carga = len(todos)
            if total_paletes_carga < MIN_PALETES_CARGA:
                penalidade += (MIN_PALETES_CARGA - total_paletes_carga) * PENALIDADE_OCUPACAO

            for sku in todos:
                paletes_usados[sku] += 1

        # Penalidade por desvio de quantidade
        for sku, qtd in zip(skus, quantidade_paletes):
            usado = paletes_usados[sku]
            if usado > qtd:
                excesso = usado - qtd
                if excesso <= qtd * 0.05:
                    penalidade += excesso * 500
                else:
                    penalidade += (excesso - qtd * 0.05) * 10000
            elif usado < qtd:
                penalidade += (qtd - usado) * 1000

        return (num_cargas_usadas + penalidade,)

    # -------------------------------------------------------
    # OPERADORES GENÉTICOS CUSTOMIZADOS
    # FIX: operadores compatíveis com lista de dicionários
    # -------------------------------------------------------

    def crossover_cargas(ind1, ind2):
        """Troca um bloco aleatório de cargas entre dois indivíduos."""
        if len(ind1) < 2 or len(ind2) < 2:
            return ind1, ind2
        cx1 = random.randint(1, len(ind1) - 1)
        cx2 = random.randint(1, len(ind2) - 1)
        ind1[cx1:], ind2[cx2:] = ind2[cx2:], ind1[cx1:]
        return ind1, ind2

    def mutacao_realocar(individuo):
        """
        Mutação: retira paletes de cargas aleatórias e os redistribui.
        Isso reduz sobras e melhora o aproveitamento.
        """
        if len(individuo) < 2:
            return (individuo,)

        # Escolhe uma carga aleatória para "desmontar" parcialmente
        idx = random.randrange(len(individuo))
        carga = individuo[idx]

        # Extrai paletes soltos (até 30% do conteúdo da carga)
        todos = carga["base"] + carga["remonte"]
        n_extrair = max(1, int(len(todos) * 0.3))
        random.shuffle(todos)
        extraidos = todos[:n_extrair]
        restantes = todos[n_extrair:]

        # Reconstrói a carga com os restantes
        individuo[idx] = {"base": restantes[:int(PALETES_BASE_MAX)], "remonte": []}

        # Tenta reinserir os extraídos em outras cargas com espaço
        for sku in extraidos:
            inserido = False
            cargas_com_espaco = [
                i for i, c in enumerate(individuo)
                if i != idx and len(c["base"]) < PALETES_BASE_MAX
            ]
            random.shuffle(cargas_com_espaco)
            for ci in cargas_com_espaco:
                c = individuo[ci]
                peso_atual = sum(peso_palete_dict[s] for s in c["base"] + c["remonte"])
                if (
                    len(c["base"]) < PALETES_BASE_MAX
                    and peso_atual + peso_palete_dict[sku] <= PESO_MAXIMO_CARGA
                ):
                    c["base"].append(sku)
                    inserido = True
                    break
            if not inserido:
                # Cria nova carga mínima se não couber em lugar algum
                individuo.append({"base": [sku], "remonte": []})

        # Remove cargas vazias
        individuo[:] = [c for c in individuo if c["base"] or c["remonte"]]

        return (individuo,)

    # -------------------------------------------------------
    # REGISTRO NO TOOLBOX
    # -------------------------------------------------------

    toolbox.register("individuo", tools.initIterate, creator.Individual, gerar_individuo)
    toolbox.register("populacao", tools.initRepeat, list, toolbox.individuo)
    toolbox.register("evaluate", avaliar)
    toolbox.register("mate",    crossover_cargas)
    toolbox.register("mutate",  mutacao_realocar)
    toolbox.register("select",  tools.selTournament, tournsize=int(TOURNSIZE))

    # -------------------------------------------------------
    # BOTÃO: INICIAR OTIMIZAÇÃO
    # -------------------------------------------------------

    if st.button("🚀 Iniciar Otimização"):
        with st.spinner("⏳ Executando otimização... isso pode levar alguns minutos..."):

            populacao = toolbox.populacao(n=int(POPULACAO))
            hof = tools.HallOfFame(1)  # FIX: elitismo — guarda o melhor indivíduo

            stats = tools.Statistics(lambda ind: ind.fitness.values)
            stats.register("min", min)

            # FIX: eaMuPlusLambda com elitismo (mu + lambda)
            # mantém o melhor indivíduo entre gerações
            algorithms.eaMuPlusLambda(
                populacao,
                toolbox,
                mu=int(POPULACAO),
                lambda_=int(POPULACAO),
                cxpb=CXPB,
                mutpb=MUTPB,
                ngen=int(NGEN),
                stats=stats,
                halloffame=hof,
                verbose=False,
            )

            melhor_individuo = hof[0]

            # -------------------------------------------------------
            # PÓS-PROCESSAMENTO: redistribui sobras residuais
            # FIX: garante que nenhum palete fique de fora
            # -------------------------------------------------------

            paletes_planejados = {sku: 0 for sku in skus}
            for carga in melhor_individuo:
                for sku in carga["base"] + carga["remonte"]:
                    paletes_planejados[sku] += 1

            sobras = []
            for sku, qtd in zip(skus, quantidade_paletes):
                diff = qtd - paletes_planejados[sku]
                if diff > 0:
                    sobras.extend([sku] * diff)

            # Tenta encaixar sobras em cargas existentes com espaço
            for sku in sobras[:]:
                for carga in melhor_individuo:
                    peso_atual = sum(
                        peso_palete_dict[s]
                        for s in carga["base"] + carga["remonte"]
                    )
                    if (
                        len(carga["base"]) < PALETES_BASE_MAX
                        and peso_atual + peso_palete_dict[sku] <= PESO_MAXIMO_CARGA
                    ):
                        carga["base"].append(sku)
                        sobras.remove(sku)
                        break

            # Cria nova carga para sobras que não couberem em lugar algum
            if sobras:
                pool = sobras[:]
                while pool:
                    nova_carga = gerar_carga(pool)
                    if nova_carga["base"] or nova_carga["remonte"]:
                        melhor_individuo.append(nova_carga)
                    else:
                        break

            st.success(f"✅ Otimização concluída! Cargas geradas: {len(melhor_individuo)}")

            # Alerta de sobras residuais (após pós-processamento)
            paletes_final = {sku: 0 for sku in skus}
            for carga in melhor_individuo:
                for sku in carga["base"] + carga["remonte"]:
                    paletes_final[sku] += 1
            sobras_finais = {
                sku: qtd - paletes_final[sku]
                for sku, qtd in zip(skus, quantidade_paletes)
                if qtd - paletes_final[sku] > 0
            }
            if sobras_finais:
                st.warning(
                    f"⚠️ {sum(sobras_finais.values())} paletes não alocados: {sobras_finais}. "
                    "Considere aumentar gerações ou relaxar penalidades."
                )
            else:
                st.success("🎯 Todos os paletes foram alocados!")

        # -------------------------------------------------------
        # RESULTADOS
        # -------------------------------------------------------

        PALETES_MAX_CARGA = int(PALETES_BASE_MAX) + int(PALETES_REMONTE_MAX)

        resumo  = []
        detalhe = []

        for i, carga in enumerate(melhor_individuo):
            todos       = carga["base"] + carga["remonte"]
            n_paletes   = len(todos)
            peso        = sum(peso_palete_dict[s]    for s in todos)
            m3          = sum(cubagem_palete_dict[s] for s in todos)

            resumo.append({
                "Carga":              f"Carga {i+1}",
                "Paletes Base":       len(carga["base"]),
                "Paletes Remonte":    len(carga["remonte"]),
                "Total Paletes":      n_paletes,
                "% Ocup. Paletes":    round(n_paletes / PALETES_MAX_CARGA * 100, 1),
                "Peso Total (kg)":    round(peso, 2),
                "% Ocup. Peso":       round(peso / PESO_MAXIMO_CARGA * 100, 1),
                "M³ Total":           round(m3, 2),
                "% Ocup. M³":         round(m3 / CUBAGEM_MAXIMA_CARGA * 100, 1),
            })

            for sku in carga["base"]:
                detalhe.append({
                    "Carga":       f"Carga {i+1}",
                    "SKU":         sku,
                    "Posição":     "Base",
                    "Peso Palete": peso_palete_dict[sku],
                    "M³ Palete":   cubagem_palete_dict[sku],
                })
            for sku in carga["remonte"]:
                detalhe.append({
                    "Carga":       f"Carga {i+1}",
                    "SKU":         sku,
                    "Posição":     "Remonte",
                    "Peso Palete": peso_palete_dict[sku],
                    "M³ Palete":   cubagem_palete_dict[sku],
                })

        df_resumo = pd.DataFrame(resumo)
        df_raw    = pd.DataFrame(detalhe)

        df_detalhe = df_raw.groupby(
            ["Carga", "SKU", "Posição"]
        ).agg(
            Quantidade_Paletes=("SKU",        "count"),
            Peso_Total        =("Peso Palete", "sum"),
            Cubagem_Total     =("M³ Palete",   "sum"),
        ).reset_index()

        # -------------------------------------------------------
        # ABA: RESUMO GERAL POR SKU (paletes disponíveis vs usados vs sobra)
        # -------------------------------------------------------

        paletes_alocados = {sku: 0 for sku in skus}
        for carga in melhor_individuo:
            for sku in carga["base"] + carga["remonte"]:
                if sku in paletes_alocados:
                    paletes_alocados[sku] += 1

        resumo_sku = []
        for sku, qtd_disp in zip(skus, quantidade_paletes):
            alocado = paletes_alocados[sku]
            sobra   = qtd_disp - alocado
            resumo_sku.append({
                "SKU":                  sku,
                "Paletes Disponíveis":  qtd_disp,
                "Paletes Alocados":     alocado,
                "Sobra":                sobra,
                "% Utilizado":          round(alocado / qtd_disp * 100, 1) if qtd_disp > 0 else 0.0,
            })

        # Linha de totais
        tot_disp   = sum(r["Paletes Disponíveis"] for r in resumo_sku)
        tot_aloc   = sum(r["Paletes Alocados"]    for r in resumo_sku)
        tot_sobra  = sum(r["Sobra"]               for r in resumo_sku)
        resumo_sku.append({
            "SKU":                 "TOTAL",
            "Paletes Disponíveis": tot_disp,
            "Paletes Alocados":    tot_aloc,
            "Sobra":               tot_sobra,
            "% Utilizado":         round(tot_aloc / tot_disp * 100, 1) if tot_disp > 0 else 0.0,
        })

        df_resumo_sku = pd.DataFrame(resumo_sku)

        # -------------------------------------------------------
        # EXIBIÇÃO NA TELA
        # -------------------------------------------------------

        st.subheader("📋 Resumo das Cargas")
        st.dataframe(df_resumo, use_container_width=True)

        st.subheader("📊 Aproveitamento por SKU")
        st.dataframe(df_resumo_sku, use_container_width=True)

        st.subheader("📦 Detalhe por SKU / Carga")
        st.dataframe(df_detalhe, use_container_width=True)

        # -------------------------------------------------------
        # EXPORTAÇÃO EXCEL COM FORMATAÇÃO
        # -------------------------------------------------------

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            wb = writer.book

            # Formatos
            fmt_header   = wb.add_format({"bold": True, "bg_color": "#1F4E79", "font_color": "#FFFFFF", "border": 1, "align": "center", "valign": "vcenter"})
            fmt_total    = wb.add_format({"bold": True, "bg_color": "#D6E4F0", "border": 1})
            fmt_pct      = wb.add_format({"num_format": "0.0\"%\"", "border": 1})
            fmt_num      = wb.add_format({"num_format": "#,##0.00", "border": 1})
            fmt_int      = wb.add_format({"num_format": "#,##0",    "border": 1})
            fmt_cell     = wb.add_format({"border": 1})
            fmt_pct_tot  = wb.add_format({"bold": True, "bg_color": "#D6E4F0", "num_format": "0.0\"%\"", "border": 1})
            fmt_num_tot  = wb.add_format({"bold": True, "bg_color": "#D6E4F0", "num_format": "#,##0.00", "border": 1})
            fmt_int_tot  = wb.add_format({"bold": True, "bg_color": "#D6E4F0", "num_format": "#,##0",    "border": 1})

            def write_header(ws, cols):
                for c, name in enumerate(cols):
                    ws.write(0, c, name, fmt_header)

            # ── Aba Resumo ──────────────────────────────────────
            df_resumo.to_excel(writer, sheet_name="Resumo", index=False, startrow=1, header=False)
            ws_res = writer.sheets["Resumo"]
            cols_res = list(df_resumo.columns)
            write_header(ws_res, cols_res)

            pct_cols_res  = {"% Ocup. Paletes", "% Ocup. Peso", "% Ocup. M³"}
            num_cols_res  = {"Peso Total (kg)", "M³ Total"}
            int_cols_res  = {"Paletes Base", "Paletes Remonte", "Total Paletes"}

            for r_idx, row in df_resumo.iterrows():
                for c_idx, col in enumerate(cols_res):
                    val = row[col]
                    if col in pct_cols_res:
                        ws_res.write(r_idx + 1, c_idx, val, fmt_pct)
                    elif col in num_cols_res:
                        ws_res.write(r_idx + 1, c_idx, val, fmt_num)
                    elif col in int_cols_res:
                        ws_res.write(r_idx + 1, c_idx, val, fmt_int)
                    else:
                        ws_res.write(r_idx + 1, c_idx, val, fmt_cell)

            ws_res.set_column(0, 0, 12)
            ws_res.set_column(1, 8, 18)
            ws_res.freeze_panes(1, 0)

            # ── Aba Aproveitamento SKU ───────────────────────────
            df_resumo_sku.to_excel(writer, sheet_name="Aproveitamento SKU", index=False, startrow=1, header=False)
            ws_sku = writer.sheets["Aproveitamento SKU"]
            cols_sku = list(df_resumo_sku.columns)
            write_header(ws_sku, cols_sku)

            for r_idx, row in df_resumo_sku.iterrows():
                is_total = row["SKU"] == "TOTAL"
                for c_idx, col in enumerate(cols_sku):
                    val = row[col]
                    if is_total:
                        fmt = fmt_pct_tot if col == "% Utilizado" else (fmt_num_tot if isinstance(val, float) else fmt_int_tot)
                    else:
                        fmt = fmt_pct if col == "% Utilizado" else (fmt_num if isinstance(val, float) and col not in {"Paletes Disponíveis","Paletes Alocados","Sobra"} else fmt_int if col != "SKU" else fmt_cell)
                    ws_sku.write(r_idx + 1, c_idx, val, fmt)

            ws_sku.set_column(0, 0, 20)
            ws_sku.set_column(1, 4, 22)
            ws_sku.freeze_panes(1, 0)

            # ── Aba Detalhe ──────────────────────────────────────
            df_detalhe.to_excel(writer, sheet_name="Detalhe", index=False, startrow=1, header=False)
            ws_det = writer.sheets["Detalhe"]
            cols_det = list(df_detalhe.columns)
            write_header(ws_det, cols_det)

            for r_idx, row in df_detalhe.iterrows():
                for c_idx, col in enumerate(cols_det):
                    val = row[col]
                    if col in {"Peso_Total", "Cubagem_Total"}:
                        ws_det.write(r_idx + 1, c_idx, val, fmt_num)
                    elif col == "Quantidade_Paletes":
                        ws_det.write(r_idx + 1, c_idx, val, fmt_int)
                    else:
                        ws_det.write(r_idx + 1, c_idx, val, fmt_cell)

            ws_det.set_column(0, 0, 12)
            ws_det.set_column(1, 5, 20)
            ws_det.freeze_panes(1, 0)

        st.download_button(
            "📥 Baixar Excel",
            data=output.getvalue(),
            file_name="cargas_otimizadas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
