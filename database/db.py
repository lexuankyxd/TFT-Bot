from pymongo import MongoClient

# Connection to localhost on default port 27017
# No username or password required in the connection string
client = MongoClient('mongodb://localhost:27017/')
MONGO_DB_NAME="TFT-MINED"

db = client[MONGO_DB_NAME]

def insert
