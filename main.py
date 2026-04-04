import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import cafi_agent.llm_parser as llm
import cafi_agent.handlers as handlers
from cafi_agent.cron_jobs import weekly_report_job, monthly_report_job
import cafi_agent.storage as storage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "tu_token_de_telegram_aqui":
        logger.error("TELEGRAM_TOKEN no está configurado adecuadamente en el archivo .env.")
        logger.error("Por favor, inserta un token de BotFather para poder iniciar.")
        return

    logger.info("Inicializando LLM Groq...")
    llm.init_llm()

    logger.info("Construyendo aplicación de Telegram...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("hoy", handlers.cmd_hoy))
    application.add_handler(CommandHandler("resumen", handlers.cmd_resumen))
    application.add_handler(CommandHandler("categorias", handlers.cmd_categorias))
    application.add_handler(CommandHandler("graficos", handlers.cmd_graficos))
    application.add_handler(CommandHandler("borrar", handlers.cmd_borrar))
    application.add_handler(CommandHandler("limpiar", handlers.cmd_limpiar))
    application.add_handler(CommandHandler("consejos", handlers.cmd_consejos))
    application.add_handler(CommandHandler("presupuesto", handlers.cmd_presupuesto))
    application.add_handler(CommandHandler("exportar", handlers.cmd_exportar))
    application.add_handler(CommandHandler("historial", handlers.cmd_historial))
    application.add_handler(CommandHandler("reporte", handlers.cmd_reporte))
    application.add_handler(CommandHandler("godmode", handlers.cmd_debug))
    
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VOICE, handlers.handle_general_message))
    application.add_handler(CallbackQueryHandler(handlers.handle_callback_query))

    # Importante: Como `weekly_report_job` necesita un chat_id al cual enviar,
    # sugerimos que el usuario ejecute un /start para registrar su chat_id.
    # Por defecto, configuraremos el job para que arranque, pero necesitarás
    # inyectarle tu chat_id (ej: application.job_queue.run_repeating...)

    # Programación de Reportes Automáticos
    import datetime
    
    # Reporte Semanal: Todos los Lunes a las 8:00 AM
    application.job_queue.run_daily(
        weekly_report_job,
        time=datetime.time(hour=8, minute=0),
        days=(0,) # 0 = Lunes en python-telegram-bot (ajustado de 1 a 0 si es necesario)
    )
    
    # Reporte Mensual: El día 1 de cada mes a las 9:00 AM
    application.job_queue.run_monthly(
        monthly_report_job,
        when=datetime.time(hour=9, minute=0),
        day=1
    )
    
    logger.info("CAFI Bot iniciado. Presiona Ctrl+C para detener.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
