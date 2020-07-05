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
Runs main functions of IOTA Canvas
"""

import datetime
import imghdr  # for determining image type
from pathlib import Path
import queue
import random
import threading
import uuid  # for creating unique ids

import gpiozero  # for managing buttons
import requests  # for communicating with AI Marketplace

from common import iotautil, settings, display, synchro

ROOT_DIR = Path(__file__).absolute().parent
# how often to run the main loop
CHECK_INTERVAL = datetime.timedelta(minutes=5)
MINUTES_IN_DAY = 24 * 60
# how often to check if a requested art piece is ready
ART_CHECK_INTERVAL = 30
# max time to check if the artwork is ready
MAX_CHECK_TIME = datetime.timedelta(minutes=15)
# time to wait before trying to refresh again
REFRESH_COOLDOWN = datetime.timedelta(minutes=4)
# valid extensions for new artwork
ARTWORK_EXTENSIONS = ('png', 'jpg', 'jpeg', 'bmp')
# amount of IOTA that is considered a low balance
LOW_BALANCE_AMOUNT = 100


def initialize_app(app_settings):
    """Load settings if config file exists,
    otherwise, create seed and receive address. \n
    Return iota_interface"""
    if not app_settings.config_path.exists():
        # need to initialize app
        # generate seed
        iota_seed = iotautil.generate_seed()
        # save seed
        app_settings.setval({'iota': {'seed': iota_seed}})
        # generate receiving address and save it
        iota_interface = iotautil.IotaUtil(app_settings)
        recv_addr = iota_interface.generate_address()
        app_settings.setval_and_save({'iota': {'receive_address': recv_addr}})
    else:
        # load settings
        app_settings.load()
        iota_interface = iotautil.IotaUtil(app_settings)
    artwork_dir = app_settings.get(['art', 'artwork_dir'])
    # make the artwork_dir if it doesn't already exist
    artwork_dir.mkdir(parents=True, exist_ok=True)
    return iota_interface


class IotaCanvas:
    """Main class for running IOTA Canvas"""

    def __init__(self, app_settings, app_display, iota_interface, event_q, stop_flag):
        self.app_settings = app_settings
        self.app_display = app_display
        self.iota_interface = iota_interface
        self._event_q = event_q
        self.stop_flag = stop_flag
        # monitor starts on
        self._monitor_state = True
        # flag for if the art is currently being refreshed
        # to ensure that multiple refreshes don't take place simultaneously
        self._is_refreshing = False
        self._last_refresh_attempt = None
        self._setup_button = None
        self._skip_button = None
        self._like_button = None

    def get_num_artworks(self):
        """Returns the number of artworks saved in the artwork_dir"""
        artwork_dir = self.app_settings.get(['art', 'artwork_dir'])
        total_sum = 0
        for ext in ARTWORK_EXTENSIONS:
            artworks = artwork_dir.glob('*.' + ext)
            total_sum += sum(1 for _ in artworks)
        return total_sum

    def get_random_artwork(self):
        """Returns filename of a random artwork in the artwork_dir"""
        artwork_dir = self.app_settings.get(['art', 'artwork_dir'])
        artworks = []
        for ext in ARTWORK_EXTENSIONS:
            art = artwork_dir.glob('*.' + ext)
            artworks.extend(art)
        rand_index = random.randrange(0, len(artworks))
        return artworks[rand_index].name

    def is_refresh_time(self):
        """Returns True if it's time to refresh the artwork.

        If there are no images in the artwork folder,
        the last refresh time is None,
        or if the current time is past the refresh interval."""
        if not self.app_settings.get(['user', 'art_refresh_enabled']):
            return False
        if self._last_refresh_attempt is not None \
            and self._last_refresh_attempt + REFRESH_COOLDOWN \
                > datetime.datetime.now():
            # still in cooldown period
            return False
        last_refresh = self.app_settings.get(['art', 'last_refresh_time'])
        if last_refresh is None:
            return True
        # parse the last refresh time from the string stored in the settings
        last_refresh = datetime.datetime.strptime(
            last_refresh, settings.DATETIME_FORMAT
        )
        # parse the refresh interval from the string stored in the settings
        refresh_interval = self.app_settings.get(['user', 'art_refresh_rate'])
        refresh_interval = datetime.timedelta(hours=refresh_interval)
        # if the current time is past the refresh time set to True
        refresh_time = \
            (last_refresh + refresh_interval) <= datetime.datetime.now()
        num_artworks = self.get_num_artworks()
        # if there are no saved artworks, or it's past refresh time return True
        return num_artworks == 0 or refresh_time

    def manage_monitor(self):
        """Turns the monitor on or off if needed based on settings."""
        def convert_time_minutes(time_string):
            # convert the time into the number of minutes since midnight
            new_time = datetime.datetime.strptime(
                time_string, settings.TIME_FORMAT
            ).timetz()
            new_time = new_time.hour * 60 + new_time.minute
            return new_time

        if self.app_settings.get(['user', 'display_off_enabled']):
            # check if monitor state needs changing
            off_time = self.app_settings.get(['user', 'display_off_time'])
            off_time = convert_time_minutes(off_time)
            on_time = self.app_settings.get(['user', 'display_on_time'])
            on_time = convert_time_minutes(on_time)
            now = datetime.datetime.now().timetz()
            now = now.hour * 60 + now.minute
            # on_time, off_time, and now are all integers representing
            # the number of minutes from midnight
            # take advantage of the modulo operator (%) to wrap correctly
            # past midnight when calculating if the current time is between
            # on_time and off_time
            monitor_should_be_on = \
                (now - on_time) % MINUTES_IN_DAY \
                < (off_time - on_time) % MINUTES_IN_DAY
            if monitor_should_be_on and not self._monitor_state:
                # turn screen on
                success = display.turn_on()
                if success:
                    self._monitor_state = True
            elif self._monitor_state and not monitor_should_be_on:
                # turn screen off
                success = display.turn_off()
                if success:
                    self._monitor_state = False

    def choose_artist(self, artist_list):
        """Chooses which artist to request art from.

        Currently selects cheapest artist."""
        if artist_list is None or not artist_list:
            raise ValueError()
        best_choice = artist_list[0]
        for artist in artist_list:
            if best_choice['cost'] > artist['cost']:
                best_choice = artist
        return best_choice

    def run(self):
        """Runs the main IOTA Canvas event loop which handles
        refreshing the artwork, communication with the marketplace,
        etc."""
        try:
            event = synchro.IotaCanvasEvent("NONE")
            # setup buttons
            self._reset_buttons()
            # if there is art in the artworks folder, show one initially
            self._initialize_artwork()
            # main event loop which runs until the program stops
            while not self.stop_flag.is_set():
                if self.is_refresh_time() or event.name == "REFRESH_ARTWORK":
                    # only try to refresh if we aren't already trying
                    if not self._is_refreshing:
                        # this is a long-running process, so start a new thread
                        threading.Thread(
                            target=self._refresh_artwork_caller
                        ).start()
                if event.name == "ARTWORK_UPDATED":
                    # show the new artwork
                    artwork_dir = self.app_settings.get(
                        ['art', 'artwork_dir'])
                    current_artwork = self.app_settings.get(
                        ['art', 'current_artwork'])
                    self.app_display.action(
                        "<<ShowImage>>", artwork_dir / current_artwork
                    )
                if event.name == "LOW_BALANCE":
                    # show the settings page
                    self.app_display.action("<<ShowServerAddress>>")
                self.manage_monitor()  # turn display on or off if needed

                try:
                    # wait until an event is received, or the stop_flag is set
                    # or until the timeout occurs
                    # this loop needs to run occasionally regardless of if an
                    # event is received in order to calculate if it is time to
                    # refresh the artwork or turn the monitor off/on
                    event = self._event_q.get_and_wait_on_event(
                        self.stop_flag,
                        timeout=CHECK_INTERVAL.total_seconds()
                    )
                except queue.Empty:
                    # raised if the get on the queue times out
                    pass
        finally:
            # set the stop flag in case the main loop has an exception
            self.stop_flag.set()

    def _refresh_artwork_caller(self):
        try:
            # set the _is_refreshing flag to true so only one refresh is performed
            # at a time
            self._is_refreshing = True
            self._refresh_artwork()
        finally:
            # reset _is_refreshing flag
            self._is_refreshing = False

    def _refresh_artwork(self):
        """Refreshes the artwork if possible.

        This follows the following process:
        1. request artist list from AI Marketplace
        2. choose an artist from the list
        3. request art from the artist via AI Marketplace
        4. send IOTA to the AI Marketplace to pay the artist
        5. repeatedly check if the artwork is ready yet
        6. download the artwork and send an event that there is new art
        """
        self._last_refresh_attempt = datetime.datetime.now()
        # 0. check the current balance is not too low
        if self.iota_interface.get_balance() < LOW_BALANCE_AMOUNT:
            self._event_q.put("LOW_BALANCE")
            return
        # 1. get the artist list
        marketplace = self.app_settings.get(['user', 'ai_marketplace_url'])
        try:
            artist_list = requests.get(marketplace + '/artist-list').json()
            # 2. choose an artist
            artist = self.choose_artist(artist_list)
            # 3. request art from the selected artist
            art_request = requests.get(
                marketplace + '/' + str(artist['id']) + '/request-art'
            ).json()
        except requests.exceptions.ConnectionError:
            self._event_q.put("ERROR", "Could not contact AI Marketplace.")
            return
        try:
            # 4. send iota to AI Marketplace
            self.iota_interface.send_iota(
                artist['cost'],
                art_request['iota_addr']
            )
        except ValueError:
            # balance too low - send event to show settings page
            self._event_q.put("LOW_BALANCE")
            return
        status = 'unknown'
        # 5. check if the artwork is ready yet
        #    this will check for up to MAX_CHECK_TIME, after which it will
        #    give up
        start_check = datetime.datetime.now()
        while status != 'completed' \
                and start_check + MAX_CHECK_TIME > datetime.datetime.now() \
                and not self.stop_flag.is_set():
            self.stop_flag.wait(ART_CHECK_INTERVAL)
            # get the status of the commissioned artwork
            try:
                status = requests.post(
                    marketplace + art_request['status_addr'],
                    json={
                        'key': art_request['key']
                    }
                ).json()['status']
            except requests.exceptions.ConnectionError:
                self._event_q.put("ERROR", "Could not contact AI Marketplace.")
                return
        if status != 'completed':
            # request timed out
            return
        # 6. get artwork
        try:
            artwork = requests.post(
                marketplace + art_request['retrieve_addr'],
                json={
                    'key': art_request['key']
                }
            ).content
        except requests.exceptions.ConnectionError:
            self._event_q.put("ERROR", "Could not contact AI Marketplace.")
            return
        # check what type of file the artwork is
        ext = imghdr.what(None, h=artwork)
        artwork_dir = self.app_settings.get(['art', 'artwork_dir'])
        # create a unique name for the artwork
        filename = uuid.uuid4().hex[:8] + '.' + ext
        # save the artwork
        with open(artwork_dir / filename, 'wb') as f:
            f.write(artwork)
        # update last_refresh_time
        refresh_time = \
            datetime.datetime.now().strftime(
                settings.DATETIME_FORMAT
            )
        self.app_settings.setval_and_save({
            'art': {
                'last_refresh_time': refresh_time,
                'current_artwork': filename
            }
        })
        # send event to main loop to display new artwork
        self._event_q.put("ARTWORK_UPDATED")

    def _reset_buttons(self):
        """Setup three buttons: setup, skip, and like buttons."""
        setup_pin = self.app_settings.get(['user', 'gpio_setup'])
        skip_pin = self.app_settings.get(['user', 'gpio_skip'])
        like_pin = self.app_settings.get(['user', 'gpio_like'])
        self._setup_button = gpiozero.Button(pin=setup_pin)
        self._skip_button = gpiozero.Button(pin=skip_pin)
        self._like_button = gpiozero.Button(pin=like_pin)
        self._setup_button.when_pressed = \
            lambda: self.app_display.action("<<ShowServerAddress>>")
        self._skip_button.when_pressed = \
            lambda: self._event_q.put("REFRESH_ARTWORK")

    def _initialize_artwork(self):
        """Shows the current artwork if one is set.

        If there is none set, chooses a random artwork as the current artwork.
        If there are no files in the artwork_dir, this method does nothing."""
        if self.get_num_artworks() != 0:
            artwork_dir = self.app_settings.get(['art', 'artwork_dir'])
            current_artwork = self.app_settings.get(
                ['art', 'current_artwork'])
            if current_artwork is None \
                    or not (artwork_dir / current_artwork).is_file():
                # set a random available artwork to be current artwork
                current_artwork = self.get_random_artwork()
                self.app_settings.setval_and_save({
                    'art': {
                        'current_artwork': current_artwork
                    }
                })
            self.app_display.action(
                "<<ShowImage>>", artwork_dir / current_artwork
            )
