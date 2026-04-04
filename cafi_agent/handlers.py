import os
from functools import wraps
import datetime
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import cafi_agent.llm_parser as llm
import cafi_agent.storage as storage
import cafi_agent.charts as charts
from cafi_agent.cron_jobs import weekly_report_job, monthly_report_job

def authorized_only(func):
    """Decorador que solo permite que el usuario autorizado ejecute la función."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        allowed_id = os.getenv("ALLOWED_USER_ID")
        user_id = update.effective_user.id
        
        if not allowed_id or str(user_id) != str(allowed_id):
            print(f"Intento de acceso denegado del ID: {user_id}")
            if update.message:
                await update.message.reply_text("⛔ Lo siento, este bot es privado.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

@authorized_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """¡Hola! Soy *CAFI* 🤖, tu asistente financiero personal inteligente.

Estoy aquí para ayudarte a registrar, clasificar y resumir todos tus gastos e ingresos automáticamente.

📝 *¿Cómo registrar algo?*
Envíame la información de la forma que te sea más fácil:
• *Texto normal:* "Gasté 15.000 en el pasaje de Uber" o "Ayer pagué 80.000 de internet".
• *Fotos:* Mándame la foto de una factura, recibo de tienda o pantallazo de tu banco.
• *Audios:* Envíame una nota de voz rápida contándome en qué gastaste.

Yo usaré Inteligencia Artificial para extraer todo por ti, te pediré que lo apruebes, y lo sincronizaré con tu Google Drive.

⚙️ *Comandos para control:*
/hoy - Ver todas las transacciones del día
/resumen - Ver tu balance total e ingresos vs gastos
/categorias - Ver qué categorías puedo reconocer
/graficos - Ver gráficos de tu situación financiera
/borrar - Borrar registros recientes
/limpiar - Reiniciar todo el periodo actual
/consejos - Ver qué ha aprendido CAFI sobre tus hábitos
/presupuesto - Establecer límites de gastos
/exportar - Descargar tus datos en Excel
/historial - Ver el log completo de transacciones (aunque limpies el periodo)
/reporte - Generar reportes financieros inmediatos

¡Envíame tu primer movimiento y empecemos!

Nota: no trates de hablarme como a un llm, solo enviame la informacion de la transaccion y usa los comandos o botones que pongo a tu disposicion.

