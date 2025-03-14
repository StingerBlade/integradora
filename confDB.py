import os
import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Usar la variable de entorno o un valor predeterminado (para desarrollo local)
uri = os.environ.get("MONGODB_URI_2", "mongodb+srv://arrasutch:gMx16JilorK0p0ee@integradora.rr5fz.mongodb.net/?retryWrites=true&w=majority&appName=Integradora")

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client["integradora"]