import flet as ft
import datetime
import sqlite3
import os

# --- POPRAWIONA OBSŁUGA BAZY DANYCH (KOMPATYBILNA Z ANDROIDEM) ---
def get_db_path():
    # Sprawdzamy, czy program działa na telefonie, czy na komputerze
    # Flet na Androidzie ustawia zmienną środowiskową FLET_APP_STORAGE_DATA_DIR
    storage_path = os.environ.get("FLET_APP_STORAGE_DATA_DIR")
    
    if storage_path:
        # Jesteśmy na telefonie - zapisz w dedykowanym folderze
        return os.path.join(storage_path, "metamorfoza_v7.db")
    else:
        # Jesteśmy na komputerze - zapisz obok pliku .py
        return "metamorfoza_v7.db"

def init_db():
    db_path = get_db_path()
    # Upewnij się, że katalog istnieje (ważne na mobile)
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    except: pass
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    
    # ... (RESZTA TABEL BEZ ZMIAN) ...
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY,
            start_date TEXT, start_weight REAL, target_weight REAL,
            height REAL, age REAL, intensity REAL, photo_start TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY,
            date TEXT UNIQUE,
            weight REAL, waist REAL, notes TEXT, photo_path TEXT
        )
    """)
    conn.commit()
    return conn

def main(page: ft.Page):
    # --- KONFIGURACJA OKNA ---
    page.title = "METAMORFOZA PRO (FIXED)"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 10
    
    conn = init_db()

    # --- ZMIENNE STANU ---
    state = {
        "start_date": datetime.date.today(),
        "view_date": datetime.date.today(),
        "profile_loaded": False,
        "is_goal_reached": False
    }

    # --- 2. LOGIKA MATEMATYCZNA (POPRAWIONA) ---
    def calculate_stats():
        if not state["profile_loaded"]: return None
        
        cur = conn.cursor()
        cur.execute("SELECT * FROM profile ORDER BY id DESC LIMIT 1")
        p = cur.fetchone() 
        
        cur.execute("SELECT weight FROM daily_logs WHERE weight > 0 ORDER BY date DESC LIMIT 1")
        w_row = cur.fetchone()
        current_w = w_row[0] if w_row else p[2]
        
        # BMR
        bmr = (10 * current_w) + (6.25 * p[4]) - (5 * p[5]) + 5
        tdee = bmr * 1.4 
        
        start_w = p[2]
        target_w = p[3]
        intensity = p[6]
        
        result = {
            "tdee": int(tdee),
            "current_weight": current_w,
            "target_weight": target_w,
            "diff_total": abs(start_w - target_w),
            "diff_done": abs(start_w - current_w),
            "start_photo": p[7]
        }
        
        # Sprawdzenie czy osiągnięto cel (Metamorfoza zakończona)
        if (target_w < start_w and current_w <= target_w) or (target_w > start_w and current_w >= target_w):
            state["is_goal_reached"] = True
        else:
            state["is_goal_reached"] = False

        if target_w < start_w: # REDUKCJA
            deficit = tdee * intensity
            result["calories"] = int(tdee - deficit)
            result["mode"] = "Redukcja"
            result["mode_color"] = "green" if intensity <= 0.15 else "red"
            
            kg_left = current_w - target_w
            # ZMIANA: 7000 kcal zamiast 7700 kcal (uwzględnia utratę wody/glikogenu = szybszy wynik)
            if kg_left <= 0:
                result["days_left"] = 0
            else:
                result["days_left"] = int((kg_left * 7000) / deficit) if deficit > 0 else 999
        else: # MASA
            surplus = tdee * 0.10
            result["calories"] = int(tdee + surplus)
            result["mode"] = "Masa"
            result["mode_color"] = "blue"
            
            kg_left = target_w - current_w
            if kg_left <= 0:
                result["days_left"] = 0
            else:
                result["days_left"] = int((kg_left * 5000) / surplus) if surplus > 0 else 999
                
        result["progress"] = min(1.0, result["diff_done"] / result["diff_total"]) if result["diff_total"] > 0 else 0
        return result

    # --- 3. UI - DEKLARACJE ---
    
    # 3.1 DASHBOARD
    txt_dash_kcal = ft.Text("---", size=40, weight="bold", color="yellow")
    txt_dash_mode = ft.Text("---", size=16, color="white70")
    txt_dash_days = ft.Text("---", size=14, color="cyan")
    pb_dash_prog = ft.ProgressBar(width=None, value=0, color="green", bgcolor="white10", height=10)
    txt_dash_prog_perc = ft.Text("0%", size=12)
    
    # Panel Zwycięzcy (Porównanie zdjęć)
    img_final_start = ft.Image(src="", width=150, height=200, fit="cover", border_radius=10)
    img_final_end = ft.Image(src="https://via.placeholder.com/150?text=Twoje+Zdjecie", width=150, height=200, fit="cover", border_radius=10)
    
    goal_panel = ft.Container(
        content=ft.Column([
            ft.Text("GRATULACJE! CEL OSIĄGNIĘTY!", size=24, weight="bold", color="gold"),
            ft.Text("To moment na podsumowanie. Zobacz swoją drogę:", size=16),
            ft.Divider(),
            ft.Row([
                ft.Column([ft.Text("START"), img_final_start], horizontal_alignment="center"),
                ft.Icon(ft.icons.ARROW_FORWARD, size=40),
                ft.Column([ft.Text("TERAZ (FINAŁ)"), img_final_end], horizontal_alignment="center"),
            ], alignment="center", spacing=20),
            ft.Text("Aby dodać zdjęcie końcowe, wgraj je w panelu dziennym.", color="cyan", size=12),
        ], horizontal_alignment="center"),
        padding=30,
        bgcolor=ft.colors.with_opacity(0.2, "green"),
        border=ft.border.all(2, "gold"),
        border_radius=20,
        visible=False
    )

    # 3.2 DZIENNIK
    date_btn_display = ft.Text("Dzisiaj", size=16, weight="bold")
    input_weight = ft.TextField(label="Waga (kg)", width=120, text_align="right", border_color="green")
    input_waist = ft.TextField(label="Talia (cm)", width=120, text_align="right")
    input_notes = ft.TextField(label="Notatki (Trening / Samopoczucie)", multiline=True, min_lines=3)
    img_day_preview = ft.Image(src="", width=100, height=100, fit="cover", visible=False, border_radius=8)
    
    # 3.3 USTAWIENIA
    st_start_weight = ft.TextField(label="Start Waga (kg)", width=100)
    st_target_weight = ft.TextField(label="Cel Waga (kg)", width=100)
    st_height = ft.TextField(label="Wzrost (cm)", width=100)
    st_age = ft.TextField(label="Wiek", width=100)
    st_intensity = ft.Dropdown(
        label="Tryb Diety", width=180, value="0.14",
        options=[
            ft.dropdown.Option("0.10", "10% (Bezpieczna)"),
            ft.dropdown.Option("0.14", "14% (Naturalna)"),
            ft.dropdown.Option("0.20", "20% (Agresywna)"),
        ]
    )
    
    # 3.4 WYKRES (NAPRAWIONY)
    # Usunięto reserved_size, dodano inteligentne skalowanie w funkcji update
    chart_plot = ft.LineChart(
        data_series=[],
        border=ft.border.all(1, ft.colors.WHITE10),
        left_axis=ft.ChartAxis(labels_size=10), # Mała czcionka
        bottom_axis=ft.ChartAxis(labels_interval=1, labels_size=10),
        horizontal_grid_lines=ft.ChartGridLines(interval=1, color=ft.colors.WHITE10, width=1),
        min_y=0, max_y=150, 
        expand=True,
        tooltip_bgcolor=ft.colors.with_opacity(0.8, ft.colors.BLACK)
    )
    
    history_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Data")),
            ft.DataColumn(ft.Text("Waga"), numeric=True),
            ft.DataColumn(ft.Text("Talia"), numeric=True),
            ft.DataColumn(ft.Text("Notatka")),
        ],
        rows=[],
        border=ft.border.all(1, ft.colors.WHITE10),
        vertical_lines=ft.border.BorderSide(1, ft.colors.WHITE10),
        horizontal_lines=ft.border.BorderSide(1, ft.colors.WHITE10),
    )

    # --- 4. FUNKCJE POMOCNICZE (FORWARD DECLARATIONS) ---
    def load_daily_entry():
        date_str = state["view_date"].strftime("%Y-%m-%d")
        date_btn_display.value = date_str
        
        cur = conn.cursor()
        cur.execute("SELECT * FROM daily_logs WHERE date=?", (date_str,))
        row = cur.fetchone()
        
        if row: 
            input_weight.value = str(row[2]) if row[2] else ""
            input_waist.value = str(row[3]) if row[3] else ""
            input_notes.value = row[4] if row[4] else ""
            if row[5]:
                img_day_preview.src = row[5]
                img_day_preview.visible = True
            else:
                img_day_preview.visible = False
        else:
            input_weight.value = ""
            input_waist.value = ""
            input_notes.value = ""
            img_day_preview.visible = False
        page.update()

    def on_date_change(e):
        if e.control.value:
            state["view_date"] = e.control.value.date()
            load_daily_entry()

    def on_start_date_change(e):
         if e.control.value:
            state["start_date"] = e.control.value.date()

    # --- 5. TWORZENIE KONTROLEK SYSTEMOWYCH (PRZED UŻYCIEM - NAPRAWA BŁĘDU 1) ---
    first_date_limit = datetime.datetime(2000, 1, 1)
    last_date_limit = datetime.datetime(2030, 12, 31)

    date_picker_main = ft.DatePicker(
        on_change=on_date_change,
        first_date=first_date_limit, last_date=last_date_limit
    )
    date_picker_start = ft.DatePicker(
        on_change=on_start_date_change,
        first_date=first_date_limit, last_date=last_date_limit
    )
    
    def on_file_picked(e):
        if e.files:
            img_day_preview.src = e.files[0].path
            img_day_preview.visible = True
            if state["is_goal_reached"]:
                img_final_end.src = e.files[0].path
                img_final_end.update()
            page.update()

    file_picker = ft.FilePicker(on_result=on_file_picked)
    
    # Rejestracja w overlay
    page.overlay.extend([date_picker_main, date_picker_start, file_picker])

    # --- 6. FUNKCJE AKTUALIZACJI I ZAPISU ---

    def refresh_dashboard():
        data = calculate_stats()
        if data:
            txt_dash_kcal.value = f"{data['calories']} kcal"
            txt_dash_mode.value = f"Tryb: {data['mode']} (TDEE: {data['tdee']})"
            txt_dash_kcal.color = data['mode_color']
            txt_dash_days.value = f"Szacowany czas do celu: {data['days_left']} dni"
            pb_dash_prog.value = data['progress']
            txt_dash_prog_perc.value = f"{int(data['progress']*100)}%"

            if state["is_goal_reached"]:
                goal_panel.visible = True
                standard_dashboard.visible = False
                if data["start_photo"]: img_final_start.src = data["start_photo"]
                else: img_final_start.src = "https://via.placeholder.com/150?text=Brak+Start"
                
                if img_day_preview.visible: img_final_end.src = img_day_preview.src
            else:
                goal_panel.visible = False
                standard_dashboard.visible = True
        else:
            txt_dash_kcal.value = "Ustaw Profil"
        page.update()

    def update_charts_tab():
        if not state["profile_loaded"]: return
        
        cur = conn.cursor()
        cur.execute("SELECT date, weight, waist, notes FROM daily_logs ORDER BY date ASC")
        rows = cur.fetchall()
        
        points = []
        all_weights = []
        
        try:
            start_w = float(st_start_weight.value)
            points.append(ft.LineChartDataPoint(0, start_w))
            all_weights.append(start_w)
        except: pass

        dates_for_table = []
        
        for r in rows:
            dates_for_table.append(r)
            if r[1] and r[1] > 0:
                dt = datetime.datetime.strptime(r[0], "%Y-%m-%d").date()
                days_diff = (dt - state["start_date"]).days
                if days_diff >= 0:
                    points.append(ft.LineChartDataPoint(days_diff, r[1]))
                    all_weights.append(r[1])

        # --- NAPRAWA WYKRESU (Skalowanie) ---
        if points:
            min_w = min(all_weights)
            max_w = max(all_weights)
            weight_range = max_w - min_w
            
            # Margines góra/dół
            pad = 2 if weight_range < 5 else weight_range * 0.1
            
            current_min = max(0, min_w - pad)
            current_max = max_w + pad
            
            # Obliczenie Interwału, aby liczby się nie nakładały
            # Chcemy max 5 etykiet na osi Y
            total_span = current_max - current_min
            interval = total_span / 5
            if interval < 1: interval = 1

            chart_plot.min_y = current_min
            chart_plot.max_y = current_max
            chart_plot.left_axis.interval = interval # <--- TO NAPRAWIA NAKŁADANIE
            chart_plot.horizontal_grid_lines.interval = interval

            chart_plot.data_series = [
                ft.LineChartData(
                    points, 
                    color="cyan", 
                    stroke_width=4, 
                    curved=True, 
                    below_line_bgcolor=ft.colors.with_opacity(0.1, ft.colors.CYAN),
                    point=True
                )
            ]
        
        history_table.rows.clear()
        for r in reversed(dates_for_table):
            history_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(r[0])),
                    ft.DataCell(ft.Text(str(r[1]) if r[1] else "-")),
                    ft.DataCell(ft.Text(str(r[2]) if r[2] else "-")),
                    ft.DataCell(ft.Text(r[3][:30] + "..." if r[3] else "")),
                ])
            )
        page.update()

    def save_day_action(e):
        try:
            date_str = state["view_date"].strftime("%Y-%m-%d")
            w = float(input_weight.value) if input_weight.value else 0
            waist = float(input_waist.value) if input_waist.value else 0
            note = input_notes.value
            photo = img_day_preview.src if img_day_preview.visible else None
            
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO daily_logs (date, weight, waist, notes, photo_path)
                VALUES (?, ?, ?, ?, ?)
            """, (date_str, w, waist, note, photo))
            conn.commit()
            
            page.snack_bar = ft.SnackBar(ft.Text("Zapisano dane dnia!"), bgcolor="green")
            page.snack_bar.open = True
            
            refresh_dashboard()
            update_charts_tab()
            page.update()
        except ValueError:
            page.snack_bar = ft.SnackBar(ft.Text("Błąd: Waga musi być liczbą!"), bgcolor="red")
            page.snack_bar.open = True
            page.update()

    def save_profile_action(e):
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM profile")
            cur.execute("""
                INSERT INTO profile (start_date, start_weight, target_weight, height, age, intensity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                state["start_date"].strftime("%Y-%m-%d"),
                float(st_start_weight.value),
                float(st_target_weight.value),
                float(st_height.value),
                float(st_age.value),
                float(st_intensity.value)
            ))
            conn.commit()
            state["profile_loaded"] = True
            page.snack_bar = ft.SnackBar(ft.Text("Profil zapisany!"), bgcolor="blue")
            page.snack_bar.open = True
            refresh_dashboard()
            update_charts_tab()
        except:
            page.snack_bar = ft.SnackBar(ft.Text("Wypełnij wszystkie pola!"), bgcolor="red")
            page.snack_bar.open = True
            page.update()

    # --- 7. UKŁAD STRONY (LAYOUT) ---

    def change_day(delta):
        state["view_date"] += datetime.timedelta(days=delta)
        load_daily_entry()

    standard_dashboard = ft.Container(
        content=ft.Column([
            ft.Text("TWOJE MAKRO NA DZIŚ", size=12, color="grey"),
            txt_dash_kcal,
            txt_dash_mode,
            ft.Divider(color="white10"),
            ft.Row([txt_dash_prog_perc, pb_dash_prog], alignment="spaceBetween"),
            txt_dash_days
        ]),
        padding=20, border_radius=15, bgcolor=ft.colors.WHITE10, # FIX: colors.surface usunięte
        border=ft.border.all(1, ft.colors.WHITE10),
    )

    # ZAKŁADKA 1: PULPIT
    tab_dashboard = ft.Container(
        content=ft.Column([
            goal_panel,          # Panel Zwycięstwa
            standard_dashboard,  # Panel Normalny
            
            ft.Divider(height=20, color="transparent"),
            
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.IconButton(ft.icons.CHEVRON_LEFT, on_click=lambda _: change_day(-1)),
                        ft.Column([
                             ft.Text("Raport z dnia", size=10, color="grey", text_align="center"),
                             date_btn_display
                        ], spacing=0, horizontal_alignment="center"),
                        ft.IconButton(ft.icons.CHEVRON_RIGHT, on_click=lambda _: change_day(1)),
                        ft.IconButton(ft.icons.CALENDAR_MONTH, on_click=lambda _: date_picker_main.pick_date()),
                    ], alignment="spaceBetween"),
                    
                    ft.Divider(),
                    ft.Row([input_weight, input_waist], alignment="center"),
                    input_notes,
                    ft.Row([
                        ft.TextButton("Dodaj zdjęcie", icon=ft.icons.PHOTO_CAMERA, on_click=lambda _: file_picker.pick_files()),
                        img_day_preview
                    ]),
                    ft.ElevatedButton("ZAPISZ WPIS", on_click=save_day_action, bgcolor="green", color="white", width=1000, height=45)
                ]),
                padding=20, border_radius=15, bgcolor=ft.colors.WHITE10,
                border=ft.border.all(1, ft.colors.WHITE10)
            )
        ], scroll="auto"),
        padding=10
    )

    # ZAKŁADKA 2: STATYSTYKI
    tab_stats = ft.Container(
        content=ft.Column([
            ft.Text("HISTORIA WAGI", size=16, weight="bold"),
            ft.Container(
                content=chart_plot,
                height=300,
                padding=10, bgcolor=ft.colors.WHITE10, border_radius=10
            ),
            ft.Divider(),
            ft.Text("DZIENNIK SZCZEGÓŁOWY", size=16, weight="bold"),
            ft.Container(
                content=history_table,
                bgcolor=ft.colors.WHITE10, border_radius=10, padding=10
            )
        ], scroll="auto"),
        padding=10
    )

    # ZAKŁADKA 3: USTAWIENIA
    tab_settings = ft.Container(
        content=ft.Column([
            ft.Text("KONFIGURACJA PROFILU", size=18, weight="bold"),
            ft.Divider(),
            ft.Row([st_start_weight, st_target_weight]),
            ft.Row([st_height, st_age]),
            st_intensity,
            ft.Row([
                ft.Text("Data Startu:", size=16),
                ft.IconButton(ft.icons.CALENDAR_MONTH, on_click=lambda _: date_picker_start.pick_date())
            ]),
            ft.Divider(),
            ft.ElevatedButton("ZAPISZ PROFIL", on_click=save_profile_action, width=1000, height=50)
        ], scroll="auto"),
        padding=20
    )

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(text="Pulpit", icon=ft.icons.DASHBOARD, content=tab_dashboard),
            ft.Tab(text="Statystyki", icon=ft.icons.INSERT_CHART, content=tab_stats),
            ft.Tab(text="Ustawienia", icon=ft.icons.SETTINGS, content=tab_settings),
        ],
        expand=True
    )
    page.add(tabs)

    # --- 8. START ---
    def load_initial_data():
        cur = conn.cursor()
        cur.execute("SELECT * FROM profile ORDER BY id DESC LIMIT 1")
        p = cur.fetchone()
        if p:
            state["profile_loaded"] = True
            state["start_date"] = datetime.datetime.strptime(p[1], "%Y-%m-%d").date()
            st_start_weight.value = str(p[2])
            st_target_weight.value = str(p[3])
            st_height.value = str(p[4])
            st_age.value = str(p[5])
            st_intensity.value = str(p[6])
            
            refresh_dashboard()
            update_charts_tab()
        
        load_daily_entry()

    load_initial_data()

ft.app(target=main)