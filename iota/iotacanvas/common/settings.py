# Copyright (C) 2019  Jeremy Webb

# This file is part of IOTA Canvas.

# IOTA Canvas is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# IOTA Canvas is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with IOTA Canvas.  If not, see <http://www.gnu.org/licenses/>.


"""
Manages the settings for iotacanvas.
"""

import json
from pathlib import Path
import threading

ROOT_DIR = Path(__file__).absolute().parent.parent
RESOURCES_DIR = "resources"
DATETIME_FORMAT = "%d-%m-%Y %H:%M:%S:%f"
TIME_FORMAT = "%H:%M"


class Settings:
    """Handles settings for IOTA Canvas."""
    CONFIG_PATH = ROOT_DIR
    DEFAULT_FILENAME = "settings.conf"
    # values ending with these strings are paths
    PATH_EXT = ['dir', 'image']
    # paths in this struct are relative to ROOT_DIR
    # unless they are absolute paths
    DEFAULT_SETTINGS = {
        "user": {
            # how often to change to a new artwork in hours
            "art_refresh_rate": 240,
            "art_refresh_enabled": True,
            "ai_marketplace_url": "http://127.0.0.1:5000",
            "timezone": "",
            "display_off_enabled": False,
            "display_off_time": "22:30",
            "display_on_time": "08:00",
            "gpio_skip": 16,
            "gpio_like": 20,
            "gpio_setup": 21
        },
        "art": {
            "preferred_genres": [],
            "last_refresh_time": None,
            "artwork_dir": "artwork",
            "current_artwork": None,  # name of current artwork (not path)
        },
        "display": {
            "default_background_image": RESOURCES_DIR + "/default_background.jpg",
            "default_image": RESOURCES_DIR + "/default_image.png",
        },
        "server": {
            "port": 8080,
        },
        "iota": {
            "node": "https://nodes.devnet.iota.org:443",
            "addr_index": 0,
            "receive_address": None,
            "seed": None,
        }
    }

    def __init__(self, config_path=CONFIG_PATH, config_filename=DEFAULT_FILENAME):
        # start with default settings
        self._settings = Settings.DEFAULT_SETTINGS
        self.config_path = config_path / config_filename
        self._thread_lock = threading.Lock()
        # initialize save_timer so it can be cancelled without issues later
        self._save_timer = threading.Timer(0, lambda: None)
        # turn paths into Path objects
        self._expand_paths(self._settings)

    def load(self):
        """Loads the settings from the config_path stored in the settings.\n
           Turns paths into absolute paths."""
        with self._thread_lock:
            with open(self.config_path) as json_data_file:
                updated_config = json.load(json_data_file)
                self._merge_recursive(self._settings, updated_config)
                self._expand_paths(self._settings)

    def save(self):
        """Saves the settings to a file at the config_path stored
            in the settings."""
        with self._thread_lock:
            # turn paths back into strings
            self._collapse_paths(self._settings)
            with open(self.config_path, 'w') as outfile:
                json.dump(self._settings, outfile)
            # turn paths into Paths objects
            self._expand_paths(self._settings)

    def get(self, keys):
        """Takes a list of keys (in case the desired setting is in a nested dict)
           and returns the desired value."""
        with self._thread_lock:
            settings_dict = self._settings
            for key in keys:
                value = settings_dict.get(key)
                settings_dict = value  # assign in case value is another dictionary
        return value

    def setval(self, settings_update):
        """Takes in a dict and adds the keyword, value pairs to the settings"""
        with self._thread_lock:
            self._merge_recursive(self._settings, settings_update)

    def setval_and_save(self, settings_update, save_delay=1.5):
        """Updates the settings and saves them.\n
           Saving is delayed by save_delay seconds
           in case this is called frequently."""
        self.setval(settings_update)
        self._save_timer.cancel()
        self._save_timer = threading.Timer(save_delay, self.save)
        self._save_timer.start()

    def _merge_recursive(self, destination, source):
        for key, val in source.items():
            if isinstance(val, dict):
                if key in destination:
                    self._merge_recursive(destination[key], val)
                else:
                    destination[key] = val
            else:
                destination[key] = val

    @staticmethod
    def _expand_paths(settings_dict):
        for key, val in settings_dict.items():
            if isinstance(val, dict):
                # if the value is a dictionary, recursively process it
                Settings._expand_paths(val)
            else:
                for ext in Settings.PATH_EXT:
                    if key.endswith(ext):
                        # this entry needs it's path expanded
                        if Path(settings_dict[key]).is_absolute():
                            settings_dict[key] = Path(settings_dict[key])
                        else:
                            settings_dict[key] = ROOT_DIR / settings_dict[key]
                        break

    @staticmethod
    def _collapse_paths(settings_dict):
        for key, val in settings_dict.items():
            if isinstance(val, dict):
                # if the value is a dictionary, recursively process it
                Settings._collapse_paths(val)
            elif isinstance(val, Path):
                # this entry needs it's path collapsed
                try:
                    settings_dict[key] = \
                        settings_dict[key].relative_to(ROOT_DIR)
                    settings_dict[key] = str(settings_dict[key])
                except ValueError:
                    # couldn't format as relative path, keep absolute path
                    settings_dict[key] = str(settings_dict[key])
