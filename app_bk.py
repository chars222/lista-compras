import streamlit as st
import pandas as pd
from datetime import datetime
import time
import gspread # Importamos gspread
from google.oauth2.service_account import Credentials # Y la autenticación

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Lista de Mercado",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Definición de Categorías y Unidades (ORDEN PERSONALIZADO) ---
CATEGORIAS = ["🥦 Verduras", "🍓 Frutas", "🥩 Carnes", "🛒 Abarrotes", "🧼 Limpieza", "📦 Otros"]
UNIDADES = ["U (Unidad)", "kg", "g", "lb (Libra)", "L (Litro)", "ml"]

# --- Conexión a Google Sheets (Nuevo método con gspread) ---
@st.cache_resource
def connect_to_gsheets():
    """Se conecta a Google Sheets usando las credenciales en st.secrets."""
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file"
        ]
        creds_dict = st.secrets["gspread_credentials"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_url = st.secrets["app_config"]["google_sheet_url"]
        spreadsheet = client.open_by_url(sheet_url)
        return spreadsheet
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        st.stop()

# --- Funciones de Ayuda ---

def read_worksheet_as_df(worksheet: gspread.Worksheet) -> pd.DataFrame:
    """Lee una hoja de gspread como texto plano."""
    data = worksheet.get_all_values() 
    if not data or len(data) < 1:
        return pd.DataFrame(columns=["category", "name", "quantity", "unit", "price", "is_checked"])
    
    header = data[0]
    records = data[1:] 
    df = pd.DataFrame(records, columns=header)
    
    expected_cols = ["category", "name", "quantity", "unit", "price", "is_checked"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA
            
    df['category'] = pd.Categorical(df['category'], categories=CATEGORIAS, ordered=True)
    df = df.sort_values(by=["category", "name"], ascending=True) 
    return df[expected_cols]

def write_df_to_worksheet(worksheet: gspread.Worksheet, df: pd.DataFrame):
    """Escribe un DataFrame en la hoja, formateando decimales."""
    df_to_format = df.copy()
    df_to_format['category'] = df_to_format['category'].astype(str)

    def format_to_comma_string(x):
        if pd.isna(x) or x is None: return ''
        return "{:g}".format(x).replace('.', ',')

    df_to_format['quantity'] = df_to_format['quantity'].apply(format_to_comma_string)
    df_to_format['price'] = df_to_format['price'].apply(format_to_comma_string)
    
    df_filled = df_to_format.fillna('')
    header = df_filled.columns.values.tolist()
    data = df_filled.values.tolist()
    values = [header] + data
    
    try:
        worksheet.clear()
        worksheet.update('A1', values, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Error al guardar en Google Sheets: {e}")
        return False

def get_default_template():
    return pd.DataFrame([
        {"category": "🥦 Verduras", "name": "Tomates", "quantity": 1.0, "unit": "kg", "price": 0.0, "is_checked": False},
        # ... (resto de la plantilla resumida para brevedad) ...
    ])

def get_all_lists(spreadsheet: gspread.Spreadsheet):
    all_sheets = spreadsheet.worksheets()
    list_titles = sorted([s.title for s in all_sheets if s.title.lower() not in ["hoja1", "sheet1"]])
    return list_titles

def get_list_data(spreadsheet: gspread.Spreadsheet, list_name: str):
    current_worksheet = spreadsheet.worksheet(list_name)
    items_df = read_worksheet_as_df(current_worksheet)
    items_df = items_df.dropna(how='all')
    items_df['is_checked'] = items_df['is_checked'].replace({'TRUE': True, 'FALSE': False, '': False}).astype(bool)
    items_df['price'] = items_df['price'].astype(str).str.replace(',', '.', regex=False)
    items_df['quantity'] = items_df['quantity'].astype(str).str.replace(',', '.', regex=False)
    items_df['price'] = pd.to_numeric(items_df['price'], errors='coerce').astype('float64').fillna(0.0)
    items_df['quantity'] = pd.to_numeric(items_df['quantity'], errors='coerce').astype('float64').fillna(0.0)
    return items_df

# --- Componentes de Interfaz ---

def render_list_selector(spreadsheet: gspread.Spreadsheet):
    """Muestra el selector para crear o cargar una lista."""
    st.header("🛒 Mis Listas de Mercado")
    st.write("Selecciona una tarea: preparar la lista del viernes o usar una lista para comprar.")

    tab_shop, tab_plan = st.tabs(["🛍️ Realizar Compras", "📝 Crear/Planificar Lista"])
    list_titles = get_all_lists(spreadsheet)

    with tab_shop:
        st.subheader("Cargar Lista Existente")
        if not list_titles:
            st.info("No hay listas guardadas.")
        else:
            col1, col2 = st.columns([3, 1])
            selected_list_name = col1.selectbox("Selecciona la lista:", options=reversed(list_titles), label_visibility="collapsed")
            if col2.button("🛍️ Cargar"):
                st.session_state.current_list_name = str(selected_list_name)
                st.session_state.view_mode = "shop"
                st.rerun()

    with tab_plan:
        st.subheader("Crear Nueva Lista")
        default_name = f"Lista {datetime.now().strftime('%Y-%m-%d')}"
        with st.form("new_list_form"):
            new_list_name = st.text_input("Nombre:", value=default_name)
            template_options = {"No usar plantilla": None, "Usar Plantilla por Defecto": "default_template"}
            template_options.update({f"Copia de: {title}": title for title in list_titles})
            selected_template = st.selectbox("Plantilla:", options=template_options.keys())
            
            if st.form_submit_button("📝 Crear"):
                if new_list_name in list_titles:
                    st.error("Ya existe una lista con ese nombre.")
                    st.stop()
                
                # Lógica de borrado de lista antigua (límite 10)
                if len(list_titles) >= 10:
                    try:
                        oldest_ws = spreadsheet.worksheet(list_titles[0])
                        spreadsheet.del_worksheet(oldest_ws)
                    except: pass

                template_id = template_options[selected_template]
                if template_id == "default_template": df = get_default_template()
                elif template_id: 
                    ws_copy = spreadsheet.worksheet(template_id)
                    df = read_worksheet_as_df(ws_copy)
                    df['price'] = 0.0
                    df['is_checked'] = False
                else: df = pd.DataFrame(columns=["category", "name", "quantity", "unit", "price", "is_checked"])

                with st.spinner("Creando..."):
                    df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
                    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0.0)
                    new_ws = spreadsheet.add_worksheet(title=new_list_name, rows=1, cols=len(df.columns))
                    write_df_to_worksheet(new_ws, df)
                
                st.session_state.current_list_name = new_list_name
                st.session_state.view_mode = "plan"
                st.rerun()

def render_list_editor(spreadsheet: gspread.Spreadsheet):
    """Editor principal (Modo Shop con Acordeones y Formulario Rápido)."""
    list_name = st.session_state.current_list_name
    view_mode = st.session_state.get("view_mode", "shop")

    col_header, col_back = st.columns([4, 1])
    with col_header:
        mode_text = "Planificando" if view_mode == "plan" else "Comprando"
        st.header(f"[{mode_text}] {list_name}")
    with col_back:
        if st.button("← Menú"):
            st.session_state.current_list_name = None
            st.session_state.view_mode = None
            st.rerun()

    try:
        items_df = get_list_data(spreadsheet, list_name)
    except:
        st.error("Error cargando lista.")
        st.stop()

    # =========================================================================
    # --- MODO SHOPPING ---
    # =========================================================================
    if view_mode == "shop":
        
        # --- 1. FORMULARIO RÁPIDO DE AÑADIR (En Expander) ---
        with st.expander("➕ Añadir Producto (Rápido)", expanded=False):
            with st.form("quick_add_shop_form", clear_on_submit=True):
                c_name, c_cat = st.columns([2, 1])
                q_name = c_name.text_input("Producto", placeholder="Ej: Leche")
                q_cat = c_cat.selectbox("Categoría", CATEGORIAS)
                
                c_qty, c_unit = st.columns([1, 1])
                q_qty = c_qty.number_input("Cant.", min_value=0.0, step=0.5, format="%.2f")
                q_unit = c_unit.selectbox("Unidad", UNIDADES)
                
                if st.form_submit_button("Añadir"):
                    new_row = pd.DataFrame([{
                        "category": q_cat, "name": q_name, "quantity": q_qty, 
                        "unit": q_unit, "price": 0.0, "is_checked": False
                    }])
                    # Concatenar y guardar
                    df_update = pd.concat([items_df, new_row], ignore_index=True)
                    ws = spreadsheet.worksheet(list_name)
                    write_df_to_worksheet(ws, df_update)
                    st.success("Añadido!")
                    time.sleep(0.5)
                    st.rerun()

        st.divider()
        
        # --- 2. LISTA DE COMPRAS CON ACORDEONES ---
        st.subheader("🛍️ Tu Lista")
        st.info("Toca una categoría para ver sus productos.")
        
        temp_updates = {}
        
        # Un solo formulario grande para guardar precios y checks
        with st.form(key="mobile_shopping_form"):
            
            # Iteramos categorías y creamos ACORDEONES
            for category in CATEGORIAS:
                category_df = items_df[items_df['category'] == category]
                
                if not category_df.empty:
                    # Calculamos cuántos items hay para ponerlo en el título
                    count = len(category_df)
                    checked_count = category_df['is_checked'].sum()
                    icon = "✅" if checked_count == count else "🛒"
                    
                    # --- COMPONENTE ACORDEÓN ---
                    # expanded=True para que se vean abiertos por defecto, 
                    # o False si prefieres todo cerrado al inicio.
                    with st.expander(f"{category} ({checked_count}/{count}) {icon}", expanded=False):
                        
                        for index, row in category_df.iterrows():
                            col_check, col_qty, col_price = st.columns([1, 2, 2])
                            
                            # Checkbox
                            is_checked = col_check.checkbox(
                                row['name'], 
                                value=row['is_checked'], 
                                key=f"check_{index}"
                            )
                            
                            # Info Cantidad
                            col_qty.markdown(
                                f"<div style='margin-top: -5px; font-size: 14px; color: grey;'>"
                                f"{row['quantity']} {row['unit']}</div>", 
                                unsafe_allow_html=True
                            )

                            # Input Precio
                            price_val = col_price.number_input(
                                f"Precio {index}", 
                                value=row['price'], 
                                min_value=0.0, step=0.5, 
                                key=f"price_{index}", 
                                label_visibility="collapsed"
                            )
                            
                            temp_updates[index] = {'is_checked': is_checked, 'price': price_val}
                            st.markdown("---") # Separador entre items

            # Botón flotante de guardar (al final del form)
            if st.form_submit_button("💾 Guardar Todo (Precios/Checks)", type="primary"):
                with st.spinner("Guardando..."):
                    df_to_save = items_df.copy()
                    for idx, vals in temp_updates.items():
                        df_to_save.loc[idx, 'is_checked'] = vals['is_checked']
                        df_to_save.loc[idx, 'price'] = vals['price']
                    
                    ws = spreadsheet.worksheet(list_name)
                    if write_df_to_worksheet(ws, df_to_save):
                        st.success("Guardado!")
                        time.sleep(0.5)
                        st.rerun()

        # Resumen de Totales
        st.divider()
        if not items_df.empty:
            comprados = items_df[items_df['is_checked'] == True]
            total = comprados['price'].sum()
            st.metric("Total Gastado", f"${total:,.2f}")

    # =========================================================================
    # --- MODO GRID (PLANNING) ---
    # =========================================================================
    else:
        st.info("⚠️ Modo Edición Masiva (Escritorio).")
        
        # Grid Editable (Como lo tenías en tu código anterior)
        column_config = {
            "name": st.column_config.TextColumn("Producto", required=True),
            "category": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS, required=True),
            "quantity": st.column_config.NumberColumn("Cant.", format="%.2f"),
            "unit": st.column_config.SelectboxColumn("Unidad", options=UNIDADES),
            "price": st.column_config.NumberColumn("Precio", disabled=True),
            "is_checked": st.column_config.CheckboxColumn("Check", disabled=True),
        }
        
        edited_df = st.data_editor(
            items_df, 
            key="editor", 
            num_rows="dynamic", 
            use_container_width=True,
            column_config=column_config,
            hide_index=True
        )

        if st.button("💾 Guardar Tabla", type="primary"):
             with st.spinner("Guardando..."):
                ws = spreadsheet.worksheet(list_name)
                # Aseguramos tipos float antes de guardar
                edited_df['price'] = pd.to_numeric(edited_df['price'], errors='coerce').fillna(0.0)
                edited_df['quantity'] = pd.to_numeric(edited_df['quantity'], errors='coerce').fillna(0.0)
                if write_df_to_worksheet(ws, edited_df):
                    st.success("Tabla guardada!")
                    time.sleep(1)
                    st.rerun()

# --- Main ---
def main():
    st.title("App de Lista de Mercado 🛒")
    spreadsheet = connect_to_gsheets()
    
    if "current_list_name" not in st.session_state:
        st.session_state.current_list_name = None
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = None

    if st.session_state.current_list_name is None:
        render_list_selector(spreadsheet)
    else:
        render_list_editor(spreadsheet)

if __name__ == "__main__":
    main()