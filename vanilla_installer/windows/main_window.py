# window.py
#
# Copyright 2022 mirkobrombin
# Copyright 2022 muqtadir
#
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

import json
import os

from gi.repository import Adw, Gtk

from vanilla_installer.utils.builder import Builder
from vanilla_installer.utils.processor import Processor
from vanilla_installer.views.confirm import VanillaConfirm
from vanilla_installer.views.done import VanillaDone
from vanilla_installer.views.progress import VanillaProgress


@Gtk.Template(resource_path="/org/vanillaos/Installer/gtk/window.ui")
class VanillaWindow(Adw.ApplicationWindow):
    __gtype_name__ = "VanillaWindow"

    carousel = Gtk.Template.Child()
    carousel_indicator_dots = Gtk.Template.Child()
    btn_back = Gtk.Template.Child()
    toasts = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # this starts the builder and generates the widgets
        # to put in the carousel
        self.__builder = Builder(self)

        # system views
        self.__view_confirm = VanillaConfirm(self)
        self.__view_progress = VanillaProgress(self, self.recipe.get("tour", {}))
        self.__view_done = VanillaDone(self)

        # this builds the UI with the widgets generated by the builder
        self.__build_ui()

        # connect system signals
        self.__connect_signals()

    def __connect_signals(self):
        self.btn_back.connect("clicked", self.back)
        self.carousel.connect("page-changed", self.__on_page_changed)
        self.__builder.widgets[-1].btn_next.connect("clicked", self.update_finals)
        self.__view_confirm.connect(
            "installation-confirmed", self.on_installation_confirmed
        )

    def __build_ui(self):
        if "VANILLA_FORCE_TOUR" not in os.environ:
            for widget in self.__builder.widgets:
                self.carousel.append(widget)
        else:
            self.__on_page_changed()

        self.carousel.append(self.__view_confirm)
        self.carousel.append(self.__view_progress)
        self.carousel.append(self.__view_done)

    def __on_page_changed(self, *args):
        cur_index = self.carousel.get_position()
        page = self.carousel.get_nth_page(cur_index)

        if page not in [self.__view_progress, self.__view_done]:
            self.btn_back.set_visible(cur_index != 0.0)
            self.btn_back.set_sensitive(cur_index != 0.0)
            self.carousel_indicator_dots.set_visible(cur_index != 0.0)
            return

        self.btn_back.set_visible(False)
        self.btn_back.set_sensitive(False)
        self.carousel_indicator_dots.set_visible(False)

        # keep the btn_back button locked if this is the last page
        if page == self.__view_done:
            return

    def update_finals(self, *args):
        # collect all the finals
        if "VANILLA_FORCE_TOUR" not in os.environ:
            self.finals = self.__builder.get_finals()
        else:
            self.finals = json.loads(os.environ["VANILLA_FORCE_TOUR"])

        self.__view_confirm.update(self.finals)

    def on_installation_confirmed(self, *args):
        recipe = Processor.gen_install_recipe(
            self.recipe.get("log_file", "/tmp/vanilla_installer.log"),
            self.finals,
            self.recipe,
        )
        self.next()
        self.__view_progress.start(recipe)

    def next(self, widget=None, fn=None, *args):
        if fn is not None:
            fn()

        cur_index = self.carousel.get_position()
        page = self.carousel.get_nth_page(cur_index + 1)
        self.carousel.scroll_to(page, True)

    def back(self, *args):
        cur_index = self.carousel.get_position()
        page = self.carousel.get_nth_page(cur_index - 1)
        self.carousel.scroll_to(page, True)

    def toast(self, message, timeout=3):
        toast = Adw.Toast.new(message)
        toast.props.timeout = timeout
        self.toasts.add_toast(toast)

    def set_installation_result(self, result, terminal):
        self.__view_done.set_result(result, terminal)
        self.next()
