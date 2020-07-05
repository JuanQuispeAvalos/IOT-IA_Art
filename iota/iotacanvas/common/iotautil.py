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
This is a collection of convenience functions to access the IOTA Tangle.
"""

import secrets
import string
import threading

import iota

from common import display
import webapp

# Minimum weight magnitude (MWM)
# if too small, the transaction will never be confirmed,
# but the smaller the number, the less proof-of-work needed
# Devnet requires MWM >=9, Mainnet requires MWM >= 14
# see https://docs.iota.org/docs/getting-started/0.1/tutorials/send-iota-tokens
MWM = 9

# size of address qr code
QR_CODE_SIZE = 256  # size in pixels (square)


def generate_seed():
    """Generate a random 81 character Iota seed"""
    valid_chars = string.ascii_uppercase + "9"
    seed = ''.join([secrets.choice(valid_chars) for i in range(81)])
    return seed


class IotaUtil:
    """Provides a wrapper around pyota to automatically manage addresses
       and sending tokens"""

    def __init__(self, user_settings):
        self.user_settings = user_settings
        self._thread_lock = threading.Lock()
        node_addr = user_settings.get(['iota', 'node'])
        seed = user_settings.get(['iota', 'seed'])
        if seed is None:
            # somehow got a default settings object
            # raise an error
            raise ValueError("Iota seed must be initialized")
        # initialize with the IOTA node address and seed
        self.iotaapi = iota.Iota(node_addr, seed=seed)

    def generate_address(self, num_addrs=1):
        """Generates a new address and increments the address index"""
        with self._thread_lock:
            index = self.user_settings.get(['iota', 'addr_index'])
            addresses = self.iotaapi.get_new_addresses(
                index=index, count=num_addrs)
            address = str(addresses['addresses'][0])
            # update the index in the settings
            settings_update = {
                'iota': {
                    'addr_index': index + num_addrs,
                }
            }
            self.user_settings.setval_and_save(settings_update)
            return address

    def get_balance(self):
        """Returns the iota balance associated with the settings seed"""
        # the thread lock is not needed here since we are not changing anything
        #
        # the stop_index is provided to force the get_account_data method to
        # search all addresses up to this index.
        # if this was not provided, the method would stop searching once it
        # reaches an address with no transactions referencing it. this could
        # occur if there are indices that were skipped when generating
        # addresses.
        # if there are funds after the skipped addresses, the get_account_data
        # method would not add them to the total balance if stop_index was not
        # provided.
        stop_index = self.user_settings.get(['iota', 'addr_index'])
        return self.iotaapi.get_account_data(stop=stop_index)['balance']

    def send_iota(self, amount, destination_address, message=None):
        """Sends the specified amount of IOTA to the specified address
            with an optional message"""
        tx = iota.ProposedTransaction(
            address=iota.Address(destination_address),
            message=self.iotaapi.messageTryteString.from_unicode(
                message) if message else None,
            tag=iota.Tag('VALUETX'),
            value=amount
        )
        # change address is used to send the extra IOTA attached to the seed to
        # since any address that has been spent from is compromised due to the
        # encryption scheme IOTA uses, funds must be moved to new addresses
        # that have not been spent from
        change_address = self.generate_address()
        # although it is not necessary to provide the stop_index
        # it assists in the process of searching for unspent
        # inputs because it ensures that all addresses up to stop_index
        # are searched and not any extra
        # in other words, it guards against the case where an index for an
        # address is skipped and has no transactions referencing it (in this
        # case, pyota would stop searching at the skipped address)
        # since we know that only addresses up to stop_index have been
        # generated, this is safe to provide
        stop_index = self.user_settings.get(['iota', 'addr_index'])
        try:
            inputs = self.iotaapi.get_inputs(stop=stop_index)
            with self._thread_lock:
                tx = self.iotaapi.prepare_transfer(
                    transfers=[tx],
                    inputs=inputs['inputs'],
                    change_address=change_address
                )
                # send the transfer and do the PoW
                self.iotaapi.send_trytes(
                    tx['trytes'], depth=3, min_weight_magnitude=MWM
                )
                self.user_settings.setval_and_save(
                    {'iota': {'receive_address': change_address}})
        except Exception:
            # if anything goes wrong,
            # rollback the address index that was used to generate
            # the change address (so it can be reused)
            settings_update = {
                'iota': {
                    'addr_index': stop_index - 1,
                }
            }
            self.user_settings.setval_and_save(settings_update)
            raise

    def save_address_qr(self):
        """Generates and saves a qr code for the iota receive address.\n
           Save location is the webapp images directory"""
        with self._thread_lock:
            qr = display.make_qrcode(
                self.user_settings.get(['iota', 'receive_address']),
                QR_CODE_SIZE
            )
            qr.save(
                webapp.IMAGES_DIR / 'receive_address_qr.jpg',
                'JPEG'
            )


if __name__ == "__main__":
    # short test of IOTA functionality
    from common import settings
    app_settings = settings.Settings()
    temp_seed = generate_seed()
    app_settings.setval({'iota': {'seed': temp_seed}})
    iota_utils = IotaUtil(app_settings)
    print(iota_utils.iotaapi.get_node_info())
