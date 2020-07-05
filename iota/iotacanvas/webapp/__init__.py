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
Defines server functions for the webapp for IOTA Canvas
"""

from pathlib import Path
import socket

import cherrypy

WEB_DIR = Path(__file__).absolute().parent
PAGES_DIR = 'pages'
PAGES_PATH = WEB_DIR / PAGES_DIR
IMAGES_DIR = WEB_DIR / 'static' / 'images'


def get_IP():
    """Returns the external IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except OSError:
        # all socket exceptions inherit from OSError
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def start_webapp(app_settings, iota_api, stop_flag):
    """Initializes and starts the Cherrypy webserver."""
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': WEB_DIR,
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': 'static'
        },
        '/favicon.ico':
        {
            'tools.staticfile.on': True,
            'tools.staticfile.filename': str(IMAGES_DIR / 'iotacanvas.ico'),
        }
    }
    # make webapp available to external clients
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': app_settings.get(['server', 'port']),
        'global': {
            'environment': 'production',
            'engine.autoreload.on': False
        }
    })
    # set the stop_flag when the cherrypy engine stops
    cherrypy.engine.subscribe('stop', stop_flag.set)
    # initialize the web app
    cherrypy.tree.mount(WebApp(app_settings, iota_api), '/', conf)
    cherrypy.engine.signals.subscribe()
    cherrypy.engine.start()


class WebApp:
    """Defines handler functions for all web requests"""

    def __init__(self, app_settings, iota_api):
        self.app_settings = app_settings
        self.iota_api = iota_api

    @cherrypy.expose
    def index(self):
        """Handles /"""
        return open(PAGES_PATH / 'index.html')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def user_settings(self):
        """Responds to /user_settings with json of the user settings."""
        return self.app_settings.get(['user'])

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def iota_settings(self):
        """Responds to /iota_settings with json of the iota settings."""
        iota_config = dict(self.app_settings.get(['iota']))
        # don't send seed
        del iota_config['seed']
        # generate qr code for receiving address
        self.iota_api.save_address_qr()
        return iota_config

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def iota_balance(self):
        """Responds to /iota_balance with the IOTA balance.

        This is a separate handler from /iota_settings because it can
        take significantly longer, and shouldn't delay /iota_settings."""
        iota_config = {}
        # add current balance
        current_bal = self.iota_api.get_balance()
        iota_config['current_balance'] = current_bal
        return iota_config

    @cherrypy.expose
    @cherrypy.tools.json_in()
    def update_settings(self):
        """Takes in a request with JSON and updates the requested settings."""
        data = cherrypy.request.json
        data_wrapper = {'user': data}
        self.app_settings.setval_and_save(
            data_wrapper,
            save_delay=15  # delay for 15 seconds in case more changed are made
        )
