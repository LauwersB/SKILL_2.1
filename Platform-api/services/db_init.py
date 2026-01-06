import psycopg2
import bcrypt
import logging
import config
import time

logger = logging.getLogger(__name__)

# Geef 'cur' mee als argument zodat de functie weet welke verbinding te gebruiken
def create_user_if_not_exists(cur, username, password, role, client_name):
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    if not cur.fetchone():
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        cur.execute("""
                    INSERT INTO users (username, password_hash, role, client_name)
                    VALUES (%s, %s, %s, %s)
                    """, (username, hashed, role, client_name))
        logger.info(f"Gebruiker '{username}' aangemaakt.")

def init_platform_db():
    print("--- DB INIT: Start procedure ---")
    conn = None
    retries = 5

    while retries > 0:
        try:
            conn = psycopg2.connect(
                host=config.db_host,
                user=config.username,
                password=config.password,
                dbname=config.db_name,
                connect_timeout=5
            )
            break
        except Exception as e:
            retries -= 1
            print(f"--- DB INIT: Wachten op DB... ({retries} pogingen over) ---")
            time.sleep(3)

    if not conn:
        print("❌ Kon geen verbinding maken.")
        return

    try:
        cur = conn.cursor()

        # 1. Maak tabellen
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                client_name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS provisions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                app_id VARCHAR(255) UNIQUE NOT NULL,
                db_name VARCHAR(255),
                db_user VARCHAR(255),
                db_password VARCHAR(255),
                db_port INTEGER,
                web_port INTEGER,
                container_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Gebruik de cursor (cur) bij het aanroepen!
        create_user_if_not_exists(cur, config.admin_user, config.admin_pass, "admin", "internal")

        conn.commit() # Nu wordt alles pas echt opgeslagen
        cur.close()
        print("✅ Database succesvol geïnitialiseerd.")

    except Exception as e:
        print(f"❌ Fout bij initialiseren database: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()