_Usa el menú de abajo para acceder rápidamente a las funciones._"""
    storage.set_chat_id(update.effective_chat.id)
    
    keyboard = [
        ["📅 Hoy", "📊 Resumen", "📈 Gráficos"],
        ["💰 Presupuesto", "📑 Reporte", "💡 Consejos"],
        ["📥 Exportar", "📜 Historial"],
        ["🗑️ Borrar", "🧹 Limpiar"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

@authorized_only
async def handle_general_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text or msg.caption
    
    if text:
        if "📅 Hoy" in text: return await cmd_hoy(update, context)
        if "📊 Resumen" in text: return await cmd_resumen(update, context)
        if "📈 Gráficos" in text: return await cmd_graficos(update, context)
        if "💰 Presupuesto" in text: return await cmd_presupuesto(update, context)
        if "📑 Reporte" in text: return await cmd_reporte(update, context)
        if "💡 Consejos" in text: return await cmd_consejos(update, context)
        if "📥 Exportar" in text: return await cmd_exportar(update, context)
        if "📜 Historial" in text: return await cmd_historial(update, context)
        if "🗑️ Borrar" in text: return await cmd_borrar(update, context)
        if "🧹 Limpiar" in text: return await cmd_limpiar(update, context)

    image_path = None
    
    if msg.photo:
        photo_file = await msg.photo[-1].get_file()
        image_path = f"temp_{msg.photo[-1].file_id}.jpg"
        await photo_file.download_to_drive(image_path)
        
    await msg.reply_text("⏳ Procesando...")
    
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    data = llm.parse_transaction(text=text, image_path=image_path, current_date=current_date)
    
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except OSError:
            pass
            
    if context.user_data.get("awaiting_monto"):
        tx_id = context.user_data.get("awaiting_monto")
        try:
            nuevo_monto = int(text.replace(".", "").replace(",", ""))
            tx_info = context.user_data.get(tx_id)
            if tx_info:
                tx_info["data"]["monto"] = nuevo_monto
                del context.user_data["awaiting_monto"]
                formatted_msg = _format_proposed_msg(tx_info["data"])
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_{tx_id}"),
                        InlineKeyboardButton("✏️ Editar", callback_data=f"options_{tx_id}"),
                        InlineKeyboardButton("❌ Cancelar", callback_data=f"reject_{tx_id}")
                    ]
                ]
                await msg.reply_text(formatted_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                return
        except ValueError:
            await msg.reply_text("❌ Por favor, envía solo el número (ej: 15000).")
            return

    if data.get("ambiguo", False):
        await msg.reply_text(f"❓ {data.get('razon_ambiguedad', 'No me queda claro.')}")
        return
        
    tipo = data.get("tipo", "GASTO").upper()
    cat = storage.normalize_category(data.get("categoria", "Otros"))
    monto = data.get("monto", 0)
    desc = data.get("descripcion", "")
    fecha = data.get("fecha", current_date)
    
    source = "imagen" if msg.photo else "texto"
    
    # Generate unique transaction ID
    tx_id = str(uuid.uuid4())
    context.user_data[tx_id] = {
        "data": data,
        "source": source
    }
    
    formatted_msg = f"📝 *Propuesta de Registro:*\n\n"\
                    f"Tipo: {tipo}\n"\
                    f"Categoría: {cat}\n"\
                    f"Monto: ${monto:,.0f} COP\n"\
                    f"Descripción: {desc}\n"\
                    f"Fecha: {fecha}\n\n"\
                    f"¿Es correcto este registro?"
                    
    keyboard = [
        [
            InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_{tx_id}"),
            InlineKeyboardButton("✏️ Editar", callback_data=f"options_{tx_id}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"reject_{tx_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await msg.reply_text(formatted_msg, reply_markup=reply_markup, parse_mode="Markdown")

@authorized_only
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    try:
        parts = data.split("_")
        action = parts[0]
        tx_id = parts[1] if len(parts) > 1 else None
    except ValueError:
        return
        
    if action == "options":
        # Menú de edición
        keyboard = [
            [InlineKeyboardButton("💰 Cambiar Monto", callback_data=f"askmonto_{tx_id}")],
            [InlineKeyboardButton("📂 Cambiar Categoría", callback_data=f"askcat_{tx_id}")],
            [InlineKeyboardButton("🔙 Volver", callback_data=f"back_{tx_id}")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "askcat":
        # Mostrar rejilla de categorías
        tx_info = context.user_data.get(tx_id)
        tipo = tx_info["data"]["tipo"]
        if tipo == "GASTO":
            cats = storage.CATEGORIES_GASTOS
        else:
            cats = storage.CATEGORIES_INGRESOS
        
        keyboard = []
        row = []
        for c in cats:
            row.append(InlineKeyboardButton(c, callback_data=f"setcat_{tx_id}_{c}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data=f"options_{tx_id}")])
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "setcat":
        cat_name = "_".join(parts[2:])
        tx_info = context.user_data.get(tx_id)
        if tx_info:
            tx_info["data"]["categoria"] = cat_name
            # Actualizar mensaje con la categoría nueva
            formatted_msg = _format_proposed_msg(tx_info["data"])
            keyboard = [[InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_{tx_id}"), InlineKeyboardButton("✏️ Editar", callback_data=f"options_{tx_id}"), InlineKeyboardButton("❌ Cancelar", callback_data=f"reject_{tx_id}")]]
            await query.edit_message_text(text=formatted_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif action == "askmonto":
        context.user_data["awaiting_monto"] = tx_id
        await query.edit_message_text(text="✍️ Por favor, escribe el nuevo monto numérico (ej: 25000):")

    elif action == "back":
        tx_info = context.user_data.get(tx_id)
        if tx_info:
            formatted_msg = _format_proposed_msg(tx_info["data"])
            keyboard = [[InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_{tx_id}"), InlineKeyboardButton("✏️ Editar", callback_data=f"options_{tx_id}"), InlineKeyboardButton("❌ Cancelar", callback_data=f"reject_{tx_id}")]]
            await query.edit_message_text(text=formatted_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif action == "approve":
        tx_info = context.user_data.get(tx_id)
        if not tx_info:
            await query.edit_message_text(text="⚠️ Esta transacción ya expiró o no se encontró en memoria.")
            return
            
        # Log to Storage and Google Drive
        alert = storage.log_transaction(tx_info["data"], source=tx_info["source"])
        del context.user_data[tx_id]
        
        tipo = tx_info['data'].get('tipo', 'GASTO').upper()
        monto = tx_info['data'].get('monto', 0)
        final_msg = f"✅ ¡Aprobado y Registrado exitosamente! ({tipo}: ${monto:,.0f})"
        if alert:
            final_msg += f"\n\n{alert}"
            
        await query.edit_message_text(text=final_msg, parse_mode="Markdown")
        
    elif action == "reject":
        if tx_id in context.user_data:
            del context.user_data[tx_id]
        await query.edit_message_text(text="❌ Registro cancelado.")

    elif action == "del":
        success = storage.delete_transaction(tx_id)
        if success:
            await query.edit_message_text(text="🗑️ Registro eliminado correctamente y balance actualizado.")
        else:
            await query.edit_message_text(text="⚠️ No se pudo eliminar el registro (puede que ya no exista).")

    elif action == "reset":
        if tx_id == "confirm":
            storage.reset_periodo()
            await query.edit_message_text(text="🆕 El periodo ha sido reiniciado a cero. ¡Todo limpio!")
        else:
            await query.edit_message_text(text="Operación cancelada.")

@authorized_only
async def cmd_hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las transacciones activas de hoy."""
    data = storage.get_periodo_data()
    historial = data.get("historial_reciente", [])
    fecha_hoy = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Filtrar solo las de hoy que están en el periodo activo
    hoy_activas = [tx for tx in historial if tx["fecha"] == fecha_hoy]
    
    if not hoy_activas:
        await update.message.reply_text("📭 No tienes transacciones activas registradas hoy en este periodo.\n\n_Nota: Si usaste /limpiar, el contador volvió a cero, pero tus logs permanentes siguen en /historial._", parse_mode="Markdown")
        return
        
    msg = f"📅 *Transacciones Activas de Hoy ({fecha_hoy}):*\n\n"
    for tx in reversed(hoy_activas): # Mostrar en orden cronológico
        monto_fmt = f"${tx['monto']:,.0f}"
        msg += f"• `{tx['tipo'][:1]}` {monto_fmt} — {tx['descripcion']} ({tx['categoria']})\n"
        
    msg += f"\nTotal hoy: ${sum(tx['monto'] for tx in hoy_activas if tx['tipo'] == 'GASTO'):,.0f} en gastos."
    await update.message.reply_text(msg, parse_mode="Markdown")

