import os
import datetime
from typing import Optional
from telegram.ext import ContextTypes
import cafi_agent.storage as storage
import cafi_agent.drive_sync as drive_sync

async def weekly_report_job(context: ContextTypes.DEFAULT_TYPE, chat_id: Optional[int] = None):
    """
    Genera el reporte semanal, lo envía por Telegram y lo guarda en Google Drive.
    """
    bot = context.bot
    if not chat_id:
        if context.job and context.job.chat_id:
            chat_id = context.job.chat_id
        else:
            chat_id = storage.get_chat_id()
    
    data = storage.get_periodo_data()
    if not data:
        return
        
    ingresos = data.get("ingresos_totales", 0)
    gastos = data.get("gastos_totales", 0)
    balance = data.get("balance", 0)
    cats = data.get("gastos_por_categoria", {})
    transacciones = data.get("transacciones_registradas", 0)
    
    hoy = datetime.datetime.now()
    semana_num = hoy.isocalendar()[1]
    
    sorted_cats = sorted(cats.items(), key=lambda item: item[1], reverse=True)
    emoji = "🟢" if balance >= 0 else "🔴"
    
    msg_lines = [
        f"📊 REPORTE SEMANA {semana_num} — {hoy.strftime('%b %Y')}",
        "",
        f"INGRESOS:   ${ingresos:,.0f}",
        f"GASTOS:     ${gastos:,.0f}",
        f"BALANCE:    ${balance:,.0f} {emoji}",
        "",
        "Top categorías de gasto:"
    ]
    
    total_gasto = gastos if gastos > 0 else 1
    for i, (c, m) in enumerate(sorted_cats[:3]):
        pct = (m / total_gasto) * 100
        msg_lines.append(f"  {i+1}. {c}  ${m:,.0f} ({pct:.0f}%)")
        
    msg_lines.append("")
    msg_lines.append(f"Transacciones registradas: {transacciones}")
        
    msg = "\n".join(msg_lines)
    
    if chat_id:
        try:
            await bot.send_message(chat_id=chat_id, text=msg)
        except Exception as e:
            print(f"Error enviando reporte semanal: {e}")
            
    reportes_dir = os.path.join(storage.WORKSPACE_DIR, "reportes")
    storage._ensure_dir_exists(reportes_dir)
    report_file = os.path.join(reportes_dir, f"semana-{semana_num}-{hoy.year}.md")
    
    with open(report_file, "w") as f:
        f.write(msg)
        
    drive_sync.upload_file_to_drive(report_file)
    update_heartbeat(f"Reporte semanal {semana_num} generado y guardado el {hoy.strftime('%Y-%m-%d %H:%M')}")

async def monthly_report_job(context: ContextTypes.DEFAULT_TYPE, chat_id: Optional[int] = None):
    """
    Genera el reporte mensual detallado.
    """
    bot = context.bot
    if not chat_id:
        if context.job and context.job.chat_id:
            chat_id = context.job.chat_id
        else:
            chat_id = storage.get_chat_id()
    
    data = storage.get_periodo_data()
    if not data:
        return
        
    ingresos = data.get("ingresos_totales", 0)
    gastos = data.get("gastos_totales", 0)
    balance = data.get("balance", 0)
    cats = data.get("gastos_por_categoria", {})
    
    hoy = datetime.datetime.now()
    mes_nombre = hoy.strftime('%B %Y')
    
    sorted_cats = sorted(cats.items(), key=lambda item: item[1], reverse=True)
    emoji = "🏆" if balance >= 0 else "📉"
    
    msg_lines = [
        f"🌟 REPORTE MENSUAL — {mes_nombre.upper()}",
        "--------------------------------------",
        f"💰 Ingresos:  ${ingresos:,.0f}",
        f"💸 Gastos:    ${gastos:,.0f}",
        f"⚖️ Balance:   ${balance:,.0f} {emoji}",
        "",
        "📊 Detalle por categorías:"
    ]
    
    total_gasto = gastos if gastos > 0 else 1
    for c, m in sorted_cats:
        pct = (m / total_gasto) * 100
        msg_lines.append(f"• {c}: ${m:,.0f} ({pct:.1f}%)")
        
    msg_lines.append("")
    msg_lines.append(f"Reporte generado automáticamente el {hoy.strftime('%d/%m/%Y')}")
    
    msg = "\n".join(msg_lines)
    
    if chat_id:
        try:
            await bot.send_message(chat_id=chat_id, text=msg)
        except Exception as e:
            print(f"Error enviando reporte mensual: {e}")
            
    reportes_dir = os.path.join(storage.WORKSPACE_DIR, "reportes")
    storage._ensure_dir_exists(reportes_dir)
    report_file = os.path.join(reportes_dir, f"mensual-{hoy.strftime('%m-%Y')}.md")
    
    with open(report_file, "w") as f:
        f.write(msg)
        
    drive_sync.upload_file_to_drive(report_file)
    update_heartbeat(f"Reporte mensual {hoy.strftime('%m-%Y')} generado el {hoy.strftime('%Y-%m-%d %H:%M')}")

def update_heartbeat(status: str):
    hb_path = os.path.join(storage.WORKSPACE_DIR, "HEARTBEAT.md")
    if os.path.exists(hb_path):
        with open(hb_path, "a") as f:
            f.write(f"\n- [LOG] {status}\n")
