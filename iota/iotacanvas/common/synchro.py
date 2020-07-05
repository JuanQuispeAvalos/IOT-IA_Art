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
Provides custom synchronization class and methods for IOTA Canvas.
"""

import queue

# pylint: disable=protected-access

# the below functions modify an event so that it will trigger a callback
# when it is set or cleared
def cb_set(event):
    """Event set which also triggers a callback"""
    event._set()
    event.cb()

def cb_clear(event):
    """Event clear which also triggers a callback"""
    event._clear()
    event.cb()

def convert_to_callback_event(event, cb):
    """Modify event so it calls a callback when set or clear are called"""
    if getattr(event, 'is_callback', False):
        # event is already a callback event
        return
    event.is_callback = True
    # keep track of original set and clear
    event._set = event.set
    event._clear = event.clear
    # assign callback
    event.cb = cb
    # assign new set and clear
    event.set = lambda: cb_set(event)
    event.clear = lambda: cb_clear(event)


class IotaCanvasEvent():
    """Container for IOTA Canvas events."""
    def __init__(self, name, data=None):
        self.name = name
        self.data = data


class PrioritizedItem:
    """Wrapper for items stored in priority queues."""
    def __init__(self, priority, data):
        self.priority = priority
        self.data = data

    def __lt__(self, other):
        return self.priority < other.priority


class EventQueue():
    """Wrapper for PriorityQueue to easily put and get items.

    Also includes get_and_wait_on_event which allows waiting
    on an event and waiting for data from the queue."""

    def __init__(self, maxsize=0):
        self._queue = queue.PriorityQueue(maxsize)
        # notifier queue is used when both the queue and an event are waited on
        self._notifier = queue.Queue()

    def put(self, event_name, data=None, priority=100, block=True, timeout=None):
        """Put an item into the queue and optionally specify its priority.

        This method behaves the same way as queue.put().
        timeout specifies how long to block for if the queue is full."""
        item = IotaCanvasEvent(event_name, data)
        priority_item = PrioritizedItem(priority, item)
        self._queue.put(priority_item, block=block, timeout=timeout)
        self._cb_put(item)

    def get(self, block=True, timeout=None):
        """Get an item from the queue.

        This method behaves the same way as queue.get().
        timeout specifies how long to block for if the queue is empty."""
        item = self._queue.get(block=block, timeout=timeout)
        return item.data

    def get_and_wait_on_event(self, event, timeout=None):
        """Waits until there is an item in the queue,
        or the event is set.

        If the event is set, this function returns True.
        Otherwise, it returns the item in the queue. A
        timeout raises an exception, the same as queue.get()"""
        convert_to_callback_event(event, lambda: self._cb_put(True))
        if event.is_set():
            return True
        self._clear_notifier()
        # wait on the notifier queue
        # if the event is set, it adds a blank item to the notifier queue
        # if an item is added to the regular queue, it is also placed in the
        # notifier queue
        return self._notifier.get(timeout=timeout)

    def _clear_notifier(self):
        # ensure notifier queue is empty
        while self._notifier.qsize() != 0:
            try:
                # remove elements until there are none left
                self._notifier.get_nowait()
            except queue.Empty:
                pass

    def _cb_put(self, item):
        # add an item to the notifier queue so it will stop waiting
        self._notifier.put(item)
