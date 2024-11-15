import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib, Pango, Adw, Gio
from datetime import datetime, timedelta
import os
import configparser
from dotenv import load_dotenv, set_key
import logging
import requests

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('openshockclock.log')
    ]
)
logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'alarms.txt')
ENV_FILE = os.path.join(os.path.dirname(__file__), '.env')

base_dir = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(base_dir, "icons", "waves.svg")

def load_env():
    logger.debug("Loading environment variables")
    load_dotenv(ENV_FILE)
    api_key = os.getenv('SHOCK_API_KEY')
    shock_id = os.getenv('SHOCK_ID')
    logger.debug(f"Loaded API key: {'*' * len(api_key) if api_key else 'None'}")
    logger.debug(f"Loaded Shock ID: {shock_id if shock_id else 'None'}")
    return api_key, shock_id

def save_env(api_key, shock_id): # note to self, add checking for if the api key and shocker id are actually valid by sending a request
    logger.debug("Saving environment variables")
    set_key(ENV_FILE, 'SHOCK_API_KEY', api_key)
    set_key(ENV_FILE, 'SHOCK_ID', shock_id)

def load_alarms_from_file():
    logger.debug("Loading alarms from file")
    alarms = {}

    try:
        if os.path.exists(CONFIG_FILE):
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)

            for section in config.sections():
                try:
                    alarm_time = datetime.strptime(config[section]['time'], '%Y-%m-%d %H:%M:%S')
                    intensity = int(config[section]['intensity'])
                    duration = int(config[section]['duration'])
                    vibrate_before = config[section].getboolean('vibrate_before')

                    while alarm_time < datetime.now():
                        alarm_time += timedelta(days=1)

                    alarms[section] = (alarm_time, intensity, duration, vibrate_before)
                    logger.debug(f"Loaded alarm: {section} at {alarm_time}")
                except (ValueError, KeyError) as e:
                    logger.error(f"Error loading alarm {section}: {str(e)}")
                    continue
    except Exception as e:
        logger.error(f"Error reading config file: {str(e)}")

    return alarms

def save_alarm_to_file(name, alarm_time, intensity, duration, vibrate_before):
    logger.debug(f"Saving alarm {name} to file")
    try:
        config = configparser.ConfigParser()

        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)

        config[name] = {
            'time': alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
            'intensity': str(intensity),
            'duration': str(duration),
            'vibrate_before': str(vibrate_before)
        }

        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

        logger.debug(f"Successfully saved alarm {name}")
    except Exception as e:
        logger.error(f"Error saving alarm to file: {str(e)}")

