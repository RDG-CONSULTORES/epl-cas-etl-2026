
import streamlit as st
import pandas as pd
from generativa.generador import generar_resumen

st.set_page_config(page_title="IA Generativa - Supervisiones", layout="wide")

df = pd.read_csv("data/supervisiones_long_format.csv")

trimestres = df['trimestre'].unique()
grupos = df['grupo'].unique()

st.sidebar.title("Filtros")
trimestre = st.sidebar.selectbox("Selecciona un trimestre", sorted(trimestres))
grupo = st.sidebar.selectbox("Selecciona un grupo", sorted(grupos))

df_filtrado = df[(df['trimestre'] == trimestre) & (df['grupo'] == grupo)]

st.title(f"Indicadores del Grupo {grupo} - {trimestre}")
st.dataframe(df_filtrado)

if st.button("Generar resumen con IA"):
    resumen = generar_resumen(df_filtrado, grupo, trimestre)
    st.subheader("Resumen Generado")
    st.write(resumen)
