'''
This is a collection of convenience functions to access the IOTA network.
'''

import secrets
import string

from flask import current_app
import iota

from aimarket.db import get_db

# Minimum weight magnitude (MWM)
# if too small, the transaction will never be confirmed,
# but the smaller the number, the less proof-of-work needed
# Devnet requires MWM >=9, Mainnet requires MWM >= 14
# see https://docs.iota.org/docs/getting-started/0.1/tutorials/send-iota-tokens
MWM = 9


def generate_seed():
    """Generate a random 81 character Iota seed"""
    valid_chars = string.ascii_uppercase + "9"
    seed = ''.join([secrets.choice(valid_chars) for i in range(81)])
    return seed


class IotaUtil:
    """Provides a wrapper around pyota to automatically manage addresses
       and checking balances"""

    def __init__(self):
        db = get_db()
        # get the IOTA seed
        data = db.execute(
            'SELECT id, seed'
            ' FROM iota'
        ).fetchone()
        self.id = data['id']
        seed = data['seed']
        # set the IOTA node address
        node_addr = current_app.config['IOTA_NODE_ADDR']
        self.iotaapi = iota.Iota(node_addr, seed=seed)


    def generate_address(self):
        """Generates a new address and increments the address index"""
        db = get_db()
        # update addr_index before fetching it so that sqlite issues a BEGIN
        # (sqlite issues a BEGIN on UPDATE/INSERT/DELETE/REPLACE)
        # this starts a transaction that doesn't end until db.commit()
        # this ensures that other threads accessing the database don't
        # access old information and cause race conditions
        #
        # increment the address index and fetch a copy of it to
        # generate a new address
        db.execute(
            'UPDATE iota SET addr_index = addr_index + 1'
            ' WHERE id = ?',
            (self.id,)
        )
        # fetch the address index and subtract 1 since 1 was added above
        addr_index = db.execute(
            'SELECT addr_index'
            ' FROM iota WHERE id = ?',
            (self.id,)
        ).fetchone()['addr_index'] - 1
        # save the database changes
        db.commit()
        # generate a new IOTA address
        # although providing the address index isn't strictly necessary,
        # it speeds up the generation of the new address considerably
        # because if it is not provided, the method will use guess-and-check.
        # in other words, addresses will be generated and then
        # the Tangle will be scanned to see if the address has been used until
        # an unused address is found.
        addresses = self.iotaapi.get_new_addresses(
            index=addr_index
        )
        address = str(addresses['addresses'][0])
        return (address, addr_index)


    def get_balance(self, index):
        """Returns the iota balance associated with
        the address generated from the given index"""
        stop_index = index + 1
        # providing the start and stop indices ensure that the balance from
        # a single address is returned.
        # if these are not given, the method will add up the balance from all
        # addresses with a nonzero balance that can be generated from the seed
        return self.iotaapi.get_account_data(
            start=index, stop=stop_index
        )['balance']
