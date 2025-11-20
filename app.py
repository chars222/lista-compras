import streamlit as st
import pandas as pd
from datetime import datetime
import time
import gspread
from google.oauth2.service_account import Credentials

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Lista de Mercado",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS PARA FORZAR DISEÑO HORIZONTAL EN MÓVIL ---
def inject_mobile_css():
    st.markdown("""
        <style>
        /* Ajustes Críticos para Móvil */
        @media (max-width: 768px) {
            /* 1. Forzar que las columnas (st.columns) NO se apilen verticalmente */
            div[data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 5px !important;
                align-items: center !important; /* Centrar verticalmente ítems */
            }
            
            /* 2. Permitir que las columnas se encojan más allá de su "mínimo" habitual */
            div[data-testid="stColumn"] {
                min-width: 0px !important;
                flex: 1 1 auto !important;
            }

            /* 3. Ajustar botones pequeños (como el de borrar) para ahorrar espacio */
            div[data-testid="stButton"] button {
                padding: 0px 8px !important;
                min-height: 35px !important;
                height: 35px !important;
                margin-top: 0px !important;
                width: 100%; /* Que ocupe su columna */
            }
            
            /* 4. Reducir márgenes del texto para que se alinee mejor con el botón */
            div[data-testid="stMarkdownContainer"] p {
                margin-bottom: 0px !important;
                line-height: 1.2 !important;
            }
            
            /* 5. Ajustar inputs numéricos y selectbox para que quepan lado a lado */
            div[data-testid="stNumberInput"] input {
                padding: 0px 5px !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

# --- Definición de Categorías y Unidades ---
CATEGORIAS = ["🥦 Verduras", "🍓 Frutas", "🥩 Carnes", "🛒 Abarrotes", "🧼 Limpieza", "📦 Otros"]
UNIDADES = ["U (Unidad)", "kg", "g", "lb (Libra)", "L (Litro)", "ml"]

# --- Conexión a Google Sheets ---
@st.cache_resource
def connect_to_gsheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]
        creds_dict = st.secrets["gspread_credentials"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_url = st.secrets["app_config"]["google_sheet_url"]
        spreadsheet = client.open_by_url(sheet_url)
        return spreadsheet
    except Exception as e:
        st.error(f"Error al conectar: {e}")
        st.stop()

# --- Funciones de Ayuda ---
def read_worksheet_as_df(worksheet: gspread.Worksheet) -> pd.DataFrame:
    data = worksheet.get_all_values() 
    if not data or len(data) < 1:
        return pd.DataFrame(columns=["category", "name", "quantity", "unit", "price", "is_checked"])
    
    header = data[0]
    records = data[1:] 
    df = pd.DataFrame(records, columns=header)
    
    expected_cols = ["category", "name", "quantity", "unit", "price", "is_checked"]
    for col in expected_cols:
        if col not in df.columns: df[col] = pd.NA
            
    df['category'] = pd.Categorical(df['category'], categories=CATEGORIAS, ordered=True)
    df = df.sort_values(by=["category", "name"], ascending=True) 
    return df[expected_cols]

def write_df_to_worksheet(worksheet: gspread.Worksheet, df: pd.DataFrame):
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
        st.error(f"Error guardando: {e}")
        return False

def get_default_template():
    return pd.DataFrame([
{"category": "🥦 Verduras", "name": "Tomates", "quantity": 1.0, "unit": "kg", "price": 0.0, "is_checked": False},
        {"category": "🥦 Verduras", "name": "Cebollas", "quantity": 3.0, "unit": "lb (Libra)", "price": 0.0, "is_checked": False},
        {"category": "🥦 Verduras", "name": "Papa harinosa", "quantity": 6.0, "unit": "lb (Libra)", "price": 12.0, "is_checked": False},
        {"category": "🥦 Verduras", "name": "Papa holadesa", "quantity": 3.0, "unit": "lb (Libra)", "price": 6.0, "is_checked": False},
        {"category": "🥦 Verduras", "name": "Platano", "quantity": 6.0, "unit": "U (Unidad)", "price": 10.0, "is_checked": False},
        {"category": "🥦 Verduras", "name": "Zapallo", "quantity": 0.5, "unit": "kg", "price": 5.0, "is_checked": False},
        {"category": "🥦 Verduras", "name": "lechuga carola", "quantity": 2.0, "unit": "U (Unidad)", "price": 13.0, "is_checked": False},
        {"category": "🥦 Verduras", "name": "Brocoli", "quantity": 1.0, "unit": "U (Unidad)", "price": 8.0, "is_checked": False},
        {"category": "🥦 Verduras", "name": "Espinaca", "quantity": 2.0, "unit": "U (Unidad)", "price": 8.0, "is_checked": False},
        {"category": "🥦 Verduras", "name": "choclo", "quantity": 6.0, "unit": "U (Unidad)", "price": 20.0, "is_checked": False},
        {"category": "🍓 Frutas", "name": "Guineo", "quantity": 6.0, "unit": "U (Unidad)", "price": 6.0, "is_checked": False},
        {"category": "🍓 Frutas", "name": "Manzana", "quantity": 4.0, "unit": "U (Unidad)", "price": 10.0, "is_checked": False},
        {"category": "🍓 Frutas", "name": "Pera", "quantity": 3.0, "unit": "U (Unidad)", "price": 10.0, "is_checked": False},
        {"category": "🍓 Frutas", "name": "Limon cambita", "quantity": 10.0, "unit": "U (Unidad)", "price": 10.0, "is_checked": False},
        {"category": "🍓 Frutas", "name": "Limon de licuar", "quantity": 10.0, "unit": "U (Unidad)", "price": 10.0, "is_checked": False},
        {"category": "🍓 Frutas", "name": "Piña", "quantity": 1.0, "unit": "U (Unidad)", "price": 8.0, "is_checked": False},
        {"category": "🍓 Frutas", "name": "Arandanos", "quantity": 1.0, "unit": "U (Unidad)", "price": 18.0, "is_checked": False},
        {"category": "🍓 Frutas", "name": "Frutillas", "quantity": 1.0, "unit": "U (Unidad)", "price": 15.0, "is_checked": False},
        {"category": "🥩 Carnes", "name": "Pollo", "quantity": 2.0, "unit": "U (Unidad)", "price": 90.0, "is_checked": False},
        {"category": "🥩 Carnes", "name": "Pollo (Pechuga)", "quantity": 1.0, "unit": "U (Unidad)", "price": 26.0, "is_checked": False},
        {"category": "🥩 Carnes", "name": "Bollo chico", "quantity": 1.0, "unit": "kg", "price": 70.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Arroz", "quantity": 1.0, "unit": "kg", "price": 0.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Huevo Maple", "quantity": 1.0, "unit": "U (Unidad)", "price": 24.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Quezo", "quantity": 0.5, "unit": "kg", "price": 22.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Fideo codito", "quantity": 1.0, "unit": "kg", "price": 8.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Fideo espiral", "quantity": 1.0, "unit": "kg", "price": 8.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Papel higuineco 24", "quantity": 1.0, "unit": "U (Unidad)", "price": 26.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Servilleta mesa", "quantity": 1.0, "unit": "U (Unidad)", "price": 15.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Servilleta cocina", "quantity": 1.0, "unit": "U (Unidad)", "price": 15.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Ajo cabeza", "quantity": 1.0, "unit": "U (Unidad)", "price": 2.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Quinua", "quantity": 0.5, "unit": "kg", "price": 10.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Azucar Morena", "quantity": 1.0, "unit": "kg", "price": 8.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Azucar Blanca", "quantity": 1.0, "unit": "kg", "price": 6.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Té frutas Pack", "quantity": 1.0, "unit": "U (Unidad)", "price": 25.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Té canela Pack", "quantity": 1.0, "unit": "U (Unidad)", "price": 12.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Té manzanilla Pack", "quantity": 1.0, "unit": "U (Unidad)", "price": 12.0, "is_checked": False},
        {"category": "🛒 Abarrotes", "name": "Agua bebe", "quantity": 3.0, "unit": "L (Litro)", "price": 11.0, "is_checked": False},
        {"category": "🧼 Limpieza", "name": "Detergente ropa adultos", "quantity": 1.0, "unit": "U (Unidad)", "price": 36.0, "is_checked": False},
        {"category": "🧼 Limpieza", "name": "Detergente ropa bebe", "quantity": 1.0, "unit": "U (Unidad)", "price": 35.0, "is_checked": False},
        {"category": "🧼 Limpieza", "name": "Detergente ropa platos", "quantity": 1.0, "unit": "U (Unidad)", "price": 25.0, "is_checked": False},
        {"category": "🧼 Limpieza", "name": "Lavandina", "quantity": 1.0, "unit": "U (Unidad)", "price": 20.0, "is_checked": False},
        {"category": "🧼 Limpieza", "name": "Trapo de piso", "quantity": 1.0, "unit": "U (Unidad)", "price": 6.0, "is_checked": False},
        {"category": "🧼 Limpieza", "name": "jaboncillo adulto", "quantity": 1.0, "unit": "U (Unidad)", "price": 20.0, "is_checked": False},
        {"category": "🧼 Limpieza", "name": "jaboncillo bebe", "quantity": 1.0, "unit": "U (Unidad)", "price": 20.0, "is_checked": False},
        {"category": "🧼 Limpieza", "name": "Pañal bebe pack", "quantity": 1.0, "unit": "U (Unidad)", "price": 90.0, "is_checked": False},
        {"category": "🧼 Limpieza", "name": "Bolsa de basura Grande pack", "quantity": 1.0, "unit": "U (Unidad)", "price": 10.0, "is_checked": False},
        {"category": "📦 Otros", "name": "Agua bebe", "quantity": 3.0, "unit": "L (Litro)", "price": 11.0, "is_checked": False},
        {"category": "📦 Otros", "name": "Pan Frances", "quantity": 5.0, "unit": "U (Unidad)", "price": 5.0, "is_checked": False},
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

# --- Acciones Inmediatas ---
def delete_item(spreadsheet, list_name, item_name):
    try:
        current_df = get_list_data(spreadsheet, list_name)
        df_to_save = current_df[current_df['name'] != item_name].copy()
        ws = spreadsheet.worksheet(list_name)
        write_df_to_worksheet(ws, df_to_save)
        st.toast(f"🗑️ {item_name} eliminado")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Error borrando: {e}")

def save_instant_edit(spreadsheet, list_name, item_name, col_key, session_key):
    try:
        current_df = get_list_data(spreadsheet, list_name)
        new_val = st.session_state[session_key]
        current_df.loc[current_df['name'] == item_name, col_key] = new_val
        ws = spreadsheet.worksheet(list_name)
        write_df_to_worksheet(ws, current_df)
    except Exception as e:
        st.error(f"Error guardando: {e}")

# --- Componentes UI ---
def render_list_selector(spreadsheet: gspread.Spreadsheet):
    st.header("🛒 Mis Listas")
    tab_shop, tab_plan = st.tabs(["🛍️ Comprar", "📝 Crear/Planificar"])
    list_titles = get_all_lists(spreadsheet)

    with tab_shop:
        if not list_titles:
            st.info("Sin listas guardadas.")
        else:
            c1, c2 = st.columns([3, 1])
            sel_list = c1.selectbox("Lista:", options=reversed(list_titles), label_visibility="collapsed")
            if c2.button("Cargar"):
                st.session_state.current_list_name = str(sel_list)
                st.session_state.view_mode = "shop"
                st.rerun()

    with tab_plan:
        with st.form("new_list"):
            default_name = f"Lista {datetime.now().strftime('%Y-%m-%d')}"
            name = st.text_input("Nombre:", value=default_name)
            
            opts = {"Vacía": None, "Plantilla Base": "default", **{f"Copia: {t}": t for t in list_titles}}
            templ = st.selectbox("Base:", options=opts.keys())
            
            if st.form_submit_button("Crear"):
                if name in list_titles:
                    st.error("Nombre ya existe.")
                    st.stop()
                
                # Limpiar antiguas (>10)
                if len(list_titles) >= 10:
                    try: spreadsheet.del_worksheet(spreadsheet.worksheet(list_titles[0]))
                    except: pass

                tid = opts[templ]
                if tid == "default": df = get_default_template()
                elif tid: 
                    df = read_worksheet_as_df(spreadsheet.worksheet(tid))
                    df['price'] = 0.0; df['is_checked'] = False
                else: df = pd.DataFrame(columns=["category", "name", "quantity", "unit", "price", "is_checked"])

                # Guardar
                df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
                df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0.0)
                ws = spreadsheet.add_worksheet(title=name, rows=1, cols=6)
                write_df_to_worksheet(ws, df)
                
                st.session_state.current_list_name = name
                st.session_state.view_mode = "plan"
                st.rerun()

def render_list_editor(spreadsheet: gspread.Spreadsheet):
    list_name = st.session_state.current_list_name
    view_mode = st.session_state.get("view_mode", "shop")
    
    # Encabezado compacto
    c_head, c_back = st.columns([5, 1])
    c_head.subheader(f"{'📝' if view_mode == 'plan' else '🛍️'} {list_name}")
    if c_back.button("🔙"):
        st.session_state.current_list_name = None
        st.rerun()

    try: items_df = get_list_data(spreadsheet, list_name)
    except: st.error("Error cargando lista."); st.stop()

    # --- MODO COMPRAS ---
    if view_mode == "shop":
        with st.expander("➕ Añadir Rápido", expanded=False):
            with st.form("quick_add_shop", clear_on_submit=True):
                c1, c2 = st.columns([2, 1])
                q_n = c1.text_input("Producto")
                q_c = c2.selectbox("Cat", CATEGORIAS)
                c3, c4 = st.columns([1, 1])
                q_q = c3.number_input("Cant", min_value=0.0, step=1.0, format="%.2f")
                q_u = c4.selectbox("Unidad", UNIDADES)
                if st.form_submit_button("Añadir"):
                    new = pd.DataFrame([{"category": q_c, "name": q_n, "quantity": q_q, "unit": q_u, "price": 0.0, "is_checked": False}])
                    write_df_to_worksheet(spreadsheet.worksheet(list_name), pd.concat([items_df, new], ignore_index=True))
                    st.rerun()
        
        st.divider()
        temp_updates = {}
        
        with st.form("shop_form"):
            for cat in CATEGORIAS:
                cat_df = items_df[items_df['category'] == cat]
                if not cat_df.empty:
                    chk = cat_df['is_checked'].sum()
                    with st.expander(f"{cat} ({chk}/{len(cat_df)})", expanded=False):
                        for idx, row in cat_df.iterrows():
                            # LAYOUT SHOP: Check | Qty | Precio
                            # Usamos CSS para que no se apilen
                            c_chk, c_qty, c_prc = st.columns([1, 2, 2])
                            
                            check = c_chk.checkbox("", value=row['is_checked'], key=f"ck_{idx}")
                            c_qty.caption(f"{row['name']}\n{row['quantity']} {row['unit']}")
                            prc = c_prc.number_input("Precio", value=row['price'], min_value=0.0, step=0.5, key=f"pr_{idx}", label_visibility="collapsed")
                            
                            temp_updates[idx] = {'is_checked': check, 'price': prc}
                            st.markdown("<hr style='margin:0px; opacity:0.3'>", unsafe_allow_html=True)
            
            if st.form_submit_button("💾 Guardar Todo", type="primary"):
                df_save = items_df.copy()
                for i, v in temp_updates.items():
                    df_save.loc[i, 'is_checked'] = v['is_checked']
                    df_save.loc[i, 'price'] = v['price']
                write_df_to_worksheet(spreadsheet.worksheet(list_name), df_save)
                st.rerun()
        
        # --- TOTALES ---
        if not items_df.empty:
            bought = items_df[items_df['is_checked']]
            if not bought.empty:
                st.divider()
                t_cat = bought.groupby("category")["price"].sum().reset_index()
                t_cat = t_cat[t_cat["price"] > 0]
                
                c_t1, c_t2 = st.columns([2, 1])
                c_t1.dataframe(t_cat, hide_index=True, column_config={"category": "Cat", "price": st.column_config.NumberColumn("Total", format="$%.2f")}, use_container_width=True)
                c_t2.metric("Total", f"${bought['price'].sum():,.2f}")

    # --- MODO PLANIFICACIÓN ---
    else:
        # Formulario Añadir
        with st.expander("➕ Añadir Rápido", expanded=False):
            with st.form("quick_add_plan", clear_on_submit=True):
                c1, c2 = st.columns([2, 1])
                q_n = c1.text_input("Producto")
                q_c = c2.selectbox("Cat", CATEGORIAS)
                c3, c4 = st.columns([1, 1])
                q_q = c3.number_input("Cant", min_value=0.0, step=1.0, format="%.2f")
                q_u = c4.selectbox("Unidad", UNIDADES)
                if st.form_submit_button("Añadir"):
                    new = pd.DataFrame([{"category": q_c, "name": q_n, "quantity": q_q, "unit": q_u, "price": 0.0, "is_checked": False}])
                    write_df_to_worksheet(spreadsheet.worksheet(list_name), pd.concat([items_df, new], ignore_index=True))
                    st.success("Añadido"); st.rerun()

        # Lista Editable
        st.divider()
        for cat in CATEGORIAS:
            cat_df = items_df[items_df['category'] == cat]
            if not cat_df.empty:
                with st.expander(f"{cat} ({len(cat_df)})", expanded=False):
                    for idx, row in cat_df.iterrows():
                        name = row['name']
                        
                        # --- FILA 1: Nombre (Izq) + Borrar (Der) ---
                        # CSS asegura que [8, 1] se mantenga horizontal en móvil
                        c_nom, c_del = st.columns([8, 2])
                        c_nom.markdown(f"**{name}**")
                        if c_del.button("🗑️", key=f"d_{idx}"):
                            delete_item(spreadsheet, list_name, name)
                        
                        # --- FILA 2: Cantidad + Unidad ---
                        # CSS asegura que [1, 1] se mantenga horizontal en móvil
                        c_q, c_u = st.columns([1, 1])
                        
                        st.session_state[f"sq_{idx}"] = row['quantity']
                        st.session_state[f"su_{idx}"] = row['unit']
                        
                        c_q.number_input("Cant",value=float(row['quantity']), min_value=0.0, step=0.5, key=f"iq_{idx}", label_visibility="collapsed",
                                        on_change=save_instant_edit, args=(spreadsheet, list_name, name, 'quantity', f"iq_{idx}"))
                        
                        c_u.selectbox("Uni", UNIDADES, key=f"iu_{idx}", label_visibility="collapsed",
                                     index=UNIDADES.index(row['unit']) if row['unit'] in UNIDADES else 0,
                                     on_change=save_instant_edit, args=(spreadsheet, list_name, name, 'unit', f"iu_{idx}"))
                        
                        st.markdown("<hr style='margin: 5px 0px; opacity: 0.2'>", unsafe_allow_html=True)

def main():
    inject_mobile_css() # <--- INYECCIÓN DE CSS
    spreadsheet = connect_to_gsheets()
    
    if "current_list_name" not in st.session_state: st.session_state.current_list_name = None
    if "view_mode" not in st.session_state: st.session_state.view_mode = None

    if st.session_state.current_list_name is None: render_list_selector(spreadsheet)
    else: render_list_editor(spreadsheet)

if __name__ == "__main__":
    main()