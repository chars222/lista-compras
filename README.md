🛒 App de Lista de Mercado Persistente

Esta es una aplicación web de Streamlit diseñada para planificar y gestionar listas de compras de mercado. Es adaptable (responsive) y utiliza Google Sheets como su base de datos persistente.

🌟 Características

Doble Modo: Permite la Planificación (añadir productos, cantidades y unidades) y la Compra (marcar productos como comprados, añadir precios y calcular totales).

Persistencia en la Nube: Usa Google Sheets (a través de la librería gspread) para guardar los datos, lo que permite el despliegue en entornos efímeros como Streamlit Community Cloud.

Rotación de Listas: Mantiene automáticamente un máximo de 10 listas; al crear la undécima, borra la más antigua.

Orden Lógico: Las listas se ordenan por categorías fijas (Verduras, Frutas, Carnes, etc.) para seguir un flujo de compra lógico en el mercado.

Manejo de Decimales: Implementa correcciones para asegurar que los decimales (0.5, 1.5) se guarden y carguen correctamente, resolviendo problemas de regionalización (punto vs. coma decimal) entre Python y Google Sheets.

🛠️ Configuración Local

Para desarrollar y probar la aplicación, sigue estos pasos:

1. Preparar el Entorno

Abre tu terminal (o Anaconda Prompt) y asegúrate de estar usando un entorno Python dedicado (como lista_compras)