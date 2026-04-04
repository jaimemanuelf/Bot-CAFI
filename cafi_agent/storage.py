import os
import json
import datetime
import threading
from typing import Optional, Union
import cafi_agent.drive_sync as drive_sync

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(WORKSPACE_DIR, "memory")
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
PERIODO_JSON = os.path.join(DATA_DIR, "periodo-actual.json")
HISTORICO_JSON = os.path.join(DATA_DIR, "historico.json")
MEMORY_MD = os.path.join(WORKSPACE_DIR, "MEMORY.md")

CATEGORIES_GASTOS = [
    "Alimentación", "Transporte", "Salud", "Gimnasio / Deporte", 
    "Educación", "Entretenimiento", "Ropa", "Servicios", 
    "Arriendo", "Suscripciones", "Otros"
]
CATEGORIES_INGRESOS = [
    "Trabajo fijo", "Freelance / Consultoría", "Transferencia", 
    "Reembolso", "Otros"
]

CATEGORY_SYNONYMS = {
    "carro": "Transporte",
    "vehiculo": "Transporte",
    "gasolina": "Transporte",
    "uber": "Transporte",
    "comida": "Alimentación",
    "restaurante": "Alimentación",
    "mercado": "Alimentación",
    "super": "Alimentación",
    "gym": "Gimnasio / Deporte",
    "deporte": "Gimnasio / Deporte",
    "entrenamiento": "Gimnasio / Deporte",
    "luz": "Servicios",
    "agua": "Servicios",
    "internet": "Servicios",
    "net": "Suscripciones",
    "netflix": "Suscripciones",
    "spotify": "Suscripciones",
    "estudio": "Educación",
    "curso": "Educación",
    "cine": "Entretenimiento",
    "salida": "Entretenimiento"
}

def is_canonical(cat: str) -> bool:
    """Verifica si una categoría pertenece al listado estándar."""
    return cat in CATEGORIES_GASTOS or cat in CATEGORIES_INGRESOS

def normalize_category(cat: str) -> str:
    """Normaliza el nombre de la categoría para evitar duplicados por minúsculas o tildes."""
    if not cat:
        return "Otros"
    
    cat_clean = cat.strip().lower()
    
    # 1. Buscar en sinónimos
    if cat_clean in CATEGORY_SYNONYMS:
        return CATEGORY_SYNONYMS[cat_clean]

    # 2. Buscar en gastos
    for c in CATEGORIES_GASTOS:
        if c.lower() == cat_clean:
            return c
            
    # 3. Buscar en ingresos
    for c in CATEGORIES_INGRESOS:
        if c.lower() == cat_clean:
            return c
            
    # Si no se encuentra, Capitalizar primera letra
    return cat.strip().capitalize()

def generate_progress_bar(percentage: float) -> str:
    """Genera una barra de progreso visual con emojis."""
    if percentage > 100: percentage = 100
    filled = int(percentage / 10)
    empty = 10 - filled
    
    if percentage >= 100:
        return "🔴" * 10
    elif percentage >= 80:
        return "🟠" * filled + "⚪" * empty
    else:
        return "🟢" * filled + "⚪" * empty

def _ensure_dir_exists(path: str):
    if not os.path.exists(path):
        os.makedirs(path)

def log_transaction(transaction: dict, source: str = "texto"):
    """
    Guarda la transacción en el MD del día y actualiza el JSON del período.
    """
    _ensure_dir_exists(MEMORY_DIR)
    fecha = transaction.get("fecha", datetime.datetime.now().strftime("%Y-%m-%d"))
    log_file = os.path.join(MEMORY_DIR, f"{fecha}.md")
    
    hora = datetime.datetime.now().strftime("%H:%M:%S")
    tipo = transaction.get("tipo", "GASTO").upper()
    cat = transaction.get("categoria", "Otros")
    monto = transaction.get("monto", 0)
    desc = transaction.get("descripcion", "")
    
    line = f"- [{hora}] {tipo} — {cat} — ${monto} — {desc} ({source})\n"
    
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write(f"# Transacciones del {fecha}\n\n")
            
    with open(log_file, "a") as f:
        f.write(line)
        
    _update_periodo_actual(transaction)
    
    # 6. Sube archivos y EJECUTA APRENDIZAJE en segundo plano
    def _background_tasks():
        # Sincronización
        drive_sync.upload_file_to_drive(log_file)
        drive_sync.upload_file_to_drive(PERIODO_JSON)
        # Aprendizaje
        _discover_insights()
        
    threading.Thread(target=_background_tasks).start()

