# Bot-CAFI-
🤖 CAFI: Agente Inteligente de Finanzas Personales en Telegram. Automatiza el seguimiento de gastos e ingresos mediante lenguaje natural, voz y visión artificial (Groq LLM). Guarda todo en Google Sheets de forma estructurada. 📊💸


# 🤖 CAFI - Personal Finance Agent

**CAFI** (*C*ontrol de *A*ctivos *FI*nancieros) es un asistente inteligente diseñado para simplificar la gestión de finanzas personales. Olvídate de llenar formularios tediosos; interactúa con tus finanzas de la misma forma que hablas con un amigo en Telegram.

## ✨ Características Principales

*   **🎙️ Registro por Voz y Texto:** Envía audios o mensajes de texto detallando tus gastos ("Me gasté 50 en una pizza con amigos") y CAFI los procesará automáticamente.
*   **📸 Visión Artificial (OCR):** Sube fotos de tus tickets o facturas y deja que el agente extraiga los montos y categorías por ti.
*   **📊 Sincronización con Google Sheets:** Todos tus movimientos se guardan en tiempo real en una hoja de cálculo, dándote control total de tus datos.
*   **📈 Reportes Visuales:** Genera gráficos de gastos por categoría y resúmenes de presupuesto directamente en el chat.
*   **🗓️ Automatización:** Reportes semanales y mensuales programados para que nunca pierdas de vista tu salud financiera.
*   **🔐 Seguridad:** Sistema de lista blanca (whitelist) para asegurar que solo tú tengas acceso a tu información.

## 🛠️ Stack Tecnológico

*   **Lenguaje:** Python 3.x
*   **Interfaz:** Telegram Bot API (`python-telegram-bot`)
*   **Inteligencia Artificial:** Groq Cloud (LLM para parsing y visión)
*   **Base de Datos:** Google Sheets API
*   **Gráficos:** Matplotlib

## ⚙️ Configuración de Variables de Entorno

Copia el archivo de ejemplo y completa tus valores:

```bash
cp .env.example .env
```

Luego edita `.env` con tus credenciales reales:

| Variable | Obligatoria | Descripción |
|---|---|---|
| `TELEGRAM_TOKEN` | ✅ | Token del bot entregado por [@BotFather](https://t.me/BotFather) |
| `ALLOWED_USER_ID` | ✅ | Tu ID numérico de Telegram (obtenlo con [@userinfobot](https://t.me/userinfobot)). Solo este usuario podrá usar el bot. |
| `GROQ_API_KEY` | ✅ | API Key de [Groq Console](https://console.groq.com) para el LLM |
| `OWNER_NAME` | ⬜ | Tu nombre, usado en los análisis del LLM (por defecto: "el usuario") |

> **Google Drive:** La sincronización con Drive no requiere variables de entorno. Solo descarga tu archivo OAuth 2.0 desde Google Cloud Console, renómbralo `credentials.json` y colócalo en la raíz del proyecto. El archivo `token.json` se genera automáticamente la primera vez. Ambos archivos están incluidos en `.gitignore`.
