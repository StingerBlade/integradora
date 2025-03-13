from pymongo import MongoClient

uri = "mongodb+srv://valeria:valeria@integradora.rr5fz.mongodb.net/?retryWrites=true&w=majority&appName=Integradora"

client = MongoClient(uri)
db = client["valeria"]
collection = db["usuarios"]
