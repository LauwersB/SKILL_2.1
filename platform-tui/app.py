from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, Input, DataTable
from textual.containers import Container, Vertical
import psycopg2
import bcrypt
import config


class TuiApp(App):
    CSS = """
    Screen { align: center middle; }
    #login-box { width: 50; height: auto; border: solid green; padding: 1; }
    .hidden { display: none; }
    #error-msg { color: red; margin: 1 0; }
    DataTable { height: 10; margin: 1 0; border: tall $primary; }
    """

    current_user = None

    def compose(self) -> ComposeResult:
        yield Header()

        # --- LOGIN SCHERM ---
        with Container(id="login-box"):
            yield Label("Welkom bij Skill-21 Hosting")
            yield Input(placeholder="Gebruikersnaam", id="user")
            yield Input(placeholder="Wachtwoord", password=True, id="pass")
            yield Button("Inloggen", id="login-btn", variant="primary")
            yield Label("", id="error-msg", classes="hidden")

        # --- DASHBOARD (Verborgen bij start) ---
        with Container(id="dashboard", classes="hidden"):
            yield Label("Jouw Projecten", id="welcome-text")
            yield DataTable(id="project-table")
            yield Button("Project Starten", id="btn-start")
            yield Button("Project Stoppen", id="btn-stop")
            yield Button("Logs Bekijken", id="btn-logs")
            yield Button("Afsluiten", id="btn-exit", variant="error")

        yield Footer()

    def get_db_connection(self):
        # We gebruiken hier de variabelen uit config.py
        return psycopg2.connect(
            host=config.db_host,
            user=config.username,
            password=config.password,
            dbname=config.db_name
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login-btn":
            self.check_login()
        elif event.button.id == "btn-exit":
            self.exit()  # Sluit app -> Sluit SSH verbinding
        elif event.button.id == "btn-stop":
            self.stop_selected_project()

    def check_login(self):
        username = self.query_one("#user").value
        password = self.query_one("#pass").value
        err_label = self.query_one("#error-msg")

        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            # Haal de user op uit de 'users' tabel
            cur.execute("SELECT id, password_hash, role, client_name FROM users WHERE username = %s", (username,))
            user_data = cur.fetchone()
            cur.close()
            conn.close()

            if user_data:
                user_id, hashed_pw, role, client_name = user_data
                # Check wachtwoord met bcrypt
                if bcrypt.checkpw(password.encode(), hashed_pw.encode()):
                    self.current_user = {
                        "id": user_id,
                        "name": username,
                        "role": role,
                        "client": client_name
                    }
                    self.switch_to_dashboard()
                    return

            err_label.update("❌ Foutieve gegevens!")
            err_label.remove_class("hidden")

        except Exception as e:
            err_label.update(f"⚠️ DB Fout: {e}")
            err_label.remove_class("hidden")

    def switch_to_dashboard(self):
        self.query_one("#login-box").add_class("hidden")
        self.query_one("#dashboard").remove_class("hidden")
        self.load_projects()

    def load_projects(self):
        table = self.query_one("#project-table")
        table.clear()
        table.add_columns("Project", "Status", "Poort")
        # Hier query je de 'provisions' tabel gefilterd op de klantnaam van de user
        table.add_row("mijn-website", "Running", "8081")

    def stop_selected_project(self):
        # Hier roep je jouw bestaande shell scripts aan
        # subprocess.run(["./stop_container.sh", self.current_user['client'], "mijn-website"])
        pass


if __name__ == "__main__":
    app = TuiApp()
    app.run()