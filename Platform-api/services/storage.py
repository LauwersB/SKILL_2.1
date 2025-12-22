import psycopg2
import os
import logging
from psycopg2 import OperationalError, DatabaseError

logger = logging.getLogger(__name__)

def save_provision_record(app_id, db_name, db_user, db_password, db_port, container_id):
    """Sla provision record op in platform database met error handling."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("PLATFORM_DB_HOST", "platform-db"),
            user=os.getenv("PLATFORM_DB_USER", "platform"),
            password=os.getenv("PLATFORM_DB_PASSWORD", "platform123"),
            dbname=os.getenv("PLATFORM_DB_NAME", "platform"),
            connect_timeout=5
        )

        cur = conn.cursor()
        
        # Check of tabel bestaat, zo niet maak aan
        cur.execute("""
            CREATE TABLE IF NOT EXISTS provisions (
                id SERIAL PRIMARY KEY,
                app_id VARCHAR(255) UNIQUE NOT NULL,
                db_name VARCHAR(255) NOT NULL,
                db_user VARCHAR(255) NOT NULL,
                db_password VARCHAR(255) NOT NULL,
                db_port INTEGER NOT NULL,
                container_id VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert record (simpel: gewoon INSERT)
        cur.execute("""
            INSERT INTO provisions (app_id, db_name, db_user, db_password, db_port, container_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (app_id, db_name, db_user, db_password, db_port, container_id))

        conn.commit()
        cur.close()
        logger.info(f"Provision record opgeslagen voor app_id: {app_id}")
        
    except OperationalError as e:
        logger.error(f"Database connectie fout: {e}")
        raise
    except DatabaseError as e:
        logger.error(f"Database fout: {e}")
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Onverwachte fout bij opslaan provision record: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