def _discover_insights():
    """Analiza el historial reciente para descubrir patrones y guardarlos en MEMORY.md."""
    import cafi_agent.llm_parser as llm
    
    data = get_periodo_data()
    historial = data.get("historial_reciente", [])
    if len(historial) < 3: # Necesitamos al menos unos pocos para ver patrones
        return
        
    # Leer memoria actual
    current_mem = ""
    if os.path.exists(MEMORY_MD):
        with open(MEMORY_MD, "r") as f:
            current_mem = f.read()
            
    # Consultar al LLM
    new_insights = llm.analyze_habits(historial, current_mem)
    
    for insight in new_insights:
        append_to_memory(insight)

def _update_periodo_actual(transaction: dict):
    _ensure_dir_exists(DATA_DIR)
    
    tipo = transaction.get("tipo", "GASTO").upper()
    cat = normalize_category(transaction.get("categoria", "Otros"))
    monto = transaction.get("monto", 0)
    desc = transaction.get("descripcion", "")
    fecha_tx = transaction.get("fecha", datetime.datetime.now().strftime("%Y-%m-%d"))
    tx_id = transaction.get("id", str(datetime.datetime.now().timestamp()))
    
    if os.path.exists(PERIODO_JSON):
        with open(PERIODO_JSON, "r") as f:
            data = json.load(f)
    else:
        data = _generate_empty_periodo()
        
    data["transacciones_registradas"] += 1
    
    # Store in history
    if "historial_reciente" not in data:
        data["historial_reciente"] = []
    
    data["historial_reciente"].insert(0, {
        "id": tx_id,
        "fecha": fecha_tx,
        "tipo": tipo,
        "categoria": cat,
        "monto": monto,
        "descripcion": desc
    })
    
    # Keep only last 20 in history for performance
    data["historial_reciente"] = data["historial_reciente"][:20]
    
    if tipo == "INGRESO":
        data["ingresos_totales"] += monto
        data["balance"] += monto
    else:
        # Inicializar categoría si no existe
        if "gastos_por_categoria" not in data:
            data["gastos_por_categoria"] = {}
        if cat not in data["gastos_por_categoria"]:
            data["gastos_por_categoria"][cat] = 0
            
        data["gastos_totales"] += monto
        data["balance"] -= monto
        data["gastos_por_categoria"][cat] += monto
        
    with open(PERIODO_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Retornamos datos de alerta si aplica
    return _check_budget_alert(data, cat, tipo)

def _check_budget_alert(data: dict, cat: str, tipo: str):
    """Verifica si el gasto actual supera el presupuesto de la categoría."""
    if tipo != "GASTO" or "presupuestos" not in data:
        return None
        
    limite = data["presupuestos"].get(cat)
    if not limite:
        return None
        
    actual = data["gastos_por_categoria"].get(cat, 0)
    porcentaje = (actual / limite) * 100
    bar = generate_progress_bar(porcentaje)
    
    if actual > limite:
        return f"⚠️ *ALERTA:* Has superado tu presupuesto en *{cat}*!\n{bar} ({porcentaje:.1f}%)\nGastado: ${actual:,.0f} de ${limite:,.0f}"
    elif actual > (limite * 0.8):
        return f"💡 *AVISO:* Estás cerca del límite en *{cat}*!\n{bar} ({porcentaje:.1f}%)\nGastado: ${actual:,.0f} de ${limite:,.0f}"
        
    return None

def _generate_empty_periodo():
    return {
        "inicio_periodo": datetime.datetime.now().strftime("%Y-%m-%d"),
        "ingresos_totales": 0,
        "gastos_totales": 0,
        "balance": 0,
        "gastos_por_categoria": {},
        "transacciones_registradas": 0,
        "historial_reciente": [],
        "presupuestos": {}
    }

def update_budget(category: str, amount: int):
    """Actualiza o crea un presupuesto para una categoría."""
    cat = normalize_category(category)
    data = get_periodo_data()
    if "presupuestos" not in data:
        data["presupuestos"] = {}
    
    # Limpiar duplicados si existen (por si acaso había uno mal escrito antes)
    if "presupuestos" in data:
        keys_to_del = [k for k in data["presupuestos"] if normalize_category(k) == cat and k != cat]
        for k in keys_to_del:
            del data["presupuestos"][k]

    data["presupuestos"][cat] = amount
    with open(PERIODO_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def delete_transaction(tx_id: str) -> bool:
    """Elimina una transacción por ID y recalcula los totales."""
    if not os.path.exists(PERIODO_JSON):
        return False
    
    with open(PERIODO_JSON, "r") as f:
        data = json.load(f)
        
    historial = data.get("historial_reciente", [])
    found_tx = None
    for tx in historial:
        if tx["id"] == tx_id:
            found_tx = tx
            break
            
    if not found_tx:
        return False
        
    # Recalcular totales
    tipo = found_tx["tipo"].upper()
    cat = found_tx["categoria"]
    monto = found_tx["monto"]
    
    data["transacciones_registradas"] -= 1
    if tipo == "INGRESO":
        data["ingresos_totales"] -= monto
        data["balance"] -= monto
    else:
        data["gastos_totales"] -= monto
        data["balance"] += monto
        if cat in data["gastos_por_categoria"]:
            data["gastos_por_categoria"][cat] -= monto
            if data["gastos_por_categoria"][cat] < 0:
                data["gastos_por_categoria"][cat] = 0
                
    data["historial_reciente"] = [tx for tx in historial if tx["id"] != tx_id]
    
    with open(PERIODO_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return True

def reset_periodo():
    """Borra los registros de transacciones pero MANTIENE los presupuestos."""
    old_data = get_periodo_data()
    presupuestos = old_data.get("presupuestos", {})
    
    data = _generate_empty_periodo()
    data["presupuestos"] = presupuestos # Mantener metas
    
    with open(PERIODO_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data

def get_periodo_data() -> dict:
    if os.path.exists(PERIODO_JSON):
        with open(PERIODO_JSON, "r") as f:
            return json.load(f)
    return {}

def _save_periodo_data(data: dict):
    _ensure_dir_exists(os.path.dirname(PERIODO_JSON))
    with open(PERIODO_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def set_chat_id(chat_id: int):
    """Guarda el chat_id del usuario para los reportes automáticos."""
    data = get_periodo_data()
    data["owner_chat_id"] = chat_id
    _save_periodo_data(data)

def get_chat_id() -> Optional[int]:
    """Obtiene el chat_id guardado."""
    data = get_periodo_data()
    return data.get("owner_chat_id")

def append_to_memory(note: str):
    """
    Agrega un patrón aprendido a MEMORY.md
    """
    _ensure_dir_exists(os.path.dirname(MEMORY_MD))
    if not os.path.exists(MEMORY_MD):
        with open(MEMORY_MD, "w") as f:
            f.write("# MEMORY.md\n\nRegistro de patrones aprendidos sobre los hábitos de Manuel:\n")
    
    with open(MEMORY_MD, "a") as f:
        f.write(f"- {note}\n")

def get_all_transactions_df():
    """Genera un DataFrame con todas las transacciones guardadas en los archivos MD."""
    import pandas as pd
    import re
    
    all_rows = []
    if not os.path.exists(MEMORY_DIR):
        return pd.DataFrame()
        
    for filename in sorted(os.listdir(MEMORY_DIR)):
        if filename.endswith(".md"):
            fecha = filename.replace(".md", "")
            path = os.path.join(MEMORY_DIR, filename)
            with open(path, "r") as f:
                lines = f.readlines()
                for line in lines:
                    # Formato: - [HH:MM:SS] TIPO — CAT — $MONTO — DESC (SOURCE)
                    match = re.match(r"- \[(.*)\] (.*) — (.*) — \$(.*) — (.*) \((.*)\)", line.strip())
                    if match:
                        all_rows.append({
                            "Fecha": fecha,
                            "Hora": match.group(1),
                            "Tipo": match.group(2),
                            "Categoría": normalize_category(match.group(3)),
                            "Monto": float(match.group(4).replace(",", "")),
                            "Descripción": match.group(5),
                            "Origen": match.group(6)
                        })
    
    return pd.DataFrame(all_rows)