@authorized_only
async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el log permanente del día (Markdown)."""
    fecha = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(storage.MEMORY_DIR, f"{fecha}.md")
    
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            content = f.read()
            
        # Limitar longitud si el log es muy largo
        if len(content) > 3500:
            content = content[:3500] + "\n\n...(Log muy largo, usa /exportar para el detalle completo)"
            
        await update.message.reply_text(f"📜 *Log Permanente de Hoy ({fecha}):*\n\n{content}", parse_mode="Markdown")
    else:
        await update.message.reply_text("Aún no hay logs registrados para el día de hoy.")

@authorized_only
async def cmd_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = storage.get_periodo_data()
    if not data:
        await update.message.reply_text("No hay datos en el período actual.")
        return
        
    balance = data.get("balance", 0)
    ingresos = data.get("ingresos_totales", 0)
    gastos = data.get("gastos_totales", 0)
    transacciones = data.get("transacciones_registradas", 0)
    
    # Formateo general
    emoji = "🟢" if balance >= 0 else "🔴"
    
    msg = f"📊 RESUMEN ACUMULADO\n\n"\
          f"INGRESOS: ${ingresos:,.0f}\n"\
          f"GASTOS: ${gastos:,.0f}\n"\
          f"BALANCE: ${balance:,.0f} {emoji}\n\n"\
          f"Transacciones: {transacciones}"
    await update.message.reply_text(msg)

@authorized_only
async def cmd_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"""
*Gastos:* {", ".join(storage.CATEGORIES_GASTOS)}
*Ingresos:* {", ".join(storage.CATEGORIES_INGRESOS)}
"""
    await update.message.reply_text(msg, parse_mode="Markdown")

@authorized_only
async def cmd_graficos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera y envía gráficos financieros al usuario."""
    data = storage.get_periodo_data()
    if not data:
        await update.message.reply_text("📊 No hay datos suficientes para generar gráficos. ¡Registra algunas transacciones primero!")
        return

    await update.message.reply_text("📊 Generando tus gráficos financieros...")

    sent = False

    # Gráfico de torta (gastos por categoría)
    pie_path = charts.generate_pie_chart()
    if pie_path and os.path.exists(pie_path):
        with open(pie_path, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption="🥧 Distribución de Gastos por Categoría")
        os.remove(pie_path)
        sent = True

    # Gráfico de barras (ingresos vs gastos vs balance)
    bar_path = charts.generate_bar_chart()
    if bar_path and os.path.exists(bar_path):
        with open(bar_path, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption="💰 Ingresos vs Gastos vs Balance")
        os.remove(bar_path)
        sent = True

    if not sent:
        await update.message.reply_text("📊 Aún no tienes suficientes datos con montos mayores a 0 para generar gráficos.")

