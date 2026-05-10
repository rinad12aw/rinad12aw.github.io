import sqlite3

DB_PATH = "../model/uti.db"

def get_connection():
    return sqlite3.connect(DB_PATH)