#Detectar que modelos de vision tienes disponible en tu cuenta groq

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq()
models = client.models.list()
for m in models.data:
    if "vision" in m.id:
        print(m.id)
