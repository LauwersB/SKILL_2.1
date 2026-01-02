import psycopg2
import bcrypt
import logging
import config
import time


logger = logging.getLogger(__name__)

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
            break  # Verbinding gelukt, breek uit de loop
        except Exception as e:
            retries -= 1
            print(f"--- DB INIT: Database niet bereikbaar. Pogingen over: {retries}. Fout: {e} ---")
            if retries == 0:
                print("--- DB INIT: Kritieke fout: Kon geen verbinding maken na 5 pogingen. ---")
                return  # Stop de functie
            time.sleep(3)  # Wacht 3 seconden voor de volgende poging

    try:
        cur = conn.cursor()

        # 1. Tabel voor Users/Klanten
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user', -- user, developer, admin
                client_name VARCHAR(100) NOT NULL, -- Gebruikt voor mapnaam /clients/naam
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Tabel voor Provisions (met FK naar users)
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

        # 2. Hulpfunctie voor het aanmaken van gebruikers
        def create_user_if_not_exists(username, password, role, client_name):
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if not cur.fetchone():
                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
                cur.execute("""
                            INSERT INTO users (username, password_hash, role, client_name)
                            VALUES (%s, %s, %s, %s)
                            """, (username, hashed, role, client_name))
                logger.info(f"Gebruiker '{username}' aangemaakt.")


        create_user_if_not_exists(config.admin_user, config.admin_pass, "admin", "internal")

        # 4. Testuser aanmaken
        create_user_if_not_exists("testuser", "123", "user", "test_client")

        conn.commit()
        cur.close()
        print("✅ Database succesvol geïnitialiseerd.")

    except Exception as e:
        print(f"❌ Fout bij initialiseren database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_platform_db()