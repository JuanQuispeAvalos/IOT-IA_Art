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
Main file for IOTA Canvas
"""

import threading

import cherrypy

import webapp
from common import settings, display, synchro
import iotacanvas


def stop_all(app_display, stop_flag):
    """Waits for the stop flag to be set.
       Then stops the webserver and display."""
    stop_flag.wait()
    cherrypy.engine.exit()
    app_display.action("<<Stop>>")

def main():
    """Main function for IOTA Canvas"""
    stop_flag = threading.Event()
    # create queue for communicating with controller thread
    app_queue = synchro.EventQueue()
    # initialize settings - this must happen before everything else
    app_settings = settings.Settings()
    # initialize IOTA API
    iota_interface = iotacanvas.initialize_app(app_settings)
    # app_settings must be initialized and loaded before passing to display
    app_display = display.Display(app_settings, stop_flag)
    # initialize main application
    app = iotacanvas.IotaCanvas(
        app_settings, app_display, iota_interface, app_queue, stop_flag
    )
    # setup threads
    app_thread = threading.Thread(
        target=app.run,
    )
    # stop_thread simply monitors the stop_flag and
    # shuts everything down if it is set to True
    stop_thread = threading.Thread(
        target=stop_all,
        args=(app_display, stop_flag)
    )
    stop_thread.start()
    # start the webserver
    webapp.start_webapp(app_settings, iota_interface, stop_flag)
    app_thread.start()
    app_display.run()
    # just in case
    stop_flag.set()
    app_thread.join(1)


if __name__ == "__main__":
    main()
