# streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
import random
import deap
from deap import base, creator, tools, algorithms
import io


# =======================
# CONFIG GERAL
# =======================

st.set_page_config(
    page_title="Gerador de Cargas - STO Mãe v1 - by: Rafael Góis - 14.Abril.2024",
    layout="wide"
)

st.title("🚚 Gerador de Cargas - STO Mãe v1")
st.write(
    """
    **Desenvolvedor:** Rafael Góis - 14.Abril.2024
    \\
    **Objetivo:** Maximiza a distribuição de paletes em cargas,
    respeitando limites de peso, volume e restrições de remonte.
    \\
    **Descrição:** Esta aplicação utiliza algoritmos genéticos para otimizar a alocação de paletes em cargas,
    garantindo que cada carga atenda às restrições do negócio.
    """
)

# =======================
# PARÂMETROS GLOBAIS
# =======================

PESO_MAXIMO_CARGA = 24000  # kg
CUBAGEM_MAXIMA_CARGA = 90  # m³
PALETES_MAXIMOS_CARGA = 56  # 28 base + 28 remonte

# =======================
# Upload do arquivo Excel
# =======================

uploaded_file = st.file_uploader(
    "📂 Faça upload do arquivo Excel de SKUs",
    type=["xlsx"]
)

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file, engine="openpyxl")
    df.columns = df.columns.str.lower().str.strip()

    required_columns = {"sku", "paletes a expedir", "peso palete", "m³ palete", "peso remonte"}
    if not required_columns.issubset(df.columns):
        st.error(f"Arquivo faltando colunas obrigatórias: {required_columns}")
        st.stop()

    # Normaliza tipos
    df["paletes a expedir"] = df["paletes a expedir"].astype(int)
    df["peso palete"] = df["peso palete"].astype(float)
    df["m³ palete"] = df["m³ palete"].astype(float)
    df["peso remonte"] = df["peso remonte"].astype(float)

    st.success("✅ Arquivo carregado com sucesso!")

    skus = df["sku"].tolist()
    quantidade_paletes = df["paletes a expedir"].tolist()
    peso_palete_dict = dict(zip(skus, df["peso palete"]))
    cubagem_palete_dict = dict(zip(skus, df["m³ palete"]))
    peso_remonte_dict = dict(zip(skus, df["peso remonte"]))

    # =======================
    # Algoritmo Genético (DEAP)
    # =======================

    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMin)
    toolbox = base.Toolbox()

    def gerar_carga(paletes_disponiveis):
        carga = {"base": [], "remonte": []}
        while len(carga["base"]) < 28 and paletes_disponiveis:
            sku = paletes_disponiveis.pop()
            carga["base"].append(sku)

        paletes_leves = [sku for sku in paletes_disponiveis if peso_palete_dict[sku] <= 350]
        paletes_pesados = [sku for sku in paletes_disponiveis if peso_palete_dict[sku] > 350]

        for sku_base in carga["base"]:
            while len(carga["remonte"]) < 28 and paletes_leves:
                sku = paletes_leves.pop()
                if peso_palete_dict[sku] <= peso_remonte_dict[sku_base]:
                    carga["remonte"].append(sku)

        for sku_base in carga["base"]:
            while len(carga["remonte"]) < 28 and paletes_pesados:
                sku = paletes_pesados.pop()
                if peso_palete_dict[sku] <= peso_remonte_dict[sku_base]:
                    carga["remonte"].append(sku)

        return carga

    def gerar_individuo():
        individuo = []
        paletes_disponiveis = []
        for sku, qtd in zip(skus, quantidade_paletes):
            paletes_disponiveis.extend([sku] * qtd)
        random.shuffle(paletes_disponiveis)
        while paletes_disponiveis:
            carga = gerar_carga(paletes_disponiveis.copy())
            individuo.append(carga)
            for sku in carga["base"] + carga["remonte"]:
                if sku in paletes_disponiveis:
                    paletes_disponiveis.remove(sku)
        return individuo

    def avaliar(individuo):
        num_cargas_usadas = len(individuo)
        penalidade = 0
        paletes_usados = {sku: 0 for sku in skus}

        for carga in individuo:
            if not carga["base"] and not carga["remonte"]:
                continue

            peso_total = sum(peso_palete_dict[sku] for sku in carga["base"]) + \
                         sum(peso_palete_dict[sku] for sku in carga["remonte"])
            cubagem_total = sum(cubagem_palete_dict[sku] for sku in carga["base"]) + \
                            sum(cubagem_palete_dict[sku] for sku in carga["remonte"])

            if peso_total > PESO_MAXIMO_CARGA:
                penalidade += (peso_total - PESO_MAXIMO_CARGA) * 1000
            if cubagem_total > CUBAGEM_MAXIMA_CARGA:
                penalidade += (cubagem_total - CUBAGEM_MAXIMA_CARGA) * 1000
            if len(carga["base"]) > 28 or len(carga["remonte"]) > 28:
                penalidade += 10000

            for sku_base, sku_remonte in zip(carga["base"], carga["remonte"]):
                if peso_palete_dict[sku_remonte] > peso_remonte_dict[sku_base]:
                    penalidade += 10000

            if len(carga["remonte"]) < 28:
                penalidade += (28 - len(carga["remonte"])) * 3000

            if len(carga["base"]) + len(carga["remonte"]) < 40:
                penalidade += (40 - (len(carga["base"]) + len(carga["remonte"]))) * 2000

            for sku in carga["base"] + carga["remonte"]:
                paletes_usados[sku] += 1

        for sku, qtd in zip(skus, quantidade_paletes):
            if paletes_usados[sku] > qtd:
                excesso = paletes_usados[sku] - qtd
                if excesso <= qtd * 0.05:
                    penalidade += excesso * 500
                else:
                    penalidade += (excesso - qtd * 0.05) * 10000
            elif paletes_usados[sku] < qtd:
                penalidade += (qtd - paletes_usados[sku]) * 1000

        return (num_cargas_usadas + penalidade,)

    toolbox.register("individuo", tools.initIterate, creator.Individual, gerar_individuo)
    toolbox.register("populacao", tools.initRepeat, list, toolbox.individuo)
    toolbox.register("evaluate", avaliar)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutShuffleIndexes, indpb=0.2)
    toolbox.register("select", tools.selTournament, tournsize=3)

    # =======================
    # Botão para executar otimização
    # =======================
    if st.button("🚀 Iniciar Otimização"):
        with st.spinner("⏳ Executando otimização... isso pode levar alguns minutos..."):
            populacao = toolbox.populacao(n=50)
            ngen = 100
            cxpb = 0.8
            mutpb = 0.2

            algorithms.eaSimple(populacao, toolbox, cxpb, mutpb, ngen, verbose=False)

            melhor_individuo = tools.selBest(populacao, k=1)[0]

            # ✅ Tudo dentro do mesmo bloco!
            st.success(f"✅ Otimização concluída! Cargas criadas: {len(melhor_individuo)}")

            resumo = []
            detalhe = []

            for i, carga in enumerate(melhor_individuo):
                peso = sum(peso_palete_dict[sku] for sku in carga["base"] + carga["remonte"])
                m3 = sum(cubagem_palete_dict[sku] for sku in carga["base"] + carga["remonte"])
                resumo.append({
                    "Carga": f"Carga {i+1}",
                    "Paletes Base": len(carga["base"]),
                    "Paletes Remonte": len(carga["remonte"]),
                    "Peso Total": peso,
                    "M³ Total": m3
                })

                for sku in carga["base"]:
                    detalhe.append({
                        "Carga": f"Carga {i+1}",
                        "SKU": sku,
                        "Posição": "Base",
                        "Peso Palete": peso_palete_dict[sku],
                        "M³ Palete": cubagem_palete_dict[sku]
                    })
                for sku in carga["remonte"]:
                    detalhe.append({
                        "Carga": f"Carga {i+1}",
                        "SKU": sku,
                        "Posição": "Remonte",
                        "Peso Palete": peso_palete_dict[sku],
                        "M³ Palete": cubagem_palete_dict[sku]
                    })

        df_resumo = pd.DataFrame(resumo)
        df_raw = pd.DataFrame(detalhe)

        df_detalhe = df_raw.groupby(
            ['Carga', 'SKU', 'Posição']
        ).agg(
            Quantidade_Paletes=('SKU', 'count'),
            Peso_Total=('Peso Palete', 'sum'),
            Cubagem_Total=('M³ Palete', 'sum')
        ).reset_index()

        st.dataframe(df_resumo)
        st.dataframe(df_detalhe)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_resumo.to_excel(writer, sheet_name='Resumo', index=False)
            df_detalhe.to_excel(writer, sheet_name='Detalhe', index=False)

        st.download_button(
            "📥 Baixar Excel",
            data=output.getvalue(),
            file_name="cargas_otimizadas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
