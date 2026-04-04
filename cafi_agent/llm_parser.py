import os
import json
from groq import Groq
import datetime
import base64

client = None

def init_llm():
    global client
    api_key = os.getenv("GROQ_API_KEY")
    if api_key and api_key != "tu_api_key_de_groq_aqui":
        client = Groq(api_key=api_key)
    else:
        print("Warning: GROQ_API_KEY no encontrada en variables de entorno.")

def encode_image(image_path: str):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def parse_transaction(text: str = None, image_path: str = None, current_date: str = None) -> dict:
    global client
    if not client:
        return {"ambiguo": True, "razon_ambiguedad": "La API Key de GROQ no ha sido pegada correctamente en el archivo .env."}

    if not current_date:
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    system_prompt = f"""
Eres CAFI, un agente experto en finanzas.
Tu objetivo es extraer información de una transacción (gasto o ingreso) contenida en la petición del usuario.
Reglas:
1. Extrae: "fecha", "tipo" (INGRESO o GASTO), "categoria", "monto" (entero positivo), "descripcion" (pequeño texto de 3-4 palabras).
2. Categorías permitidas GASTO: Alimentación, Transporte, Salud, Gimnasio / Deporte, Educación, Entretenimiento, Ropa, Servicios, Arriendo, Suscripciones, Otros.
3. Categorías permitidas INGRESO: Trabajo fijo, Freelance / Consultoría, Transferencia, Reembolso, Otros.
4. Si la fecha es ambigua (como "hoy"), usa esta fecha de hoy como referencia: {current_date}. Retorna YYYY-MM-DD.
5. Si falta un monto, es incomprensible, o no tiene sentido financiero, pon "ambiguo": true y en "razon_ambiguedad" dile brevemente al usuario qué quieres que aclare.
6. Si la información es clara y pudiste rellenar todo, pon "ambiguo": false y "razon_ambiguedad": null.

NO PUEDES DEVOLVER OTRA COSA QUE NO SEA JSON. SIN BACKTICKS (```), SIN MARKDOWN, SOLO EL JSON ASÍ:
{{
  "fecha": "YYYY-MM-DD",
  "tipo": "GASTO",
  "categoria": "Transporte",
  "monto": 15000,
  "descripcion": "transporte viaje uber",
  "ambiguo": false,
  "razon_ambiguedad": null
}}
"""

    messages = [{"role": "system", "content": system_prompt}]
    
    user_content = []
    if text:
        user_content.append({"type": "text", "text": text})
    else:
        user_content.append({"type": "text", "text": "Analiza la imagen adjunta para extraer la información financiera."})

    model_name = "llama-3.3-70b-versatile" # Por defecto el mejor para texto en Groq
    
    if image_path:
        try:
            base64_image = encode_image(image_path)
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })
            # Groq model para imágenes
            model_name = "llama-3.2-90b-vision-preview"
        except Exception as e:
            print(f"Error codificando la imagen: {e}")
            return {"ambiguo": True, "razon_ambiguedad": "Hubo un error cargando o entendiendo la imagen que me enviaste."}

    messages.append({"role": "user", "content": user_content})

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0 # Lo más determinista posible
        )
        content = response.choices[0].message.content.strip()
        
        # Limpieza de Markdown si LLama alucina los backticks por costumbre
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        data = json.loads(content)
        return data
    except Exception as e:
        error_msg = str(e)
        print(f"Error grave procesando LLM Groq: {error_msg}")
        return {"ambiguo": True, "razon_ambiguedad": "Recibí una respuesta confusa internamente o no fue muy claro el texto. ¿Puedes replantearlo?"}

def analyze_habits(history: list, current_memory: str = "") -> list:
    """
    Analiza el historial de transacciones para extraer patrones, consejos y preferencias.
    Retorna una lista de strings con nuevos insights.
    """
    global client
    if not client or not history:
        return []

    history_str = json.dumps(history, indent=2, ensure_ascii=False)
    
    system_prompt = f"""
Eres la 'Consciencia Financiera' de CAFI.
Tu tarea es analizar el historial de transacciones de Manuel y extraer INSIGHTS significativos (patrones, gastos hormiga, consejos de ahorro o preferencias de categorización).

Reglas para los INSIGHTS:
1. Sé breve y directo (máximo 15-20 palabras por cada uno).
2. Enfócate en tendencias (ej: "Has gastado mucho en café esta semana" o "Sueles registrar Uber como Transporte").
3. No repitas consejos que ya están en la memoria actual.
4. Si no hay nada interesante, no inventes, devuelve una lista vacía.
5. Evita juicios de valor pesados; sé un asistente útil.

Memoria actual para contexto:
{current_memory}

Responde ÚNICAMENTE con una lista de strings en formato JSON: ["insight 1", "insight 2", ...]
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Aquí está mi historial reciente:\n{history_str}"}
            ],
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        
        # Limpieza simple
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        insights = json.loads(content)
        if isinstance(insights, list):
            return insights
        return []
    except Exception as e:
        print(f"Error en análisis de hábitos: {e}")
        return []

