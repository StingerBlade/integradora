import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Obtener URI de MongoDB desde variables de entorno
uri = os.getenv('MONGODB_URI_1')
if not uri:
    raise ValueError("MONGODB_URI_1 no está configurada en las variables de entorno")

client = MongoClient(uri)
db = client["valeria"]
collection = db["usuarios"]