@authorized_only
async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las últimas transacciones para poder borrarlas."""
    data = storage.get_periodo_data()
    historial = data.get("historial_reciente", [])
    
    if not historial:
        await update.message.reply_text("No tienes registros recientes para borrar.")
        return
        
    msg = "🗑️ *Selecciona un registro para borrar:*\n\n"
    keyboard = []
    
    # Mostrar las últimas 5 para no saturar
    for tx in historial[:5]:
        tx_id = tx["id"]
        # Resumen corto para el botón
        btn_text = f"{tx['tipo'][:1]}: ${tx['monto']:,.0f} - {tx['descripcion'][:15]}"
        keyboard.append([InlineKeyboardButton(f"❌ {btn_text}", callback_data=f"del_{tx_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

@authorized_only
async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comanda para reiniciar todo el periodo."""
    msg = "🚨 *ATENCIÓN:* Estás a punto de borrar TODOS los totales del periodo actual (ingresos, gastos y balance se volverán cero).\n\n¿Estás seguro de que quieres continuar?"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Sí, reiniciar todo", callback_data="reset_confirm"),
            InlineKeyboardButton("❌ No, cancelar", callback_data="reset_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

@authorized_only
async def cmd_consejos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los aprendizajes guardados en MEMORY.md."""
    if not os.path.exists(storage.MEMORY_MD):
        await update.message.reply_text("Aún no he aprendido lo suficiente. ¡Sigue registrando tus gastos para darte consejos!")
        return
        
    with open(storage.MEMORY_MD, "r") as f:
        content = f.read()
        
    # El archivo tiene un encabezado por defecto de unas 3 líneas
    if not content or len(content.strip().split("\n")) <= 3:
        await update.message.reply_text("Aún no tengo consejos específicos para ti. Sigue registrando y pronto notaré tus patrones.")
        return
        
    await update.message.reply_text(f"🧠 *Esto es lo que he aprendido de tus finanzas:*\n\n{content}", parse_mode="Markdown")

@authorized_only
async def cmd_presupuesto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Establece, ajusta o muestra los presupuestos."""
    args = context.args
    data = storage.get_periodo_data()
    presupuestos = data.get("presupuestos", {})

    if not args:
        if not presupuestos:
            msg = "📌 *No tienes presupuestos establecidos.*\n\n"\
                  "Para crear uno, usa: `/presupuesto [Categoría] [Monto]`\n"\
                  "Ejemplo: `/presupuesto Alimentacion 500000`"
        else:
            msg = "💰 *Tus Presupuestos Actuales:*\n\n"
            for cat, limite in presupuestos.items():
                gastado = data.get("gastos_por_categoria", {}).get(cat, 0)
                porcentaje = (gastado / limite * 100) if limite > 0 else 0
                bar = storage.generate_progress_bar(porcentaje)
                msg += f"• *{cat}*: ${limite:,.0f}\n{bar} ({porcentaje:.1f}%)\nGastado: ${gastado:,.0f}\n\n"
            
            msg += "💡 *Para ajustar:* Envía el comando de nuevo con el nuevo monto.\n"\
                   "💡 *Para quitar:* Pon el monto en 0."
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
        
    if len(args) < 2:
        await update.message.reply_text("💡 Uso: `/presupuesto [Categoria] [Monto]`\nEjemplo: `/presupuesto Alimentacion 500000`", parse_mode="Markdown")
        return
        
    cat_raw = args[0]
    try:
        monto = int(args[1].replace(".", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("❌ El monto debe ser un número entero.")
        return
    
    cat_norm = storage.normalize_category(cat_raw)
    
    if not storage.is_canonical(cat_norm):
        msg = f"⚠️ La categoría *'{cat_raw}'* no es reconocida.\n\n"\
              f"Categorías válidas de gastos:\n_{', '.join(storage.CATEGORIES_GASTOS)}_\n\n"\
              f"Categorías válidas de ingresos:\n_{', '.join(storage.CATEGORIES_INGRESOS)}_"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
        
    storage.update_budget(cat_norm, monto)
    
    if monto == 0:
        await update.message.reply_text(f"🗑️ Presupuesto para *{cat_norm}* eliminado.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"✅ Presupuesto establecido/ajustado: *{cat_norm}* con límite de ${monto:,.0f}", parse_mode="Markdown")

@authorized_only
async def cmd_exportar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera un archivo Excel con todas las transacciones."""
    await update.message.reply_text("📝 Generando tu reporte Excel...")
    
    df = storage.get_all_transactions_df()
    if df.empty:
        await update.message.reply_text("No hay transacciones registradas para exportar.")
        return
        
    output_file = "Reporte_Financiero_CAFI.xlsx"
    df.to_excel(output_file, index=False)
    
    with open(output_file, "rb") as f:
        await update.message.reply_document(document=f, filename=output_file, caption="Aquí tienes tu reporte detallado de gastos e ingresos. 📊")
        
    os.remove(output_file)

def _format_proposed_msg(data: dict) -> str:
    tipo = data.get("tipo", "GASTO").upper()
    cat = storage.normalize_category(data.get("categoria", "Otros"))
    monto = data.get("monto", 0)
    desc = data.get("descripcion", "")
    fecha = data.get("fecha", "")
    
    return f"📝 *Propuesta de Registro (Editada):*\n\n"\
           f"Tipo: {tipo}\n"\
           f"Categoría: {cat}\n"\
           f"Monto: ${monto:,.0f} COP\n"\
           f"Descripción: {desc}\n"\
           f"Fecha: {fecha}\n\n"\
           f"¿Es correcto este registro?"


@authorized_only
async def cmd_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera y envía los reportes semanal y mensual manualmente para prueba."""
    chat_id = update.effective_chat.id
    await update.message.reply_text("🔄 Generando reportes de prueba (Semanal y Mensual)...")
    
    # Llamamos a los jobs directamente pasando el chat_id
    await weekly_report_job(context, chat_id=chat_id)
    await monthly_report_job(context, chat_id=chat_id)
    
    await update.message.reply_text("✅ Reportes generados, enviados y guardados en la carpeta /reportes.")

@authorized_only
async def cmd_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando oculto para agregar datos de prueba."""
    # 1. Crear transacciones de prueba
    hoy = datetime.datetime.now().strftime("%Y-%m-%d")
    test_txs = [
        {"tipo": "GASTO", "categoria": "Alimentación", "monto": 25000, "descripcion": "🍔 Cena rápida de prueba", "fecha": hoy},
        {"tipo": "INGRESO", "categoria": "Otros", "monto": 120000, "descripcion": "💵 Venta de prueba", "fecha": hoy},
        {"tipo": "GASTO", "categoria": "Transporte", "monto": 12000, "descripcion": "🚕 Uber de prueba", "fecha": hoy},
        {"tipo": "GASTO", "categoria": "Servicios", "monto": 80000, "descripcion": "💡 Internet (Test)", "fecha": hoy}
    ]
    
    for tx in test_txs:
        storage.log_transaction(tx, source="TEST_DEBUG")
        
    # 2. Establecer un presupuesto de prueba
    storage.update_budget("Alimentación", 100000)
    storage.update_budget("Transporte", 50000)
    
    await update.message.reply_text("🧪 *MODO DEBUG:* Se han agregado 4 transacciones de prueba y se configuraron presupuestos para 'Alimentación' (100k) y 'Transporte' (50k). Puedes ver los resultados en /resumen o /presupuesto.", parse_mode="Markdown")

