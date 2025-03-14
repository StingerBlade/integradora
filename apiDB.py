import os
from pymongo import MongoClient

# Usar la variable de entorno o un valor predeterminado (para desarrollo local)
uri = os.environ.get("MONGODB_URI_1", "mongodb+srv://valeria:valeria@integradora.rr5fz.mongodb.net/?retryWrites=true&w=majority&appName=Integradora")

client = MongoClient(uri)
db = client["valeria"]
collection = db["usuarios"]