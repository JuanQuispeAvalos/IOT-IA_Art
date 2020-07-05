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
Manages the display for iotacanvas, including displaying images
and generating qr codes
"""
import subprocess
import sys
import tkinter

from PIL import Image, ImageTk, ImageFilter, ImageEnhance
import qrcode

import webapp


def make_qrcode(text, qr_size):
    """Creates a square qr of qr_size pixels encoding passed-in text"""
    qr_border_size = 4
    qr_boxes = 41
    box_size = qr_size // (qr_boxes + 2*qr_border_size)
    qr = qrcode.QRCode(
        version=6,  # 41x41, allows at least 84 characters
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=qr_border_size,
    )
    qr.add_data(text)
    img = qr.make_image(fill_color="black", back_color="white")
    return img


def turn_on():
    """Attempts to turn the monitor screen on.

    Return value of True indicates success."""
    try:
        subprocess.call("vcgencmd display_power 1", shell=True)
        return True
    except OSError as e:
        print("Couldn't turn monitor on:", e, file=sys.stderr)
        return False


def turn_off():
    """Attempts to turn the monitor screen off.

    Return value of True indicates success."""
    try:
        subprocess.call("vcgencmd display_power 0", shell=True)
        return True
    except OSError as e:
        print("Couldn't turn monitor off:", e, file=sys.stderr)
        return False


class Display:
    """Manipulates the display for IOTA Canvas"""
    FRAME_WIDTH = 10  # frame width in pixels
    FRAME_COLOR = (255, 255, 255)  # frame color in RGB

    def __init__(self, user_settings, stop_flag):
        self.user_settings = user_settings
        self.stop_flag = stop_flag
        self._fullscreen_state = True
        # setup tkinter windows and default canvas
        self._root = tkinter.Tk()
        self._root.attributes("-fullscreen", self._fullscreen_state)
        self._width = self._root.winfo_screenwidth()
        self._height = self._root.winfo_screenheight()
        # initialize main panel
        self._panel = tkinter.Canvas(self._root, highlightthickness=0)
        self._panel.pack(fill="both", expand="yes")
        # show background image
        background_img = Image.open(
            user_settings.get(['display', 'default_background_image'])
        )
        background_img = self.format_background(background_img, blur_size=2)
        self._background_img = ImageTk.PhotoImage(background_img)
        self._background = self._panel.create_image(
            self._width//2,
            self._height//2, image=self._background_img)
        # show foreground image
        self._foreground_img = \
            Image.open(user_settings.get(['display', 'default_image']))
        self._foreground_img = ImageTk.PhotoImage(self._foreground_img)
        self._foreground = self._panel.create_image(
            self._width//2,
            self._height//2, image=self._foreground_img)
        # create text element
        self._text = self._panel.create_text(
            self._width//2,
            self._height - self._height//5, text="IOTA Canvas",
            font=("courier", 30, "bold"),
            width=int(self._width*0.75),
            justify="center"
        )
        # bind events and keys
        self._root.bind("<<ShowServerAddress>>", self._show_server_address)
        # bind show_image in a different way because we need to pass some data
        # to the callback function
        show_img_cmd = self._root.register(self._show_image)
        self._root.tk.call("bind", self._root, "<<ShowImage>>",
                           show_img_cmd + " %d")
        self._root.bind("<<Stop>>", self._stop)
        self._root.bind("<F11>", self._toggle_fullscreen)
        self._root.bind("<Escape>", self._stop)
        #self._root.wm_attributes("-topmost", "true")

    def run(self):
        """Start running the main display loop"""
        try:
            self._root.mainloop()
        finally:
            # if there's an exception or the mainloop exits some other way,
            # stop the display
            self._stop()

    def is_running(self):
        """Returns true if the display loop is active"""
        return self._root is not None

    def action(self, action_string, additional_data=""):
        """Queue an action for the display to take.
           Valid actions are: 'ShowServerAddress', 'ShowImage', 'Stop'
           additional_data will be provided to bound function as a string."""
        if self.is_running():
            # to prevent hanging: waiting to add an event which can't be added,
            # first check if the display is running
            # this means that actions cannot be queued before mainloop starts
            self._root.event_generate(action_string,
                                      data=str(additional_data), when="tail"
                                      )
            return True
        return False

    def _stop(self, *_):
        self.stop_flag.set()
        if self.is_running():
            self._root.quit()
            self._root = None

    def _update_image(self, image, new_x=None, new_y=None):
        """Update passed-in image on screen.

        If new_x or new_y is not None,
        the image is also moved to the new position."""
        photo = ImageTk.PhotoImage(image)
        # need to keep a reference to the image (below)
        # otherwise the Python garbage collector will delete it
        # see https://effbot.org/tkinterbook/photoimage.htm for more info
        self._foreground_img = photo  # keep a reference!
        self._panel.itemconfig(self._foreground, image=photo)
        self._update_coords(self._foreground, new_x, new_y)

    def _update_background(self, image):
        """Update background image"""
        photo = ImageTk.PhotoImage(image)
        self._background_img = photo
        self._panel.itemconfig(self._background, image=photo)

    def _update_text(self, text, new_x=None, new_y=None):
        """Update text shown on display.

        If new_x or new_y is not None,
        the text is also moved to the new position."""
        self._panel.itemconfig(self._text, text=text)
        self._update_coords(self._text, new_x, new_y)

    def _update_coords(self, item_id, new_x, new_y):
        coords = self._panel.coords(item_id)
        if new_y is not None:
            coords[1] = new_y
        if new_x is not None:
            coords[0] = new_x
        self._panel.coords(item_id, coords)

    def _show_image(self, image_file):
        """Show the image in image_file on the screen."""
        image = Image.open(image_file)
        background_img = self.format_background(image)
        image = self._make_fullscreen(image)
        self._update_background(background_img)
        self._update_image(image)
        self._update_text("")

    def _show_server_address(self, _):
        """Show the settings website address on the screen."""
        ip = webapp.get_IP()
        site_address = f"http://{ip}:{self.user_settings.get(['server', 'port'])}"
        qr_fraction = 0.65  # make qr code 65% of screen size
        qr_size = qr_fraction * min(self._width, self._height)
        qr = make_qrcode(site_address, qr_size=qr_size)
        qr_y = self._height//2.6  # qr y position
        self._update_image(qr, new_y=qr_y)
        text = f"Visit {site_address}\nto configure\nIOTA Canvas"
        # center text vertically in leftover space below qr code
        qr_bottom_edge = qr_y + qr.get_image().size[0] / 2
        text_y = (self._height + qr_bottom_edge) // 2
        self._update_text(text, new_y=text_y)
        # set background to default
        background = Image.open(
            self.user_settings.get(['display', 'default_background_image'])
        )
        background = self.format_background(background)
        self._update_background(background)

    def _make_fullscreen(self, image):
        """Enlarges image as large as screen while maintaining aspect ratio.
           Also adds a frame around image."""
        screenRatio = self._width / self._height
        imageRatio = image.size[0] / image.size[1]
        if screenRatio < imageRatio:
            # image is skinnier from top to bottom than the screen
            # so set the image width to the screen width
            newWidth = self._width - 2*Display.FRAME_WIDTH
            newHeight = int(image.size[1] * (newWidth / image.size[0]))
        elif screenRatio > imageRatio:
            # screen aspect ratio is greater than image aspect ratio
            # therefore, the image height should equal screen height
            newHeight = self._height - 2*Display.FRAME_WIDTH
            # the width should be scaled by the change in height
            newWidth = int(image.size[0] * (newHeight / image.size[1]))
        else:
            # screen and image are same size
            newWidth = self._width
            newHeight = self._height
        image = image.resize((newWidth, newHeight))
        # if the image doesn't match the screen dimensions,
        # then add a frame and background image
        if newWidth != self._width or newHeight != self._height:
            # create frame
            frame = Image.new('RGB',
                              (newWidth + 2*Display.FRAME_WIDTH,
                               newHeight + 2*Display.FRAME_WIDTH), Display.FRAME_COLOR)
            image = self._layer_images(frame, image)
        return image

    def format_background(self, image, blur_size=10):
        """Returns background image which is original image resized
         so that it's smallest dimension is the same size as the screen
         and blurred."""
        blurFilter = ImageFilter.GaussianBlur(radius=blur_size)
        screenDimMax = max(self._width, self._height)
        scaleRatio = screenDimMax / max(image.size)
        # resize and blur background image
        background_img = image.resize((int(image.size[0]*scaleRatio),
                                       int(image.size[1]*scaleRatio))).filter(blurFilter)
        # darken the background image
        enhancer = ImageEnhance.Brightness(background_img)
        background_img = enhancer.enhance(0.6)
        return background_img

    def _layer_images(self, background_img, image):
        """Copy image on top of background_img."""
        back_width, back_height = background_img.size
        img_width, img_height = image.size
        offset = (int((back_width - img_width) // 2),
                  int((back_height - img_height) // 2))
        # backgroundImg.paste(image, offset, image)
        background_img.paste(image, offset)
        return background_img

    def _toggle_fullscreen(self, _=None):
        """Toggles fullscreen"""
        self._fullscreen_state = not self._fullscreen_state
        self._root.attributes("-fullscreen", self._fullscreen_state)


if __name__ == '__main__':
    # short example of using the functions in this module
    import threading
    from common import settings
    stop = threading.Event()
    disp = Display(settings.Settings(), stop)
    disp.action("<<ShowImage>>", settings.RESOURCES_DIR /
                "default_image.png")
    disp.run()
