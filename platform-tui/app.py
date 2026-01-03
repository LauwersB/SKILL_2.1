import requests
import psycopg2
import bcrypt
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, Input, DataTable, Static
from textual.containers import Container, Vertical, Horizontal
from textual import on, work
import config

# API Instellingen
API_URL = "http://skill_21-platform-api-1:8080"


class TuiApp(App):
    CSS = """
        Screen { align: center middle; }

        /* LOGIN */
        #login-box { width: 50; height: auto; border: solid green; padding: 1; }
        .hidden { display: none; }
        #error-msg { color: red; margin: 1 0; }

        /* HEADER */
        .header-bar { height: 3; width: 100%; padding: 0 1; background: $boost; margin-bottom: 1; layout: horizontal; }
        #welcome-text { width: 1fr; content-align: left middle; }
        #btn-logout { width: 16; }

        /* SECTIES */
        .section-box { border: solid $primary; padding: 1; margin-bottom: 1; height: auto; width: 100%; }
        .section-title { text-style: bold; color: $accent; }

        /* TABEL FIX: Zorgt dat de lijn niet verspringt */
        DataTable { 
            height: auto; 
            max-height: 8; 
            width: 100%; 
            margin: 1 0; 
            border: none; /* De rand komt al van de section-box */
        }

        /* ACTIEBALK ONDERAAN */
        #action-bar { 
            height: 3; 
            width: 100%; 
            layout: horizontal; 
            align: left middle;
        }

        /* Knoppen uniform maken om 'verspringende lijnen' te voorkomen */
        #action-bar Button { 
            min-width: 14;
            height: 3;        /* Genoeg ruimte voor tekst */
            margin-right: 1;
            border: tall $primary-darken-2; /* Allemaal dezelfde border-stijl */
        }

        /* Verwijderknop kleur, maar behoud dezelfde afmetingen */
        #btn-delete {
            background: $error;
            border: tall $error-darken-2;
        }
        """

    current_user = None
    selected_app_id = None

    def compose(self) -> ComposeResult:
        yield Header()

        # --- 1. LOGIN SCHERM ---
        with Container(id="login-box"):
            yield Label("🔐 Skill-21 Hosting Login")
            yield Input(placeholder="Gebruikersnaam", id="user")
            yield Input(placeholder="Wachtwoord", password=True, id="pass")
            yield Button("Inloggen", id="login-btn", variant="primary")
            yield Label("", id="error-msg", classes="hidden")

        # --- 2. DASHBOARD (Initieel verborgen) ---
        with Vertical(id="dashboard", classes="hidden"):
            # Welkomsttekst & Uitlog knop
            with Horizontal(classes="header-bar"):
                yield Label("Welkom", id="welcome-text")
                yield Button("Uitloggen", id="btn-logout", variant="error")

            # --- SECTIE A: KLANTENLIJST (Alleen zichtbaar voor ADMIN) ---
            # In Sectie A: KLANTEN
            with Vertical(id="section-clients", classes="hidden section-box"):
                yield Label("👥 Klanten Beheer", classes="section-title")
                yield DataTable(id="table-clients", cursor_type="row")

                yield Button("+ Nieuwe Gebruiker", id="btn-toggle-new-user", variant="success")

                # Het formulier (standaard verborgen)
                with Vertical(id="new-user-box", classes="hidden"):
                    yield Input(placeholder="Gebruikersnaam", id="in-user-name")
                    yield Input(placeholder="Wachtwoord", password=True, id="in-user-pass")
                    yield Label("Rol:")
                    # Een simpele switch of select voor rol
                    yield Button("Rol: user", id="btn-role-toggle")
                    yield Input(placeholder="Klantnaam (bijv. Test_Client)", id="in-user-client")
                    with Horizontal():
                        yield Button("💾 Opslaan", id="btn-save-user", variant="primary")
                        yield Button("Annuleren", id="btn-cancel-user")

            # --- SECTIE B: PROJECTEN (Voor ADMIN & USER) ---
            with Vertical(id="section-projects", classes="hidden section-box"):
                yield Label("📦 Projecten Overzicht", classes="section-title", id="lbl-projects")

                # Tabel met projecten
                yield DataTable(id="table-projects", cursor_type="row")

                # Nieuw project starten (Github Link)
                yield Button("+ Start Nieuw Project", id="btn-toggle-new-project", variant="success")

                with Vertical(id="new-project-box", classes="hidden"):
                    yield Label("Github Clone URL:")
                    yield Input(placeholder="https://github.com/jouwnaam/jouw-project.git", id="input-github")
                    with Horizontal():
                        yield Button("🚀 Deploy Nu", id="btn-deploy-confirm", variant="warning")
                        yield Button("Annuleren", id="btn-deploy-cancel", variant="default")

            # --- SECTIE C: CONTAINERS & ACTIES (Wordt zichtbaar na klik op project) ---
            with Vertical(id="section-containers", classes="hidden section-box"):
                yield Label("⚙️ Live Containers (Stack)", classes="section-title", id="lbl-containers")
                yield DataTable(id="table-containers", cursor_type="row")

                # De actiebalk
                with Horizontal(id="action-bar"):
                    yield Button("🔄 Update", id="btn-update")
                    yield Button("⏸️ Pauze", id="btn-pause")
                    yield Button("📜 Logs", id="btn-logs")
                    yield Button("ℹ️ Info", id="btn-info")
                    yield Button("🗑️ Verwijderen", id="btn-delete", variant="error")


        yield Footer()

    # --- DATABASES & API ---
    def get_db_connection(self):
        return psycopg2.connect(
            host=config.db_host, user=config.username,
            password=config.password, dbname=config.db_name
        )

    def fetch_api_containers(self):
        try:
            # Haalt live data uit /containers
            response = requests.get(f"{API_URL}/containers?all=true", timeout=2)
            if response.status_code == 200:
                return response.json().get("containers", [])
        except Exception:
            return []
        return []

    # --- INTERACTIE ---
    @on(Button.Pressed)
    def handle_buttons(self, event: Button.Pressed):
        btn = event.button.id

        if btn == "login-btn":
            self.check_login()
        elif btn == "btn-logout":
            self.logout()

        # Nieuw project UI
        elif btn == "btn-toggle-new-project":
            self.query_one("#new-project-box").remove_class("hidden")
            self.query_one("#input-github").focus()
        elif btn == "btn-deploy-cancel":
            self.query_one("#new-project-box").add_class("hidden")
        elif btn == "btn-deploy-confirm":
            url = self.query_one("#input-github").value
            self.notify(f"🚀 Deploy gestart voor: {url}")
            # HIER later de API call naar /deploy/full-stack toevoegen
            self.query_one("#new-project-box").add_class("hidden")

        # Container Acties
        elif btn in ["btn-update", "btn-pause", "btn-logs", "btn-info", "btn-delete"]:
            if not self.selected_app_id:
                self.notify("⚠️ Selecteer eerst een project!", severity="warning")
                return
            self.notify(f"Actie '{btn}' uitgevoerd op {self.selected_app_id}")

    @on(DataTable.RowSelected)
    def on_table_select(self, event: DataTable.RowSelected):
        table_id = event.data_table.id
        row_key = event.row_key.value

        if table_id == "table-clients":
            # Pak de waarde uit de TWEEDE kolom (index 1), dat is de 'Naam'
            # event.cursor_row geeft de index van de geselecteerde rij
            client_name = event.data_table.get_cell_at((event.cursor_row, 1))

            self.load_projects(user_id=row_key, client_name=client_name)
            self.query_one("#section-containers").add_class("hidden")

        elif table_id == "table-projects":
            self.selected_app_id = row_key
            self.load_containers(app_id=row_key)

    # --- LOGICA ---
    def check_login(self):
        username = self.query_one("#user").value
        password = self.query_one("#pass").value
        err_label = self.query_one("#error-msg")

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, password_hash, role, client_name FROM users WHERE username = %s", (username,))
            user_data = cur.fetchone()
            cur.close()
            conn.close()

            if user_data:
                user_id, hashed_pw, role, client_name = user_data
                if bcrypt.checkpw(password.encode(), hashed_pw.encode()):
                    self.current_user = {"id": user_id, "name": username, "role": role, "client": client_name}
                    self.setup_dashboard()
                    return

            err_label.update("❌ Foutieve gegevens!")
            err_label.remove_class("hidden")
        except Exception as e:
            err_label.update(f"⚠️ DB Fout: {e}")
            err_label.remove_class("hidden")

    def setup_dashboard(self):
        self.query_one("#login-box").add_class("hidden")
        self.query_one("#dashboard").remove_class("hidden")
        self.query_one("#welcome-text").update(f"Ingelogd: {self.current_user['name']}")

        if self.current_user['role'] == 'admin':
            # Admin: Ziet eerst klantenlijst
            self.query_one("#section-clients").remove_class("hidden")
            self.load_clients()
        else:
            # User: Ziet DIRECT projectenlijst en nieuwe project knop
            self.query_one("#section-clients").add_class("hidden")
            self.load_projects(user_id=self.current_user['id'], client_name=self.current_user['client'])

    def logout(self):
        self.current_user = None
        self.query_one("#dashboard").add_class("hidden")
        self.query_one("#section-containers").add_class("hidden")
        self.query_one("#section-projects").add_class("hidden")
        self.query_one("#login-box").remove_class("hidden")
        self.query_one("#user").value = ""
        self.query_one("#pass").value = ""

    def load_clients(self):
        table = self.query_one("#table-clients")
        table.clear(columns=True)  # Reset de hele tabel inclusief kolommen
        table.add_columns("ID", "Naam", "Rol", "Client")

        conn = self.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, client_name FROM users ORDER BY id ASC")
        for r in cur.fetchall():
            # We voegen de rij toe en gebruiken de Database ID als row_key
            table.add_row(str(r[0]), r[1], r[2], r[3], key=str(r[0]))
        cur.close()
        conn.close()

    def load_projects(self, user_id, client_name):
        self.query_one("#section-projects").remove_class("hidden")
        self.query_one("#lbl-projects").update(f"📦 Projecten van: {client_name}")

        table = self.query_one("#table-projects")
        table.clear(columns=True)
        table.add_columns("App ID", "Web Port", "DB Port", "Status")

        conn = self.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT app_id, web_port, db_port, container_id FROM provisions WHERE user_id = %s", (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if rows:
            for r in rows:
                table.add_row(r[0], str(r[1]), str(r[2]), r[3], key=r[0])
        else:
            self.notify("Geen projecten gevonden.")

    @on(Button.Pressed)
    def handle_user_actions(self, event: Button.Pressed):
        btn = event.button.id

        if btn == "btn-toggle-new-user":
            self.query_one("#new-user-box").remove_class("hidden")

        elif btn == "btn-role-toggle":
            # Simpele toggle tussen admin en user
            current = event.button.label
            event.button.label = "Rol: admin" if "user" in str(current) else "Rol: user"

        elif btn == "btn-cancel-user":
            self.query_one("#new-user-box").add_class("hidden")

        elif btn == "btn-save-user":
            self.action_create_user()

    def action_create_user(self):
        # Gegevens ophalen
        username = self.query_one("#in-user-name").value
        password = self.query_one("#in-user-pass").value
        role = "admin" if "admin" in str(self.query_one("#btn-role-toggle").label) else "user"
        client = self.query_one("#in-user-client").value

        if not username or not password:
            self.notify("⚠️ Vul alle velden in!", severity="error")
            return

        # API aanroep
        try:
            payload = {
                "username": username,
                "password": password,
                "role": role,
                "client_name": client
            }
            resp = requests.post(f"{API_URL}/users", json=payload, timeout=5)

            if resp.status_code == 201:
                self.notify(f"✅ Gebruiker {username} aangemaakt!")
                self.query_one("#new-user-box").add_class("hidden")
                self.load_clients()  # Ververs de tabel
            else:
                self.notify(f"❌ Fout: {resp.json().get('error')}", severity="error")
        except Exception as e:
            self.notify(f"❌ Verbinding mislukt: {e}", severity="error")

    @work(exclusive=True)
    async def load_containers(self, app_id):
        self.query_one("#section-containers").remove_class("hidden")
        self.query_one("#lbl-containers").update(f"⚙️ Stack info voor: {app_id}")

        table = self.query_one("#table-containers")
        table.clear(columns=True)
        table.add_columns("Container Naam", "Image", "Status", "CPU %", "RAM")

        all_containers = self.fetch_api_containers()
        project_containers = [c for c in all_containers if c['name'].startswith(app_id)]

        if not project_containers:
            table.add_row("Geen actieve containers", "-", "Offline", "-", "-")
        else:
            for c in project_containers:
                table.add_row(
                    c['name'], c['image'], c['state'],
                    c.get('cpu_percent', '0%'), c.get('mem_usage', '0MB')
                )


if __name__ == "__main__":
    app = TuiApp()
    app.run()