def trigger_shock(api_key, shock_id, intensity, duration, vibrate=False):
    logger.debug(f"Triggering shock - Intensity: {intensity}, Duration: {duration}, Vibrate: {vibrate}")
    url = "https://api.shocklink.net/2/shockers/control"
    headers = {
        "accept": "application/json",
        "OpenShockToken": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "shocks": [{
            "id": shock_id,
            "type": "Vibrate" if vibrate else "Shock",
            "intensity": intensity,
            "duration": duration,
            "exclusive": True
        }],
        "customName": "OpenShockClock"
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        logger.debug(f"Shock API response: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to trigger shock: {str(e)}")
        return False

class OpenShockClock(Adw.Application):
    def __init__(self):
        super().__init__(application_id='openshock.alarm')
        self.api_key, self.shock_id = load_env()
        self.alarms = load_alarms_from_file()
        logger.debug("OpenShockClock started")

    def check_alarms(self):
        current_time = datetime.now()
        for name, (alarm_time, intensity, duration, vibrate_before) in self.alarms.items():
            time_until = (alarm_time - current_time).total_seconds()

            if vibrate_before and 30 > time_until > 29:
                logger.debug(f"Triggering vibration warning for alarm {name} at intensity 100 for 10 seconds")
                vibration_data = {
                    "shocks": [{
                        "id": self.shock_id,
                        "type": "Vibrate",
                        "intensity": 100,
                        "duration": 10000,
                        "exclusive": True
                    }],
                    "customName": "OpenShockClock - Vibration Warning"
                }

                try:
                    response = requests.post(
                        "https://api.shocklink.net/2/shockers/control",
                        headers={
                            "accept": "application/json",
                            "OpenShockToken": self.api_key,
                            "Content-Type": "application/json"
                        },
                        json=vibration_data
                    )
                    response.raise_for_status()
                    logger.debug(f"Vibration warning API response: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    logger.error(f"Failed to trigger vibration warning: {str(e)}")

            if 1 > time_until > 0:
                logger.debug(f"Triggering alarm {name}")
                trigger_shock(self.api_key, self.shock_id, intensity, duration)

                new_alarm_time = alarm_time + timedelta(days=1)
                self.alarms[name] = (new_alarm_time, intensity, duration, vibrate_before)
                save_alarm_to_file(name, new_alarm_time, intensity, duration, vibrate_before)
                logger.debug(f"Reset alarm {name} for next day: {new_alarm_time}")

        return True

    def update_timers(self):
        current_time = datetime.now()

        child = self.list_box.get_first_child()
        while child is not None:
            row = child
            name = row.get_title()

            if name in self.alarms:
                alarm_time, intensity, duration, vibrate_before = self.alarms[name]

                time_until = alarm_time - current_time
                if time_until.total_seconds() < 0:
                    alarm_time = alarm_time + timedelta(days=1)
                    time_until = alarm_time - current_time
                    self.alarms[name] = (alarm_time, intensity, duration, vibrate_before)

                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                seconds = int(time_until.total_seconds() % 60)
                timer_text = f"Time until: {hours:02}:{minutes:02}:{seconds:02}"

                row.set_subtitle(timer_text)

            child = child.get_next_sibling()

        return True

    def open_settings(self, action, param):
        settings_window = SettingsWindow(self)
        settings_window.present()

    def add_new_alarm(self, button):
        window = NewAlarmWindow(self)
        window.present()

    def do_activate(self):
        self.window = Adw.ApplicationWindow(application=self)
        self.window.set_default_size(800, 600)
        self.window.set_title("OpenShockClock")

        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        menu_button = Gtk.MenuButton()
        menu = Gtk.PopoverMenu.new_from_model(self.create_menu())
        menu_button.set_popover(menu)
        menu_button.set_icon_name("open-menu-symbolic")
        header.pack_end(menu_button)

        new_alarm_button = Gtk.Button()
        new_alarm_button.set_icon_name("list-add-symbolic")
        new_alarm_button.connect("clicked", self.add_new_alarm)
        header.pack_start(new_alarm_button)

        toolbar_view.add_top_bar(header)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.status_page = Adw.StatusPage()
        self.status_page.set_title("OpenShockClock")
        if self.api_key and self.shock_id:
            self.status_page.set_description("Connected")
            self.status_page.set_icon_name("network-wireless-signal-excellent-symbolic")
        else:
            self.status_page.set_description("Not Connected")
            self.status_page.set_icon_name("network-wireless-offline-symbolic")
        main_box.append(self.status_page)

        alarms_group = Adw.PreferencesGroup()
        alarms_group.set_title("Your Alarms")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list_box.add_css_class("boxed-list")
        scrolled.set_child(self.list_box)

        alarms_group.add(scrolled)
        main_box.append(alarms_group)

        toolbar_view.set_content(main_box)
        self.window.set_content(toolbar_view)

        self.populate_alarms()

        GLib.timeout_add_seconds(1, self.update_timers)
        GLib.timeout_add_seconds(1, self.check_alarms)

        self.window.present()

    def create_menu(self):
        menu = Gio.Menu()

        menu.append("Settings", "app.settings")

        menu.append("About", "app.about")

        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self.open_settings)
        self.add_action(settings_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.show_about)
        self.add_action(about_action)

        return menu

    def show_about(self, action, param):
        about = Adw.AboutWindow(
            transient_for=self.window,
            application_name="OpenShockClock",
            application_icon="alarm-symbolic",
            developer_name="Arxari",
            version="1.0",
            copyright="© 2024",
            license_type=Gtk.License.GPL_3_0,
            website="https://openshock.org"
        )
        about.present()

    def populate_alarms(self):
        child = self.list_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.list_box.remove(child)
            child = next_child

        current_time = datetime.now()
        for name, (alarm_time, intensity, duration, vibrate_before) in self.alarms.items():
            row = Adw.ActionRow()
            row.set_title(name)

            time_until = alarm_time - current_time
            if time_until.total_seconds() < 0:
                alarm_time = alarm_time + timedelta(days=1)
                time_until = alarm_time - current_time
                self.alarms[name] = (alarm_time, intensity, duration, vibrate_before)

            hours = int(time_until.total_seconds() // 3600)
            minutes = int((time_until.total_seconds() % 3600) // 60)
            seconds = int(time_until.total_seconds() % 60)

            timer_text = f"{hours:02}:{minutes:02}:{seconds:02}"
            row.set_subtitle(f"Time until: {timer_text}")

            intensity_label = Gtk.Label(label=f"{intensity}%")
            intensity_label.add_css_class("dim-label")
            row.add_suffix(intensity_label)

            duration_label = Gtk.Label(label=f"{duration/1000:.1f}s")
            duration_label.add_css_class("dim-label")
            row.add_suffix(duration_label)

            if vibrate_before:
                vibrate_icon = Gtk.Image.new_from_file(icon_path)
                row.add_suffix(vibrate_icon)

            delete_button = Gtk.Button()
            delete_button.set_icon_name("user-trash-symbolic")
            delete_button.connect("clicked", self.delete_alarm, name)
            delete_button.add_css_class("flat")
            row.add_suffix(delete_button)

            self.list_box.append(row)

    def delete_alarm(self, button, alarm_name):
        if alarm_name in self.alarms:
            del self.alarms[alarm_name]
            config = configparser.ConfigParser()
            if os.path.exists(CONFIG_FILE):
                config.read(CONFIG_FILE)
                if alarm_name in config:
                    config.remove_section(alarm_name)
                with open(CONFIG_FILE, 'w') as configfile:
                    config.write(configfile)
            self.populate_alarms()

class SettingsWindow(Gtk.Window):
    def __init__(self, parent):
        super().__init__(title="Settings")
        self.parent = parent
        self.set_default_size(400, -1)
        self.set_modal(True)
        self.set_transient_for(parent.window)

        self.api_key, self.shock_id = load_env()

        page = Adw.PreferencesPage()
        self.set_child(page)

        settings_group = Adw.PreferencesGroup()
        settings_group.set_title("OpenShock Settings")
        page.add(settings_group)

        api_key_row = Adw.EntryRow()
        api_key_row.set_title("API Key")
        api_key_row.set_text(self.api_key or "")
        self.api_key_entry = api_key_row

        api_key_entry = api_key_row.get_child()
        if isinstance(api_key_entry, Gtk.Entry):
            api_key_entry.set_placeholder_text("Enter your API Key")

        settings_group.add(api_key_row)

        shock_id_row = Adw.EntryRow()
        shock_id_row.set_title("Shock ID")
        shock_id_row.set_text(self.shock_id or "")
        self.shock_id_entry = shock_id_row

        shock_id_entry = shock_id_row.get_child()
        if isinstance(shock_id_entry, Gtk.Entry):
            shock_id_entry.set_placeholder_text("Enter your Shocker ID")

        settings_group.add(shock_id_row)

        button_group = Adw.PreferencesGroup()

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(16)

        save_button = Gtk.Button(label="Save")
        save_button.add_css_class("suggested-action")
        save_button.connect("clicked", self.save_settings)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda x: self.close())

        button_box.append(save_button)
        button_box.append(cancel_button)
        button_box.set_spacing(12)

        button_group.add(button_box)
        page.add(button_group)

    def save_settings(self, button):
        api_key = self.api_key_entry.get_text()
        shock_id = self.shock_id_entry.get_text()

        save_env(api_key, shock_id)

        self.parent.api_key = api_key
        self.parent.shock_id = shock_id

        if api_key and shock_id:
            self.parent.status_page.set_description("Connected")
            self.parent.status_page.set_icon_name("network-wireless-signal-excellent-symbolic")
        else:
            self.parent.status_page.set_description("Not Connected")
            self.parent.status_page.set_icon_name("network-wireless-offline-symbolic")

        self.close()


class NewAlarmWindow(Adw.Window):
    def __init__(self, parent):
        super().__init__(title="New Alarm")
        self.parent = parent
        self.set_default_size(400, -1)
        self.set_modal(True)
        self.set_transient_for(parent.window)

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        page.add(group)

        name_row = Adw.EntryRow()
        name_row.set_title("Alarm Name")
        self.name_entry = name_row
        group.add(name_row)

        time_row = Adw.EntryRow()
        time_row.set_title("Time (HH:MM)")
        self.time_entry = time_row
        group.add(time_row)

        intensity_row = Adw.SpinRow()
        intensity_row.set_title("Intensity")
        intensity_adj = Gtk.Adjustment(value=50, lower=0, upper=100, step_increment=10, page_increment=10)
        intensity_row.set_adjustment(intensity_adj)
        self.intensity_entry = intensity_row
        group.add(intensity_row)

        duration_row = Adw.SpinRow()
        duration_row.set_title("Duration (seconds)")
        duration_adj = Gtk.Adjustment(value=1, lower=0, upper=30, step_increment=1, page_increment=5)
        duration_row.set_adjustment(duration_adj)
        self.duration_entry = duration_row
        group.add(duration_row)

        vibrate_row = Adw.SwitchRow()
        vibrate_row.set_title("Vibrate Before")
        self.vibrate_switch = vibrate_row
        group.add(vibrate_row)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(24)
        button_box.set_margin_bottom(24)
        button_box.set_margin_end(24)

        save_button = Gtk.Button(label="Add Alarm")
        save_button.add_css_class("suggested-action")
        save_button.connect("clicked", self.save_alarm)
        button_box.append(save_button)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda x: self.destroy())
        button_box.append(cancel_button)

        button_box.set_spacing(12)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(page)
        main_box.append(button_box)

        self.set_content(main_box)

    def save_alarm(self, widget):
        alarm_name = self.name_entry.get_text().strip()
        if not alarm_name:
            alarm_name = f"Alarm {len(self.parent.alarms) + 1}"

        try:
            time_str = self.time_entry.get_text()
            hours, minutes = map(int, time_str.split(':'))
            now = datetime.now()
            alarm_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

            if alarm_time < now:
                alarm_time += timedelta(days=1)

            intensity = int(self.intensity_entry.get_value())
            duration = int(self.duration_entry.get_value() * 1000)
            vibrate_before = self.vibrate_switch.get_active()

            self.parent.alarms[alarm_name] = (alarm_time, intensity, duration, vibrate_before)
            save_alarm_to_file(alarm_name, alarm_time, intensity, duration, vibrate_before)

            self.parent.populate_alarms()

            self.destroy()

        except (ValueError, IndexError):
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading="Invalid Time Format",
                body="Please enter time in HH:MM format (e.g., 09:30)"
            )
            dialog.add_response("ok", "OK")
            dialog.present()

if __name__ == "__main__":
    app = OpenShockClock()
    app.run()
