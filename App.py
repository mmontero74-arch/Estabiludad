import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Simulador Estabilidad LME", layout="wide", page_icon="🎯")

st.title("🎯 Dashboard Híbrido: Estabilidad y Cierre de Año")
st.markdown("Integración total: Histórico exacto desde Power BI + Proyección predictiva Q4 desde la Sábana.")

# 1. ZONA DE CARGA DE LOS 2 ARCHIVOS
c1, c2 = st.columns(2)
file_sabana = c1.file_uploader("1. Sábana de Datos (Excel)", type=["xlsx"])
file_pbi26 = c2.file_uploader("2. Datos PBI 2026", type=["xlsx"])

COLECTIVOS = ['VENDEDOR/A', 'VENDEDOR/A PROYECTO', 'ASESOR/A PROFESIONAL', 'COORDINADOR/A PROYECTOS CLIENTE']

st.divider()

if file_sabana and file_pbi26:
    try:
        with st.spinner("Fusionando Sábana con Motor Power BI..."):
            
            # ==========================================
            # A. PROCESAMIENTO DE LA SÁBANA
            # ==========================================
            df = pd.read_excel(file_sabana, sheet_name=0)
            df.columns = df.columns.str.strip()
            
            excluded_codes = ['00', '000', '300', '402', '410', '420', '502', '510', '520', '540', '330']
            if 'Id. Contrato legal' in df.columns:
                df['Id. Contrato legal'] = df['Id. Contrato legal'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                df_indef = df[~df['Id. Contrato legal'].isin(excluded_codes)].copy()
            else:
                df_indef = df.copy() 
                
            df_indef['Fecha alta'] = pd.to_datetime(df_indef['Fecha alta'], errors='coerce')
            df_indef['Fecha fin'] = pd.to_datetime(df_indef['Fecha fin'], errors='coerce')
            
            if 'Id RH' in df_indef.columns:
                df_indef['Id RH'] = df_indef['Id RH'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
            traslados_efectivos = {
                '196704': '2026-06-01', '185838': '2025-11-01',
                '211733': '2026-06-01', '205588': '2025-03-01'
            }
            for emp_id, fecha_efectiva in traslados_efectivos.items():
                df_indef.loc[df_indef['Id RH'] == emp_id, 'Fecha alta'] = pd.to_datetime(fecha_efectiva)

            if 'Causa Baja' in df_indef.columns:
                df_indef['Causa Baja'] = df_indef['Causa Baja'].astype(str).str.strip().str.upper()
                df_indef.loc[df_indef['Causa Baja'] == 'NAN', 'Causa Baja'] = ''
                df_indef.loc[df_indef['Causa Baja'] == 'AGOTAMIENTO IT', 'Fecha fin'] = pd.NaT
            
            hoy = pd.to_datetime('today')
            df_indef['Antigüedad_Años'] = (hoy - df_indef['Fecha alta']).dt.days / 365.25

            solo_estrategicos = st.toggle("🎯 Filtrar solo Colectivo Estratégico (Ventas/Asesores/Coordinadores)")
            
            if 'Descripción Puesto' in df_indef.columns:
                df_indef['Descripción Puesto'] = df_indef['Descripción Puesto'].astype(str).str.strip().str.upper()
                df_indef['Descripción sección'] = df_indef['Descripción sección'].astype(str).str.strip().str.upper()
            
            if solo_estrategicos:
                df_indef = df_indef[df_indef['Descripción Puesto'].isin(COLECTIVOS)]
                objetivo_chart = 80
            else:
                objetivo_chart = 86

            # CREACIÓN DE TABS
            tab1, tab2, tab3 = st.tabs(["📊 Dashboard y Simulador", "👥 Análisis Demográfico y Fugas", "ℹ️ Info y Metodología"])

            with tab1:
                chart_and_table_container = st.container()
                risk_container = st.container()

                # TABLA DE RIESGO
                start_q4 = pd.to_datetime('2025-09-01') 
                end_q4 = pd.to_datetime('2025-12-31')
                activos_hoy = df_indef[df_indef['Fecha fin'].isna() | (df_indef['Fecha fin'] > hoy)]
                alertas_df = activos_hoy[(activos_hoy['Fecha alta'] >= start_q4) & (activos_hoy['Fecha alta'] <= end_q4)].copy()
                alertas_df = alertas_df.drop_duplicates(subset=['Id RH']).sort_values('Fecha alta')

                with risk_container:
                    st.divider()
                    st.subheader("⚠️ Colaboradores que cumplirán 1 año de antigüedad antes del 31 de Diciembre")
                    st.markdown("Marca la casilla **'Simular Baja'** para ver cómo impactaría su salida en la curva de estabilidad.")
                    
                    display_df = alertas_df[['Id RH', 'Nombre', 'Apellidos', 'Descripción Puesto', 'Descripción sección', 'Fecha alta']].copy()
                    display_df.insert(0, 'Simular Baja', False)
                    display_df['Cumple 1 Año'] = (display_df['Fecha alta'] + pd.DateOffset(years=1)).dt.strftime('%d/%m/%Y')
                    display_df['Fecha alta'] = display_df['Fecha alta'].dt.strftime('%d/%m/%Y')
                    
                    edited_df = st.data_editor(
                        display_df, hide_index=True, use_container_width=True,
                        disabled=['Id RH', 'Nombre', 'Apellidos', 'Descripción Puesto', 'Descripción sección', 'Fecha alta', 'Cumple 1 Año']
                    )
                    bajas_simuladas = edited_df[edited_df['Simular Baja'] == True]['Id RH'].tolist()
                
                df_sim = df_indef.copy()
                if bajas_simuladas:
                    df_sim.loc[df_sim['Id RH'].isin(bajas_simuladas), 'Fecha fin'] = hoy

                # PROCESAMIENTO PBI GENERAL
                df_pbi = pd.read_excel(file_pbi26).dropna(subset=['Mes'])
                df_pbi['SECCION'] = df_pbi['SECCION'].astype(str).str.strip().str.upper()
                df_pbi['PUESTO'] = df_pbi['PUESTO'].astype(str).str.strip().str.upper()
                
                if solo_estrategicos:
                    df_pbi = df_pbi[df_pbi['PUESTO'].isin(COLECTIVOS)]
                    
                df_pbi['PLANTILLA ACTIVA N-1'] = pd.to_numeric(df_pbi['PLANTILLA ACTIVA N-1'], errors='coerce').fillna(0)
                df_pbi['PLANTILLA ANTIGUEDAD > 1 AÑO'] = pd.to_numeric(df_pbi['PLANTILLA ANTIGUEDAD > 1 AÑO'], errors='coerce').fillna(0)
                
                pbi_grp = df_pbi.groupby('Mes')[['PLANTILLA ACTIVA N-1', 'PLANTILLA ANTIGUEDAD > 1 AÑO']].sum().reset_index()
                meses_map = {'enero':'Ene', 'febrero':'Feb', 'marzo':'Mar', 'abril':'Abr', 'mayo':'May', 'junio':'Jun', 'julio':'Jul', 'agosto':'Ago', 'septiembre':'Sep', 'octubre':'Oct', 'noviembre':'Nov', 'diciembre':'Dic'}
                pbi_grp['Mes_corto'] = pbi_grp['Mes'].astype(str).str.strip().str.lower().map(meses_map)
                pbi_dict = {row['Mes_corto']: {'Base': row['PLANTILLA ACTIVA N-1'], 'Retenidos': row['PLANTILLA ANTIGUEDAD > 1 AÑO']} 
                            for _, row in pbi_grp.iterrows() if pd.notnull(row['Mes_corto']) and row['PLANTILLA ACTIVA N-1'] > 0}

                def calc_mes_sabana(df_eval, year, month):
                    eom_prev = pd.to_datetime(f"{year-1}-{month:02d}-01") + pd.offsets.MonthEnd(1)
                    base_df = df_eval[(df_eval['Fecha alta'] <= eom_prev) & (df_eval['Fecha fin'].isna() | (df_eval['Fecha fin'] >= eom_prev))]
                    base_ids = set(base_df['Id RH'])
                    if not base_ids: return 0, 0
                    eom_curr = pd.to_datetime(f"{year}-{month:02d}-01") + pd.offsets.MonthEnd(1)
                    ret_df = df_eval[(df_eval['Id RH'].isin(base_ids)) & (df_eval['Fecha fin'].isna() | (df_eval['Fecha fin'] >= eom_curr))]
                    return len(base_ids), len(set(ret_df['Id RH']))

                meses_orden = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
                data_mensual = []
                for i, mes in enumerate(meses_orden, start=1):
                    if i <= 10 and mes in pbi_dict:
                        b, r = pbi_dict[mes]['Base'], pbi_dict[mes]['Retenidos']
                        estado = "Consolidado PBI"
                    else:
                        b, r = calc_mes_sabana(df_sim, 2026, i)
                        estado = "Proyección Q4"
                    p = (r / b * 100) if b > 0 else 0
                    data_mensual.append({'Mes': mes, 'Num_Mes': i, 'Base': b, 'Retenidos': r, 'Estabilidad (%)': p, 'Estado': estado})
                
                df_resumen = pd.DataFrame(data_mensual)

                with chart_and_table_container:
                    st.header("📈 Curva de Aterrizaje a Diciembre 2026")
                    fig = go.Figure()
                    df_plot = df_resumen[df_resumen['Num_Mes'] >= 1] 
                    fig.add_trace(go.Scatter(x=df_plot['Mes'], y=df_plot['Estabilidad (%)'], mode='lines+markers+text', 
                                             text=df_plot['Estabilidad (%)'].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else ""),
                                             textposition="top center", name='Estabilidad', line=dict(color='#006400', width=4)))
                    fig.add_hline(y=objetivo_chart, line_dash="dash", line_color="red", annotation_text=f"Objetivo ({objetivo_chart}%)")
                    
                    mes_actual_idx = hoy.month - 1
                    if mes_actual_idx < 12:
                        fig.add_vline(x=meses_orden[mes_actual_idx], line_width=2, line_dash="dot", line_color="gray")
                        fig.add_annotation(x=meses_orden[mes_actual_idx], y=1.05, yref='paper', text="Inicio Simulación ->", showarrow=False, xanchor="left", font=dict(color="gray"))

                    fig.update_layout(yaxis_title="Porcentaje (%)", hovermode="x unified")
                    st.plotly_chart(fig, use_container_width=True)

                    with st.expander("📊 Ver Tabla Detallada Mensual", expanded=True):
                        st.dataframe(df_resumen.style.format({'Estabilidad (%)': '{:.2f}%'}))

            with tab2:
                # ==========================================
                # E. ANÁLISIS DEL ÚLTIMO MES REAL
                # ==========================================
                meses_completos = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                df_pbi['Mes_cat'] = pd.Categorical(df_pbi['Mes'].str.lower(), categories=meses_completos, ordered=True)
                ultimo_mes_pbi = df_pbi['Mes_cat'].max()
                
                st.header(f"🔍 Análisis de Estabilidad y Bajas (Mes Real: {str(ultimo_mes_pbi).capitalize()})")
                st.markdown(f"Datos oficiales de **Power BI** del último mes consolidado ({ultimo_mes_pbi}).")
                
                df_pbi_ultimo = df_pbi[df_pbi['Mes_cat'] == ultimo_mes_pbi]
                
                c_a1, c_a2 = st.columns(2)
                
                with c_a1:
                    sec_pbi = df_pbi_ultimo.groupby('SECCION')[['PLANTILLA ACTIVA N-1', 'PLANTILLA ANTIGUEDAD > 1 AÑO']].sum().reset_index()
                    sec_pbi['% Estabilidad'] = (sec_pbi['PLANTILLA ANTIGUEDAD > 1 AÑO'] / sec_pbi['PLANTILLA ACTIVA N-1'] * 100).fillna(0)
                    sec_pbi = sec_pbi[sec_pbi['PLANTILLA ACTIVA N-1'] > 0].sort_values('% Estabilidad')
                    
                    # Altura dinámica para que no haya que hacer scroll (Mejora 1)
                    altura_sec = max(400, len(sec_pbi) * 35)
                    fig_bar_sec = px.bar(sec_pbi, x='% Estabilidad', y='SECCION', orientation='h', title='Estabilidad por Sección (PBI)')
                    fig_bar_sec.update_traces(marker_color='#006400')
                    fig_bar_sec.update_layout(xaxis_range=[0,100], height=altura_sec)
                    st.plotly_chart(fig_bar_sec, use_container_width=True)
                
                with c_a2:
                    pue_pbi = df_pbi_ultimo.groupby('PUESTO')[['PLANTILLA ACTIVA N-1', 'PLANTILLA ANTIGUEDAD > 1 AÑO']].sum().reset_index()
                    pue_pbi['% Estabilidad'] = (pue_pbi['PLANTILLA ANTIGUEDAD > 1 AÑO'] / pue_pbi['PLANTILLA ACTIVA N-1'] * 100).fillna(0)
                    pue_pbi = pue_pbi[pue_pbi['PLANTILLA ACTIVA N-1'] > 0].sort_values('% Estabilidad')
                    
                    # Altura dinámica para que no haya que hacer scroll (Mejora 1)
                    altura_pue = max(400, len(pue_pbi) * 35)
                    fig_bar_pue = px.bar(pue_pbi, x='% Estabilidad', y='PUESTO', orientation='h', title='Estabilidad por Puesto (PBI)')
                    fig_bar_pue.update_traces(marker_color='#2ca02c')
                    fig_bar_pue.update_layout(xaxis_range=[0,100], height=altura_pue)
                    st.plotly_chart(fig_bar_pue, use_container_width=True)

                # RASTREADOR DE FUGAS
                st.divider()
                st.subheader(f"🕵️ Rastreador de Fugas: Empleados que penalizaron el mes de {str(ultimo_mes_pbi).capitalize()}")
                st.markdown("Cruce con la Sábana de Datos para identificar a las personas en las secciones con estabilidad inferior al 100%.")
                
                secciones_criticas = sec_pbi[sec_pbi['% Estabilidad'] < 99.9]['SECCION'].tolist()
                
                if secciones_criticas:
                    mes_idx = meses_completos.index(ultimo_mes_pbi) + 1
                    eom_prev = pd.to_datetime(f"2025-{mes_idx:02d}-01") + pd.offsets.MonthEnd(1)
                    eom_curr = pd.to_datetime(f"2026-{mes_idx:02d}-01") + pd.offsets.MonthEnd(1)
                    
                    base_rastreo = df_indef[(df_indef['Fecha alta'] <= eom_prev) & (df_indef['Fecha fin'].isna() | (df_indef['Fecha fin'] >= eom_prev))]
                    ret_rastreo = base_rastreo[(base_rastreo['Fecha fin'].isna() | (base_rastreo['Fecha fin'] >= eom_curr))]
                    
                    fugas_df = base_rastreo[~base_rastreo['Id RH'].isin(ret_rastreo['Id RH'])].copy()
                    fugas_mostrar = fugas_df[fugas_df['Descripción sección'].isin(secciones_criticas)].copy()
                    
                    if not fugas_mostrar.empty:
                        # Cálculo de cuándo deja de penalizar (Mejora 2)
                        def calc_fin_penalizacion(fecha_fin):
                            if pd.isna(fecha_fin):
                                return ""
                            if fecha_fin.is_month_end:
                                target = fecha_fin + pd.DateOffset(years=1, months=1)
                            else:
                                target = fecha_fin + pd.DateOffset(years=1)
                            meses_nombres = {1:'Ene', 2:'Feb', 3:'Mar', 4:'Abr', 5:'May', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dic'}
                            return f"{meses_nombres[target.month]} {target.year}"

                        fugas_mostrar['¿Cuándo deja de penalizar?'] = fugas_mostrar['Fecha fin'].apply(calc_fin_penalizacion)
                        
                        fugas_mostrar = fugas_mostrar[['Descripción sección', 'Nombre', 'Apellidos', 'Descripción Puesto', 'Causa Baja', '¿Cuándo deja de penalizar?']].sort_values('Descripción sección')
                        
                        # Filtros interactivos de tabla (Mejora 2)
                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            filtro_sec = st.multiselect("Filtrar por Sección", options=sorted(fugas_mostrar['Descripción sección'].unique()))
                        with col_f2:
                            filtro_puesto = st.multiselect("Filtrar por Puesto", options=sorted(fugas_mostrar['Descripción Puesto'].unique()))
                            
                        if filtro_sec:
                            fugas_mostrar = fugas_mostrar[fugas_mostrar['Descripción sección'].isin(filtro_sec)]
                        if filtro_puesto:
                            fugas_mostrar = fugas_mostrar[fugas_mostrar['Descripción Puesto'].isin(filtro_puesto)]
                            
                        st.dataframe(fugas_mostrar, use_container_width=True, hide_index=True)
                    else:
                        st.success("No se han encontrado fugas estructurales en la sábana para este periodo.")
                else:
                    st.success("¡Todas las secciones están al 100% de estabilidad!")

                # ==========================================
                # F. RADIOGRAFÍA VIVA
                # ==========================================
                st.divider()
                st.header("👥 Radiografía de la Plantilla Viva")
                st.markdown("Fuerza de trabajo real activa HOY. *(Excluyendo bajas por Agotamiento IT)*")
                
                # Exclusión de Agotamiento IT para el quesito (Mejora 4)
                activos_analisis = df_sim[(df_sim['Fecha fin'].isna() | (df_sim['Fecha fin'] > hoy)) & (df_sim['Causa Baja'] != 'AGOTAMIENTO IT')].copy()
                activos_analisis = activos_analisis.drop_duplicates(subset=['Id RH'])
                
                # Proporción [2, 1, 1] para hacer el gráfico circular más grande (Mejora 4)
                c_sec, c_pue, c_ant = st.columns([2, 1, 1])
                
                with c_sec:
                    st.subheader("Por Sección")
                    if 'Descripción sección' in activos_analisis.columns and not activos_analisis.empty:
                        fig_sec = px.pie(activos_analisis, names='Descripción sección', hole=0.4)
                        fig_sec.update_traces(textposition='inside', textinfo='percent+label')
                        fig_sec.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                        st.plotly_chart(fig_sec, use_container_width=True)
                with c_pue:
                    st.subheader("Por Puesto")
                    if 'Descripción Puesto' in activos_analisis.columns and not activos_analisis.empty:
                        conteo_puesto = activos_analisis['Descripción Puesto'].value_counts().reset_index()
                        fig_pue = px.bar(conteo_puesto, x='count', y='Descripción Puesto', orientation='h')
                        fig_pue.update_layout(showlegend=False, yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig_pue, use_container_width=True)
                with c_ant:
                    st.subheader("Por Antigüedad")
                    if not activos_analisis.empty:
                        bins = [-1, 1, 3, 5, 10, 50]
                        labels = ['< 1 año', '1 a 3 años', '3 a 5 años', '5 a 10 años', '+ 10 años']
                        activos_analisis['Tramo Antigüedad'] = pd.cut(activos_analisis['Antigüedad_Años'], bins=bins, labels=labels)
                        conteo_ant = activos_analisis['Tramo Antigüedad'].value_counts().reindex(labels).reset_index()
                        fig_ant = px.bar(conteo_ant, x='Tramo Antigüedad', y='count')
                        fig_ant.update_layout(showlegend=False)
                        st.plotly_chart(fig_ant, use_container_width=True)

            with tab3:
                # ==========================================
                # G. INFO Y METODOLOGÍA
                # ==========================================
                st.header("📘 ¿Qué es el Índice de Estabilidad?")
                st.markdown("""
                Este indicador mide la capacidad de nuestra tienda y compañía para retener el talento. Matemáticamente, evalúa cuántos empleados indefinidos que formaban parte de nuestra base estructural hace un año siguen trabajando con nosotros a día de hoy.
                """)
                st.info("**Fórmula Oficial LME:** Es la proporción de colaboradores con contrato indefinido y antigüedad en Leroy Merlin España mayor o igual a un año en el periodo, sobre el total de colaboradores con contrato indefinido y cualquier antigüedad en el mismo periodo del año anterior.")
                col_i1, col_i2 = st.columns(2)
                with col_i1:
                    st.subheader("🔢 ¿Cómo se calcula?")
                    st.markdown("""
                    *   **Numerador (Retenidos):** Empleados activos a último día del mes actual que llevan al menos 1 año en la empresa (`Fecha de alta <= Fin de mes año anterior`).
                    *   **Denominador (Base):** Todos los empleados indefinidos que estaban activos en la empresa el último día de ese mismo mes, pero del año anterior.
                    
                    **Resultado:** `(Retenidos / Base) * 100`
                    """)
                with col_i2:
                    st.subheader("🚫 Exclusiones Oficiales")
                    st.markdown("""
                    Para que el indicador sea fiel a la retención estructural, el motor excluye automáticamente:
                    *   **Fijos Discontinuos** (Códigos 300, 330)
                    *   **Contratos Temporales / Formación** (Códigos 402, 410, 420)
                    *   **Prácticas y Relevo** (Códigos 502, 510, 520, 540)
                    *   **Traslados Externos:** Los meses prestados en otra tienda no computan en el histórico local.
                    """)
                st.divider()
                st.subheader("💡 ¿Cómo mejorar la Estabilidad?")
                st.markdown("""
                1.  **Foco en el primer año:** El momento de mayor riesgo de fuga ocurre antes del primer aniversario. Usa la tabla de *Alertas Q4* para detectar qué colaboradores están a punto de cumplir su primer año.
                2.  **Análisis Demográfico:** Utiliza la pestaña de Análisis para detectar qué secciones o puestos están sufriendo una fuga de talento por debajo de la media.
                3.  **Simulación:** Anticípate a fin de año simulando bajas.
                """)

    except Exception as e:
        import traceback
        st.error(f"Error crítico procesando los datos: {e}")
        st.code(traceback.format_exc())
