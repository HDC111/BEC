import psycopg2
from psycopg2 import sql
import sys
import getpass

def create_db_and_user(config):
    user = config["postgres"]["user"]
    password = config["postgres"]["password"]
    host = config["postgres"].get("host", "localhost")
    port = config["postgres"].get("port", 5432)

    dbs_to_create = [
        config["postgres"]["db_name"],       # Superset metadata DB
        config["postgres"]["name"]           # Logs DB
    ]

    try:
        # Prompt for PostgreSQL admin password
        print("🔐 This script requires the PostgreSQL admin password.")
        print("ℹ️  This is the password you set when you installed PostgreSQL.")
        admin_user = "postgres"
        admin_password = getpass.getpass(prompt=f"🔑 Enter PostgreSQL admin password for user '{admin_user}': ")

        # Connect to the default 'postgres' database
        conn = psycopg2.connect(
            dbname="postgres",
            user=admin_user,
            password=admin_password,
            host=host,
            port=port
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Create user if not exists
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE USER {} WITH PASSWORD %s").format(sql.Identifier(user)), [password])
            print(f"✅ User '{user}' created.")
        else:
            print(f"ℹ️ User '{user}' already exists.")

        # Create databases and assign privileges
        for db_name in dbs_to_create:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if not cur.fetchone():
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
                print(f"✅ Database '{db_name}' created.")
            else:
                print(f"ℹ️ Database '{db_name}' already exists.")

            cur.execute(sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier(db_name), sql.Identifier(user)))
            print(f"✅ Privileges granted on '{db_name}' to '{user}'.")

            # Connect to the created DB to grant detailed access
            schema_conn = psycopg2.connect(
                dbname=db_name,
                user=admin_user,
                password=admin_password,
                host=host,
                port=port
            )
            schema_conn.autocommit = True
            schema_cur = schema_conn.cursor()

            # Grant schema usage and creation
            schema_cur.execute(sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(sql.Identifier(user)))
            schema_cur.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(user)))

            # Grant full access to all tables and sequences
            schema_cur.execute(sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(user)))
            schema_cur.execute(sql.SQL("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(user)))

            # Set default privileges for future tables and sequences
            schema_cur.execute(sql.SQL("""
                ALTER DEFAULT PRIVILEGES IN SCHEMA public
                GRANT ALL ON TABLES TO {};
            """).format(sql.Identifier(user)))

            schema_cur.execute(sql.SQL("""
                ALTER DEFAULT PRIVILEGES IN SCHEMA public
                GRANT ALL ON SEQUENCES TO {};
            """).format(sql.Identifier(user)))

            print(f"✅ Full schema, table, and sequence access granted on '{db_name}.public' to '{user}'.")

            schema_cur.close()
            schema_conn.close()

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error during DB/User setup: {e}")
        sys.exit(1)
