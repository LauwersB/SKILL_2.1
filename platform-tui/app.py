import requests
import psycopg2
import bcrypt
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, Input, DataTable, Static, LoadingIndicator, TextArea
from textual.screen import ModalScreen
from textual.containers import Container, Vertical, Horizontal
from textual import on, work
import config

# API Instellingen
API_URL = "http://skill_21-platform-api-1:8080"


class LogScreen(ModalScreen):
    """Een popup venster voor het bekijken van logs."""

    def __init__(self, app_id: str, log_content: str):
        super().__init__()
        self.app_id = app_id
        self.log_content = log_content

    def compose(self) -> ComposeResult:
        with Vertical(id="log-dialog"):
            yield Label(f"📄 Logs voor: {self.app_id}", id="log-title")

            # Maak de widget aan
            log_view = TextArea(self.log_content, id="log-area")
            # Zet hem op alleen-lezen
            log_view.read_only = True

            yield log_view
            yield Button("Sluiten", variant="primary", id="btn-close-logs")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-logs":
            self.app.pop_screen()


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
        
        /* LOADER FIX */
        LoadingIndicator {
            height: 3;
            color: $accent;
            content-align: center middle;
        }
        
        /* LOG MODAL */
        #log-dialog {
            padding: 1 2;
            background: $panel;
            border: thick $primary;
            width: 80%;
            height: 80%;
        }
        #log-title {
            text-style: bold;
            margin-bottom: 1;
        }
        #log-area {
            height: 1fr;
            border: solid $surface;
            background: $surface;
        }
        #btn-close-logs {
            margin-top: 1;
            width: 100%;
        }
        """

    current_user = None
    selected_app_id = None
    selected_client_name = None
    selected_user_id = None

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
                yield Button("Start/update Project", id="btn-toggle-new-project", variant="success")

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
                    yield Button("⏸️ Pauze", id="btn-pause")
                    yield Button("📜 Logs", id="btn-logs")
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
            self.action_deploy_project()
            self.query_one("#new-project-box").add_class("hidden")

            # Container Acties
        elif btn == "btn-pause":
            if not self.selected_app_id:
                self.notify("⚠️ Selecteer eerst een project!", severity="warning")
                return
            # DIT roept nu de API aanroep aan:
            self.action_pause_project()

        elif btn in ["btn-delete"]:
            if not self.selected_app_id:
                self.notify("⚠️ Selecteer eerst een project!", severity="warning")
                return
            self.action_delete_project()

        elif btn in ["btn-logs"]:
            if not self.selected_app_id:
                self.notify("⚠️ Selecteer eerst een project!", severity="warning")
                return
            self.action_fetch_logs()

    @on(DataTable.RowSelected)
    def on_table_select(self, event: DataTable.RowSelected):
        table_id = event.data_table.id
        row_key = event.row_key.value

        if table_id == "table-clients":
            # Pak de waarde uit de TWEEDE kolom (index 1), dat is de 'Naam'
            # event.cursor_row geeft de index van de geselecteerde rij
            self.selected_user_id = event.data_table.get_cell_at((event.cursor_row, 0))
            self.selected_client_name = event.data_table.get_cell_at((event.cursor_row, 3))

            self.load_projects(user_id=self.selected_user_id, client_name=self.selected_client_name)
            self.query_one("#section-containers").add_class("hidden")

        elif table_id == "table-projects":
            self.selected_app_id = event.row_key.value
            self.load_containers(app_id=self.selected_app_id)

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

        # We voegen kolommen toe die passen bij jouw specifieke data
        table.add_columns("Container Naam", "Status", "Gezondheid", "CPU %", "RAM Gebruik")

        try:
            # Gebruik het specifieke endpoint voor deze app_id
            url = f"{API_URL}/containers/{app_id}"

            worker = self.run_worker(
                lambda: requests.get(url, timeout=5),
                thread=True
            )
            resp = await worker.wait()

            if resp.status_code == 200:
                container_data = resp.json().get("containers", [])

                if not container_data:
                    table.add_row("Geen actieve containers", "-", "-", "-", "-")
                else:
                    for c in container_data:
                        # Hier mappen we de JSON velden naar de tabel
                        table.add_row(
                            c.get("name", "N/A"),
                            c.get("state", "offline"),
                            c.get("health", "unknown"),
                            c.get("cpu_percent", "0.00%"),
                            c.get("mem_usage", "0MiB / 0GiB")
                        )
            else:
                self.notify(f"❌ API Fout: {resp.status_code}", severity="error")

        except Exception as e:
            self.notify(f"❌ Verbinding mislukt: {e}", severity="error")
            table.add_row("Fout bij laden", "-", "-", "-", "-")

    @work(exclusive=True)
    async def action_deploy_project(self):
        github_url = self.query_one("#input-github").value

        # Bepaal de juiste client_name (Admin selectie OF eigen account)
        client_name = self.selected_client_name if self.current_user['role'] == 'admin' else self.current_user['client']

        if not github_url or not client_name:
            self.notify("⚠️ Github URL of Clientnaam ontbreekt!", severity="error")
            return

        # 1. We zoeken de sectie waar de loader moet komen
        project_section = self.query_one("#section-projects")
        # 2. We maken de loader aan
        loader = LoadingIndicator(id="deploy-loader")
        # 3. We plakken hem in het scherm
        await project_section.mount(loader)

        self.notify(f"🚀 Deploy gestart voor {client_name}...")
        self.query_one("#new-project-box").add_class("hidden")

        try:
            payload = {"client_name": client_name, "github_url": github_url}
            # We wachten op de API
            worker = self.run_worker(
                lambda: requests.post(f"{API_URL}/deploy/start", json=payload, timeout=120),
                thread=True
            )

            # We wachten op het resultaat van de worker
            resp = await worker.wait()

            if resp.status_code == 200:
                self.notify("✅ Project succesvol gedeployed!")
                self.load_projects(
                    user_id=self.selected_user_id or self.current_user['id'],
                    client_name=client_name
                )
            else:
                self.notify(f"❌ Fout: {resp.json().get('detail')}", severity="error")
        except Exception as e:
            self.notify(f"❌ Verbinding mislukt: {e}", severity="error")

        finally:
            # --- NIEUW: LAAD-INDICATOR VERWIJDEREN ---
            loader.remove()

    @work(exclusive=True)
    async def action_pause_project(self):
        full_app_id = self.selected_app_id
        client_name = self.selected_client_name if self.current_user['role'] == 'admin' else self.current_user['client']

        if not full_app_id or not client_name:
            self.notify("⚠️ Selectie onvolledig", severity="error")
            return

        # STRIP de client_name van de app_id om de pure projectnaam over te houden
        # We halen "{client_name}_" weg aan het begin van de string
        prefix = f"{client_name}_"
        if full_app_id.startswith(prefix):
            pure_project_name = full_app_id[len(prefix):]
        else:
            pure_project_name = full_app_id  # Fallback

        self.notify(f"⏸️ Pauzeren: {pure_project_name} (Klant: {client_name})")

        # DEBUG: Laat zien wat we gaan sturen
        self.notify(f"DEBUG STUREN: client={client_name}, project={pure_project_name}")

        if not pure_project_name or not client_name:
            self.notify("⚠️ App ID of Client Name ontbreekt!", severity="error")
            return

        # Loader logica
        try:
            old_loader = self.query_one("#pause-loader")
            old_loader.remove()
        except:
            pass

        container_section = self.query_one("#section-containers")
        loader = LoadingIndicator(id="pause-loader")
        await container_section.mount(loader)

        try:
            payload = {
                "client_name": client_name,
                "project_name": pure_project_name
            }

            # Gebruik de worker voor de request
            worker = self.run_worker(
                lambda: requests.post(f"{API_URL}/deploy/pauze", json=payload, timeout=30),
                thread=True
            )
            resp = await worker.wait()

            if resp.status_code == 200:
                self.notify(f"✅ Project {pure_project_name} gepauzeerd.")
                await self.load_containers(app_id=full_app_id)
            else:
                self.notify(f"❌ Fout: {resp.status_code}", severity="error")

        except Exception as e:
            self.notify(f"❌ Verbinding mislukt: {e}", severity="error")
        finally:
            loader.remove()

    @work(exclusive=True)
    async def action_delete_project(self):
        full_app_id = self.selected_app_id
        client_name = self.selected_client_name if self.current_user['role'] == 'admin' else self.current_user['client']

        if not full_app_id:
            self.notify("⚠️ Geen project geselecteerd", severity="warning")
            return

        prefix = f"{client_name}_"
        pure_project_name = full_app_id[len(prefix):] if full_app_id.startswith(prefix) else full_app_id

        # Loader initialisatie
        try:
            self.query_one("#delete-loader").remove()
        except:
            pass

        container_section = self.query_one("#section-containers")
        loader = LoadingIndicator(id="delete-loader")
        await container_section.mount(loader)

        self.notify(f"🗑️ Verwijderen van {pure_project_name} gestart...")

        try:
            payload = {
                "client_name": client_name,
                "project_name": pure_project_name
            }

            # We voeren de request uit in een worker
            # TIP: Verhoog de timeout naar 60 als het verwijderen van containers traag is
            worker = self.run_worker(
                lambda: requests.post(f"{API_URL}/deploy/verwijderen", json=payload, timeout=60),
                thread=True
            )
            resp = await worker.wait()

            # DEBUG: Print de status in je terminal om te zien wat er echt gebeurt
            print(f"DEBUG: API Status Code: {resp.status_code}")
            print(f"DEBUG: API Response Body: {resp.text}")

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    message = data.get('message', 'Project succesvol verwijderd')
                except:
                    message = "Project verwijderd (geen leesbaar antwoord van server)"

                self.notify(f"✅ {message}")

                # UI Updaten
                self.query_one("#section-containers").add_class("hidden")
                self.load_projects(user_id=self.selected_user_id or self.current_user['id'], client_name=client_name)

            else:
                # Als de status code niet 200 is, proberen we de fout te vinden
                try:
                    error_detail = resp.json().get('detail', 'Onbekende fout op server')
                except:
                    error_detail = f"Server gaf foutcode {resp.status_code}"

                self.notify(f"❌ Verwijderen mislukt: {error_detail}", severity="error")

        except requests.exceptions.Timeout:
            self.notify("❌ Time-out: De server doet er te lang over, maar de actie loopt mogelijk door.",
                        severity="error")
        except Exception as e:
            self.notify(f"❌ Verbinding mislukt: {str(e)}", severity="error")
        finally:
            loader.remove()

    @work(exclusive=True)
    async def action_fetch_logs(self):
        app_id = self.selected_app_id  # Hier hebben we de VOLLEDIGE id nodig (klant_project)

        if not app_id:
            self.notify("⚠️ Selecteer eerst een project!", severity="warning")
            return

        self.notify(f"⌛ Logs ophalen voor {app_id}...")

        try:
            # We vragen om 'raw' formaat zodat we één grote string krijgen voor de TextArea
            url = f"{API_URL}/apps/{app_id}/logs?format=raw&tail=100"

            worker = self.run_worker(
                lambda: requests.get(url, timeout=10),
                thread=True
            )
            resp = await worker.wait()

            if resp.status_code == 200:
                # Open de Modal met de ontvangen tekst
                self.push_screen(LogScreen(app_id, resp.text))
            else:
                detail = resp.json().get('detail', 'Onbekende fout')
                self.notify(f"❌ Logs mislukt: {detail}", severity="error")

        except Exception as e:
            self.notify(f"❌ Verbinding mislukt: {e}", severity="error")


if __name__ == "__main__":
    app = TuiApp()
    app.run()