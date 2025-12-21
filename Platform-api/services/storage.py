import psycopg2
import os

def save_provision_record(app_id, db_name, db_user, db_password, db_port, container_id):
    conn = psycopg2.connect(
        host=os.getenv("PLATFORM_DB_HOST"),
        user=os.getenv("PLATFORM_DB_USER"),
        password=os.getenv("PLATFORM_DB_PASSWORD"),
        dbname=os.getenv("PLATFORM_DB_NAME")
    )

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO provisions (app_id, db_name, db_user, db_password, db_port, container_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (app_id, db_name, db_user, db_password, db_port, container_id))

    conn.commit()
    cur.close()
    conn.close()

