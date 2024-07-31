# keyboard.py
#
# Copyright 2024 mirkobrombin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundationat version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
import os
import re
import subprocess

from gi.repository import Adw, Gio, GLib, Gtk

from vanilla_installer.core.keymaps import KeyMaps

@Gtk.Template(resource_path="/org/vanillaos/Installer/gtk/widget-keyboard.ui")
class KeyboardRow(Adw.ActionRow):
    __gtype_name__ = "KeyboardRow"

    select_button = Gtk.Template.Child()
    suffix_bin = Gtk.Template.Child()

    def __init__(
        self, title, subtitle, layout, variant, key, selected_keyboard, **kwargs
    ):
        super().__init__(**kwargs)
        self.__title = title
        self.__subtitle = subtitle
        self.__layout = layout
        self.__variant = variant
        self.__key = key
        self.__selected_keyboard = selected_keyboard

        self.set_title(title)
        self.set_subtitle(subtitle)
        self.suffix_bin.set_label(key)

        self.select_button.connect("toggled", self.__on_check_button_toggled)

    def __on_check_button_toggled(self, widget):
        if widget.get_active():
            self.__selected_keyboard.append({"layout": self.__layout, "model": "pc105", "variant": self.__variant})
            self.get_parent().emit("selected-rows-changed")
        else:
            self.__selected_keyboard.remove({"layout": self.__layout, "model": "pc105", "variant": self.__variant})
            self.get_parent().emit("selected-rows-changed")



@Gtk.Template(resource_path="/org/vanillaos/Installer/gtk/default-keyboard.ui")
class VanillaDefaultKeyboard(Adw.Bin):
    __gtype_name__ = "VanillaDefaultKeyboard"

    btn_next = Gtk.Template.Child()
    entry_test = Gtk.Template.Child()
    entry_search_keyboard = Gtk.Template.Child()
    all_keyboards_group = Gtk.Template.Child()
    selected_keyboard = []

    search_controller = Gtk.EventControllerKey.new()
    test_focus_controller = Gtk.EventControllerFocus.new()

    match_regex = re.compile(r"[^a-zA-Z0-9 ]")

    def __init__(self, window, distro_info, key, step, **kwargs):
        super().__init__(**kwargs)
        self.__window = window
        self.__distro_info = distro_info
        self.__key = key
        self.__step = step
        self.delta = True
        self.__keymaps = KeyMaps()
        self.__keyboard_rows = self.__generate_keyboard_list_widgets(
            self.selected_keyboard
        )


    def gen_deltas(self):
        for i, widget in enumerate(self.__keyboard_rows):
            self.all_keyboards_group.append(widget)

        # controllers
        self.entry_search_keyboard.add_controller(self.search_controller)
        self.entry_test.add_controller(self.test_focus_controller)

        # signals
        self.btn_next.connect("clicked", self.__next)
        self.all_keyboards_group.connect(
            "selected-rows-changed", self.__keyboard_verify
        )
        self.all_keyboards_group.connect("row-selected", self.__keyboard_verify)
        self.all_keyboards_group.connect("row-activated", self.__keyboard_verify)
        self.__window.carousel.connect("page-changed", self.__keyboard_verify)

        self.search_controller.connect("key-released", self.__on_search_key_pressed)
        if "VANILLA_NO_APPLY_XKB" not in os.environ:
            self.test_focus_controller.connect("enter", self.__apply_layout)


    def del_deltas(self):
        self.all_keyboards_group.remove_all()


    def __keyboard_verify(self, *args):
        if self.selected_keyboard != []:
            self.btn_next.set_sensitive(True)
        else:
            self.btn_next.set_sensitive(False)

    def __next(self, *args):
        if "VANILLA_NO_APPLY_XKB" in os.environ:
            self.__window.next()
        else:
            self.__window.next(None, self.__apply_layout)

    def get_finals(self):

        if self.selected_keyboard == []:
            return {
                "keyboard": [{"layout": "us", "model": "pc105", "variant": ""}]
            }  # fallback

        return {
            "keyboard": self.selected_keyboard 
        }

    def __generate_keyboard_list_widgets(self, selected_keyboard):
        keyboard_widgets = []

        all_keyboard_layouts = {
            value["display_name"]: {
                "key": key,
                "country": country,
                "layout": value["xkb_layout"],
                "variant": value["xkb_variant"],
            }
            for country in self.__keymaps.list_all.keys()
            for key, value in self.__keymaps.list_all[country].items()
        }

        # Changed display_name as this charchter string is causing gtk markup error
        if all_keyboard_layouts.get("Czech (with <\|> key)"):
            all_keyboard_layouts["Czech (bksl)"] = all_keyboard_layouts.pop(
                "Czech (with <\|> key)"
            )

        for keyboard_title, content in all_keyboard_layouts.items():
            keyboard_key = content["key"]
            keyboard_country = content["country"]
            keyboard_layout = content["layout"]
            keyboard_variant = content["variant"]
            keyboard_row = KeyboardRow(
                keyboard_title,
                keyboard_country,
                keyboard_layout,
                keyboard_variant,
                keyboard_key,
                selected_keyboard,
            )

            keyboard_widgets.append(keyboard_row)

        return keyboard_widgets

    def __apply_layout(self, *args):
        if self.selected_keyboard == []:
            return

        # set the layout
        self.__set_keyboard_layout(self.selected_keyboard)

    def __on_search_key_pressed(self, *args):
        keywords = self.match_regex.sub(
            "", self.entry_search_keyboard.get_text().lower()
        )

        for row in self.all_keyboards_group:
            row_title = self.match_regex.sub("", row.get_title().lower())
            row_subtitle = self.match_regex.sub("", row.get_subtitle().lower())
            row_label = self.match_regex.sub("", row.suffix_bin.get_label().lower())

            search_text = row_title + " " + row_subtitle + " " + row_label
            row.set_visible(re.search(keywords, search_text, re.IGNORECASE) is not None)

    def __set_keyboard_layout(self, selected_keyboard):
        Gio.Settings.new("org.gnome.desktop.input-sources").set_value(
            "sources",
            GLib.Variant.new_array(
                GLib.VariantType("(ss)"),
                self.__create_keyboard_layout_array(selected_keyboard) 
            ),
        )

    def __create_keyboard_layout_array(self, selected_keyboard):
        keyboard_layout_array = []
        for i in selected_keyboard:
            value = i["layout"]
            if i["variant"] != "":
                value += "+" + i["variant"]
            keyboard_layout_array.append(GLib.Variant.new_tuple(GLib.Variant.new_string("xkb"), GLib.Variant.new_string(value)))
        return keyboard_layout_array
