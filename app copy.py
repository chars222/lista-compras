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
# CRÍTICO: El orden de esta lista define el orden de la visualización en la tabla.
CATEGORIAS = ["🥦 Verduras", "🍓 Frutas", "🥩 Carnes", "🛒 Abarrotes", "🧼 Limpieza", "📦 Otros"]
UNIDADES = ["U (Unidad)", "kg", "g", "lb (Libra)", "L (Litro)", "ml"]

# --- Conexión a Google Sheets (Nuevo método con gspread) ---

# Usamos st.cache_resource para conectarnos solo una vez.
@st.cache_resource
def connect_to_gsheets():
    """
    Se conecta a Google Sheets usando las credenciales en st.secrets
    y devuelve el objeto Spreadsheet.
    """
    try:
        # Definimos los "scopes" (permisos) que necesita gspread
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file"
        ]
        
        # Leemos las credenciales desde el archivo secrets.toml
        # st.secrets.gspread_credentials coincide con [gspread_credentials]
        creds_dict = st.secrets["gspread_credentials"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Autorizamos a gspread con esas credenciales
        client = gspread.authorize(creds)
        
        # Abrimos la Google Sheet por su URL (más robusto)
        # st.secrets.app_config.google_sheet_url coincide con [app_config]
        sheet_url = st.secrets["app_config"]["google_sheet_url"]
        spreadsheet = client.open_by_url(sheet_url)
        return spreadsheet
    
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        st.error("¿Configuraste correctamente .streamlit/secrets.toml con las [gspread_credentials] y [app_config]?")
        st.stop()

# --- Funciones de Ayuda para gspread ---

def read_worksheet_as_df(worksheet: gspread.Worksheet) -> pd.DataFrame:
    """
    Lee una hoja de gspread como texto plano para evitar la conversión automática de Google.
    Devuelve un DataFrame de Pandas.
    """
    # CRÍTICO: Usamos get_all_values() para obtener los datos como strings (texto),
    # sin que Google intente interpretarlos como números, fechas, etc.
    data = worksheet.get_all_values() 
    
    if not data or len(data) < 1:
        # Si la hoja está vacía, devuelve un DF vacío con las columnas correctas
        return pd.DataFrame(columns=["category", "name", "quantity", "unit", "price", "is_checked"])
    
    # La primera fila son las cabeceras
    header = data[0]
    # El resto son los datos
    records = data[1:] 
    
    df = pd.DataFrame(records, columns=header)
    
    # Asegurarnos de que todas las columnas existan, incluso si la hoja está casi vacía
    expected_cols = ["category", "name", "quantity", "unit", "price", "is_checked"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA
            
    # CRÍTICO: Aplicar el orden personalizado a la columna 'category'
    df['category'] = pd.Categorical(
        df['category'], 
        categories=CATEGORIAS, 
        ordered=True
    )

    # Ordenar primero por la nueva categoría (orden fijo) y luego por nombre
    df = df.sort_values(by=["category", "name"], ascending=True) 
            
    return df[expected_cols] # Reordenar por si acaso

def write_df_to_worksheet(worksheet: gspread.Worksheet, df: pd.DataFrame):
    """Limpia una hoja y escribe un DataFrame en ella, formateando decimales con coma."""
    
    df_to_format = df.copy()

    # --- CORRECCIÓN CRÍTICA DE LA CATEGORÍA ---
    # Convertir el tipo Categorical a string (Object) ANTES de guardar.
    # Esto resuelve el error "Cannot setitem on a Categorical with a new category"
    # que ocurre al eliminar filas.
    df_to_format['category'] = df_to_format['category'].astype(str)

    # Función para convertir flotante a string con coma decimal (ej. 0.5 -> "0,5")
    def format_to_comma_string(x):
        if pd.isna(x) or x is None:
            return ''
        # Usamos :g para la representación más concisa (0.5 -> "0.5", 1.0 -> "1")
        # y reemplazamos el punto por la coma para la configuración regional de Sheets
        return "{:g}".format(x).replace('.', ',')

    # Aplicar formato de coma decimal SOLO a las columnas numéricas relevantes
    df_to_format['quantity'] = df_to_format['quantity'].apply(format_to_comma_string)
    df_to_format['price'] = df_to_format['price'].apply(format_to_comma_string)
    
    # Rellenar cualquier otro NaN/None con strings vacíos para gspread (booleans y strings)
    df_filled = df_to_format.fillna('')
    
    # Convertir el DataFrame a una lista de listas (incluyendo cabecera)
    header = df_filled.columns.values.tolist()
    data = df_filled.values.tolist()
    
    # Combinar cabecera y datos
    values = [header] + data
    
    # Limpiar la hoja y escribir los nuevos datos
    try:
        worksheet.clear()
        # CRÍTICO: USER_ENTERED le dice a Sheets que intente parsear la cadena ("0,5") como número.
        worksheet.update('A1', values, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Error al guardar en Google Sheets: {e}")
        return False


# --- Funciones de Lógica de la App (Adaptadas) ---

def get_default_template():
    """Genera la plantilla por defecto como un DataFrame."""
    # (Todos los números son flotantes (X.0) para la inferencia de tipo)
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
    """Obtiene todas las hojas (listas) de Google Sheets y las ordena."""
    all_sheets = spreadsheet.worksheets()
    # Filtramos la hoja "Hoja1" o "Sheet1" por defecto
    list_titles = sorted([s.title for s in all_sheets if s.title.lower() not in ["hoja1", "sheet1"]])
    return list_titles

def render_list_selector(spreadsheet: gspread.Spreadsheet):
    """Muestra el selector para crear o cargar una lista."""
    st.header("🛒 Mis Listas de Mercado")
    st.write("Selecciona una tarea: preparar la lista del viernes o usar una lista para comprar.")

    tab_shop, tab_plan = st.tabs(["🛍️ Realizar Compras", "📝 Crear/Planificar Lista"])

    # Obtenemos las listas existentes desde Google Sheets
    list_titles = get_all_lists(spreadsheet)

    # --- Pestaña 1: Realizar Compras (Cargar lista) ---
    with tab_shop:
        st.subheader("Cargar Lista Existente")
        
        if not list_titles:
            st.info("No hay listas guardadas. ¡Ve a la pestaña 'Crear/Planificar Lista' para empezar!")
        else:
            col1, col2 = st.columns([3, 1])
            selected_list_name = col1.selectbox(
                "Selecciona la lista que usarás para comprar:",
                options=reversed(list_titles), # Más reciente primero
                label_visibility="collapsed"
            )
            
            if col2.button("🛍️ Cargar Lista"):
                st.session_state.current_list_name = str(selected_list_name)
                st.session_state.view_mode = "shop" # <-- MODO COMPRAR
                st.rerun()

    # --- Pestaña 2: Crear/Planificar Lista (Nueva lista) ---
    with tab_plan:
        st.subheader("Crear Nueva Lista")
        
        default_name = f"Lista {datetime.now().strftime('%Y-%m-%d')}"
        
        with st.form("new_list_form"):
            new_list_name = st.text_input("Nombre de la nueva lista:", value=default_name)
            
            template_options = {"No usar plantilla": None, "Usar Plantilla por Defecto": "default_template"}
            template_options.update({f"Copia de: {title}": title for title in list_titles})
            
            selected_template = st.selectbox("Usar como plantilla:", options=template_options.keys())
            
            submit_button = st.form_submit_button("📝 Crear y Planificar")

            if submit_button and new_list_name:
                if new_list_name in list_titles:
                    st.error(f"Ya existe una lista con el nombre '{new_list_name}'. Elige otro nombre.")
                    st.stop()
                
                template_id = template_options[selected_template]
                
                # --- INICIO: LÓGICA DE 10 LISTAS ---
                if len(list_titles) >= 10:
                    try:
                        oldest_list_name = list_titles[0] # La más antigua por orden alfabético
                        oldest_worksheet = spreadsheet.worksheet(oldest_list_name)
                        spreadsheet.del_worksheet(oldest_worksheet)
                        st.toast(f"Límite de 10 listas alcanzado. Borrando la más antigua: '{oldest_list_name}'")
                    except Exception as e:
                        st.error(f"No se pudo borrar la lista más antigua: {e}")
                        st.stop()
                # --- FIN: LÓGICA DE 10 LISTAS ---

                # 2. Decidir qué plantilla cargar
                if template_id == "default_template":
                    df = get_default_template()
                elif template_id is not None:
                    worksheet_to_copy = spreadsheet.worksheet(template_id)
                    df = read_worksheet_as_df(worksheet_to_copy)
                    # Reiniciamos precio y check para la plantilla
                    df['price'] = 0.0
                    df['is_checked'] = False
                else:
                    df = pd.DataFrame(columns=["category", "name", "quantity", "unit", "price", "is_checked"])

                # 3. Crear la nueva hoja de cálculo (lista)
                with st.spinner(f"Creando lista '{new_list_name}'..."):
                    try:
                        # Limpiar el DF antes de guardar (asegurar tipos)
                        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0).astype('float64') # Asegurar float
                        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0.0).astype('float64') # Asegurar float
                        df['is_checked'] = df['is_checked'].fillna(False).astype(bool)
                        
                        # Nueva forma de crear hoja:
                        new_worksheet = spreadsheet.add_worksheet(title=new_list_name, rows=1, cols=len(df.columns))
                        write_df_to_worksheet(new_worksheet, df)
                        
                    except Exception as e:
                        st.error(f"Error al crear la nueva hoja en Google Sheets: {e}")
                        st.stop()

                # 4. Cargar la nueva lista en el estado de la sesión y refrescar
                st.session_state.current_list_name = new_list_name
                st.session_state.view_mode = "plan" # <-- MODO PLANIFICAR
                st.success(f"¡Lista '{new_list_name}' creada!")
                time.sleep(1)
                st.rerun()

def get_list_data(spreadsheet: gspread.Spreadsheet, list_name: str):
    """Función para cargar y limpiar datos de la lista, forzando float64."""
    current_worksheet = spreadsheet.worksheet(list_name)
    items_df = read_worksheet_as_df(current_worksheet)
    
    # --- Limpieza de Datos ---
    items_df = items_df.dropna(how='all')
    
    # Convertir booleanos (gspread puede devolver 'TRUE'/'FALSE')
    items_df['is_checked'] = items_df['is_checked'].replace(
        {'TRUE': True, 'FALSE': False, True: True, False: False, '': False, None: False}
    ).astype(bool)
    
    # CRÍTICO: Solución para Pandas antiguos. Reemplazamos la coma por el punto antes de la conversión
    # La lectura con get_all_values asegura que el dato sea una cadena ("0,5").
    items_df['price'] = items_df['price'].astype(str).str.replace(',', '.', regex=False)
    items_df['quantity'] = items_df['quantity'].astype(str).str.replace(',', '.', regex=False)
    
    # Ahora pd.to_numeric usa el separador decimal estándar (punto)
    items_df['price'] = pd.to_numeric(items_df['price'], errors='coerce').astype('float64').fillna(0.0)
    items_df['quantity'] = pd.to_numeric(items_df['quantity'], errors='coerce').astype('float64').fillna(0.0)

    return items_df

def render_list_editor(spreadsheet: gspread.Spreadsheet):
    """Muestra el editor de la lista (para el Planner y el Shopper)."""
    list_name = st.session_state.current_list_name
    view_mode = st.session_state.get("view_mode", "shop") # 'shop' es el default si no se define

    col_header, col_back = st.columns([4, 1])
    with col_header:
        mode_text = "Planificando" if view_mode == "plan" else "Comprando"
        st.header(f"[{mode_text}] Lista: {list_name}")
    with col_back:
        if st.button("← Volver al Menú"):
            st.session_state.current_list_name = None
            st.session_state.view_mode = None
            st.rerun()

    # --- Cargar datos de la lista ---
    try:
        with st.spinner("Cargando datos de la lista..."):
            items_df = get_list_data(spreadsheet, list_name)
    except Exception as e:
        st.error(f"No se pudo cargar la hoja '{list_name}'. ¿Ha sido borrada?")
        st.error(e)
        st.session_state.current_list_name = None
        st.button("Volver al Menú")
        st.stop()
    
    if items_df.empty:
        items_df = pd.DataFrame(columns=["category", "name", "quantity", "unit", "price", "is_checked"])


    # =========================================================================
    # --- Interfaz Móvil (Shopping List) vs. Grid (Planning/Desktop) ---
    # =========================================================================

    if view_mode == "shop":
        # --- MODO 1: INTERFAZ MÓVIL (SOLO SHOPPING) ---
        
        st.subheader("🛍️ Marcar y Poner Precios")
        st.info("Toca el producto para marcar/desmarcar o haz clic en el precio para actualizarlo.")
        
        # Guardamos los cambios en un diccionario temporal antes de guardar
        temp_updates = {}
        
        # Usamos un formulario para agrupar todos los inputs de la lista y el botón Guardar
        with st.form(key="mobile_shopping_form"):
            
            # Iterar por categorías
            for category in CATEGORIAS:
                category_df = items_df[items_df['category'] == category]
                
                if not category_df.empty:
                    # Título de la sección
                    st.markdown(f"### {category}")
                    
                    # Iterar por productos dentro de la categoría
                    for index, row in category_df.iterrows():
                        # Usamos st.columns para un diseño compacto horizontal (mejor en móvil)
                        col_check, col_qty, col_price = st.columns([1, 2, 2])
                        
                        # 1. Checkbox de Compra (Columna 1)
                        is_checked = col_check.checkbox(
                            label=row['name'],
                            value=row['is_checked'],
                            key=f"check_{list_name}_{index}"
                        )
                        
                        
                        # 3. Cantidad y Unidad (Columna 3)
                        col_qty.markdown(
                            f"<div style='margin-top: -5px; font-size: 14px; color: grey;'>"
                            f"{row['quantity']} {row['unit']}</div>", 
                            unsafe_allow_html=True
                        )

                        # 4. Campo de Precio (Columna 4)
                        # Usamos un campo de número pequeño para editar el precio
                        price_val = col_price.number_input(
                            label=f"Precio {index}",
                            value=row['price'],
                            min_value=0.0,
                            format="%.2f",
                            step=0.01,
                            key=f"price_{list_name}_{index}",
                            label_visibility="collapsed"
                        )
                        
                        # Guardar los cambios en el diccionario temporal
                        temp_updates[index] = {
                            'is_checked': is_checked,
                            'price': price_val
                        }
                        
            # Botón de Guardar
            submit_button = st.form_submit_button("💾 Guardar Cambios", type="primary")

            if submit_button:
                with st.spinner("Guardando en Google Sheets..."):
                    try:
                        # Aplicar los cambios del formulario al DataFrame original
                        df_to_save = items_df.copy()
                        for index, update in temp_updates.items():
                            df_to_save.loc[index, 'is_checked'] = update['is_checked']
                            df_to_save.loc[index, 'price'] = update['price']
                            
                        # Limpieza y casting de tipos antes de guardar
                        df_to_save = df_to_save.dropna(subset=['name'])
                        df_to_save['is_checked'] = df_to_save['is_checked'].fillna(False).astype(bool)
                        df_to_save['price'] = pd.to_numeric(df_to_save['price'], errors='coerce').astype('float64').fillna(0.0)
                        df_to_save['quantity'] = pd.to_numeric(df_to_save['quantity'], errors='coerce').astype('float64').fillna(0.0)
                        df_to_save = df_to_save[["category", "name", "quantity", "unit", "price", "is_checked"]]

                        # Guardar el DF completo
                        worksheet_to_save = spreadsheet.worksheet(list_name)
                        success = write_df_to_worksheet(worksheet_to_save, df_to_save)
                        
                        if success:
                            st.success("¡Lista guardada con éxito en Google Sheets!")
                            time.sleep(1)
                            st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                        
        # --- Resumen de Totales (SOLO MODO SHOPPER) ---
        st.divider()
        st.subheader("Resumen de Compras")
        
        # Calcular el DataFrame final con los valores del estado de sesión
        final_df = items_df.copy()
        if st.session_state:
             for index in final_df.index:
                if f"check_{list_name}_{index}" in st.session_state:
                    final_df.loc[index, 'is_checked'] = st.session_state[f"check_{list_name}_{index}"]
                if f"price_{list_name}_{index}" in st.session_state:
                    final_df.loc[index, 'price'] = st.session_state[f"price_{list_name}_{index}"]


        if not final_df.empty:
            final_df['price'] = pd.to_numeric(final_df['price'], errors='coerce').fillna(0.0).astype('float64')
            comprados_df = final_df[final_df['is_checked'] == True]
            
            if comprados_df.empty:
                st.info("Marca productos (✅) y ponles precio para ver el total.")
            else:
                totals_by_category = comprados_df.groupby("category")["price"].sum().reset_index()
                totals_by_category = totals_by_category.rename(columns={"price": "Total ($)"})
                total_general = totals_by_category["Total ($)"].sum()

                col_metric, col_table = st.columns([1, 2])
                with col_metric:
                    st.metric("Gasto Total (Comprados)", f"${total_general:,.2f}")
                with col_table:
                    st.write("**Total por Categoría (Comprados):**")
                    st.dataframe(
                        totals_by_category, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "category": "Categoría",
                            "Total ($)": st.column_config.NumberColumn(format="$%.2f")
                        }
                    )
        else:
            st.info("Añade productos a la lista para ver el resumen de totales.")


    else:
        # --- MODO 2: INTERFAZ GRID (SOLO PLANIFICACIÓN/ESCRITORIO) ---
        
        st.info("⚠️ Modo Planificación. Utiliza esta tabla para añadir, editar o eliminar filas. Se recomienda usar una tableta o escritorio para esta vista.")
        
        # --- Definición de Columnas (Para el data_editor) ---
        column_config = {
            "name": st.column_config.TextColumn("Producto", required=True),
            "category": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS, required=True),
            "quantity": st.column_config.NumberColumn("Cantidad", min_value=0, format="%.2f", default=None, step=0.01),
            "unit": st.column_config.SelectboxColumn("Unidad", options=UNIDADES),
            # Ocultamos price/check
            "price": st.column_config.NumberColumn("Precio ($)", disabled=True, default=0.0),
            "is_checked": st.column_config.CheckboxColumn("Comprado", disabled=True, default=False),
        }
        
        # Columnas visibles en el data_editor para Planning
        column_order = ["name", "category", "quantity", "unit"]

        # --- El Editor de Datos ---
        edited_df = st.data_editor(
            items_df[column_order], # Solo mostramos las columnas de Planning
            key=f"editor_{list_name}",
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            column_order=column_order
        )

        # --- Botón de Guardar ---
        if st.button("💾 Guardar Cambios", type="primary"):
            with st.spinner("Guardando en Google Sheets..."):
                try:
                    df_to_save = edited_df.copy()
                    
                    # Añadimos las columnas que faltan (price y is_checked) con valores por defecto
                    if 'price' not in df_to_save.columns:
                        df_to_save['price'] = 0.0
                    if 'is_checked' not in df_to_save.columns:
                        df_to_save['is_checked'] = False

                    # Limpieza final antes de guardar
                    df_to_save = df_to_save.dropna(subset=['name'])
                    
                    # Aplicamos el casting CRÍTICO a float64
                    df_to_save['is_checked'] = df_to_save['is_checked'].fillna(False).astype(bool)
                    df_to_save['price'] = pd.to_numeric(df_to_save['price'], errors='coerce').astype('float64').fillna(0.0)
                    df_to_save['quantity'] = pd.to_numeric(df_to_save['quantity'], errors='coerce').astype('float64').fillna(0.0)
                    
                    # Asegurarnos de que el orden de columnas es el correcto para la BD
                    df_to_save = df_to_save[["category", "name", "quantity", "unit", "price", "is_checked"]]
                    
                    # Guardar el DF completo
                    worksheet_to_save = spreadsheet.worksheet(list_name)
                    success = write_df_to_worksheet(worksheet_to_save, df_to_save)
                    
                    if success:
                        st.success("¡Lista guardada con éxito en Google Sheets!")
                        time.sleep(1)
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"Error al guardar: {e}")


# --- Función Principal de la App ---
def main():
    st.title("App de Lista de Mercado 🛒")
    st.info("""
    **Conectado a Google Sheets:** Los datos se guardan en tiempo real. Máximo 10 listas.
    """)
    
    # Nos conectamos a Google Sheets
    spreadsheet = connect_to_gsheets()
    
    if "current_list_name" not in st.session_state:
        st.session_state.current_list_name = None
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = None # 'plan' o 'shop'

    if st.session_state.current_list_name is None:
        render_list_selector(spreadsheet)
    else:
        render_list_editor(spreadsheet)

if __name__ == "__main__":
    main()