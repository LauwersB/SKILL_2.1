import psycopg2
import logging
import sys
from pathlib import Path
from psycopg2 import OperationalError, DatabaseError

# Zorg dat we de config.py uit de bovenliggende map kunnen importeren
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

logger = logging.getLogger(__name__)


def save_provision_record(app_id, db_name, db_user, db_password, db_port, container_id):
    """Sla provision record op in platform database met gebruik van centrale config."""
    conn = None
    try:
        # We gebruiken nu de namen die jij in config.py hebt gedefinieerd
        conn = psycopg2.connect(
            host=config.db_host,
            user=config.username,
            password=config.password,
            dbname=config.db_name,
            connect_timeout=5
        )

        cur = conn.cursor()

        # 1. Tabel aanmaken als deze nog niet bestaat
        cur.execute("""
            CREATE TABLE IF NOT EXISTS provisions (
                id SERIAL PRIMARY KEY,
                app_id VARCHAR(255) UNIQUE NOT NULL,
                db_name VARCHAR(255) ,
                db_user VARCHAR(255) ,
                db_password VARCHAR(255) ,
                db_port INTEGER ,
                web_port INTEGER ,
                container_id VARCHAR(255) ,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Record invoegen of bijwerken (Upsert)
        # Dit voorkomt 'Unique Violation' errors als je een app her-deploys
        cur.execute("""
            INSERT INTO provisions (app_id, db_name, db_user, db_password, db_port, container_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (app_id) DO UPDATE SET
                db_name = EXCLUDED.db_name,
                db_user = EXCLUDED.db_user,
                db_password = EXCLUDED.db_password,
                db_port = EXCLUDED.db_port,
                container_id = EXCLUDED.container_id;
        """, (app_id, db_name, db_user, db_password, db_port, container_id))

        conn.commit()
        cur.close()
        logger.info(f"Provision record succesvol verwerkt voor app_id: {app_id}")

    except OperationalError as e:
        logger.error(f"Database connectie fout (Check of platform-db draait): {e}")
        raise
    except DatabaseError as e:
        logger.error(f"Database query fout: {e}")
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        logger.error(f"Onverwachte fout in storage.py: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()