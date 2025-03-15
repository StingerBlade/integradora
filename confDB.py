import os
import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Obtener URI de MongoDB desde variables de entorno
uri = os.getenv('MONGODB_URI_2')
if not uri:
    raise ValueError("MONGODB_URI_2 no está configurada en las variables de entorno")

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client["integradora"]