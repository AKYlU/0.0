from __future__ import annotations
from typing import TYPE_CHECKING, Optional

import logging

from pywm import PYWM_PRESSED, PYWM_MOD_LOGO, PyWMModifiers

from .overlay import Overlay
from ..config import configured_value

from ..gestures import Gesture, GestureListener, LowpassGesture

if TYPE_CHECKING:
    from ..layout import Layout
    from ..view import View
    from ..state import LayoutState

logger = logging.getLogger(__name__)

conf_anim_t = configured_value("anim_time", .3)

conf_lp_freq = configured_value('gestures.lp_freq', 60.)
conf_lp_inertia = configured_value('gestures.lp_inertia', .8)

conf_gesture_binding_move_resize = configured_value('gesture_bindings.move_resize', ('L', 'move-1', 'swipe-2'))

class MoveResizeFloatingOverlay(Overlay):
    def __init__(self, layout: Layout, view: View):
        super().__init__(layout)


        self.layout.update_cursor(False)
        self._cursor = self.layout.cursor_pos

        self.view = view
        self.i = 0.
        self.j = 0.
        self.workspace = self.layout.workspaces[0]
        self.ws_state = self.layout.state.get_workspace_state(self.workspace)

        try:
            state, self.ws_state, ws_handle = self.layout.state.find_view(self.view)
            self.workspace = [w for w in self.layout.workspaces if w._handle == ws_handle][0]
            self.i, self.j = state.float_pos
            self.w, self.h = state.float_size

            self.layout.update(
                self.layout.state.setting_workspace_state(
                    self.workspace, self.ws_state.replacing_view_state(
                        self.view,
                        scale_origin=(self.w, self.h)
                    )))
        except Exception:
            logger.warn("Unexpected: Could not access view %s state", self.view)

        self._motion_mode = True
        self._gesture_mode = False
        self._gesture_last_dx = 0.
        self._gesture_last_dy = 0.

    def move(self, dx: float, dy: float) -> None:
        self.i += dx * self.ws_state.size
        self.j += dy * self.ws_state.size

        self._cursor = self._cursor[0] + dx*self.workspace.width, self._cursor[1] + dy*self.workspace.height

        workspace, i, j, w, h = self.view.transform_to_closest_ws(self.workspace, self.i, self.j, self.w, self.h)

        if workspace != self.workspace:
            logger.debug("Move floating - switching workspace %d -> %d" % (self.workspace._handle, workspace._handle))
            self.layout.state.move_view_state(self.view, self.workspace, workspace)
            self.workspace = workspace

        self.i = i
        self.j = j
        self.w = round(w) # pixels
        self.h = round(h) # pixels

        self.layout.state.update_view_state(self.view, float_pos=(self.i, self.j), float_size=(self.w, self.h))
        self.layout.damage()

    def resize(self, dx: float, dy: float) -> None:
        self.w += round(dx * self.workspace.width)
        self.h += round(dy * self.workspace.height)

        workspace, i, j, w, h = self.view.transform_to_closest_ws(self.workspace, self.i, self.j, self.w, self.h)

        if workspace != self.workspace:
            logger.debug("Move floating - switching workspace %d -> %d" % (self.workspace._handle, workspace._handle))
            self.layout.state.move_view_state(self.view, self.workspace, workspace)
            self.workspace = workspace

        self.i = i
        self.j = j
        self.w = round(w) # pixels
        self.h = round(h) # pixels

        self.layout.state.update_view_state(self.view, float_pos=(self.i, self.j), float_size=(self.w, self.h))
        self.layout.damage()

    def gesture_move(self, values: dict[str, float]) -> None:
        if self._gesture_mode:
            self.move(
                values['delta_x'] - self._gesture_last_dx,
                values['delta_y'] - self._gesture_last_dy)
            self._gesture_last_dx = values['delta_x']
            self._gesture_last_dy = values['delta_y']

    def gesture_resize(self, values: dict[str, float]) -> None:
        if self._gesture_mode:
            self.resize(
                values['delta_x'] - self._gesture_last_dx,
                values['delta_y'] - self._gesture_last_dy)
            self._gesture_last_dx = values['delta_x']
            self._gesture_last_dy = values['delta_y']

    def gesture_finish(self) -> None:
        self._gesture_mode = False
        self._gesture_last_dx = 0
        self._gesture_last_dy = 0

        if not self.layout.modifiers.has(conf_gesture_binding_move_resize()[0]):
            logger.debug("MoveResizeFloatingOverlay: Exiting on gesture end")
            self.layout.exit_overlay()


    def on_motion(self, time_msec: int, delta_x: float, delta_y: float) -> bool:
        if self._motion_mode:
            self.move(delta_x / self.workspace.width, delta_y / self.workspace.height)
        return False

    def on_button(self, time_msec: int, button: int, state: int) -> bool:
        if self._motion_mode:
            logger.debug("MoveFloatingOverlay: Exiting on mouse release")
            self.layout.exit_overlay()
            return True
        return False

    def on_gesture(self, gesture: Gesture) -> bool:
        if gesture.kind == conf_gesture_binding_move_resize()[2]:
            logger.debug("MoveResizeFloatingOverlay: New TwoFingerSwipePinch")

            self._motion_mode = False
            self._gesture_mode = True
            LowpassGesture(gesture, conf_lp_inertia(), conf_lp_freq()).listener(GestureListener(
                self.gesture_resize,
                self.gesture_finish
            ))
            return True

        if gesture.kind == conf_gesture_binding_move_resize()[1]:
            logger.debug("MoveResizeFloatingOverlay: New SingleFingerMove")

            self._motion_mode = False
            self._gesture_mode = True
            LowpassGesture(gesture, conf_lp_inertia(), conf_lp_freq()).listener(GestureListener(
                self.gesture_move,
                self.gesture_finish
            ))
            return True

        return False


    def on_modifiers(self, modifiers: PyWMModifiers, last_modifiers: PyWMModifiers) -> bool:
        if last_modifiers.pressed(modifiers).has(conf_gesture_binding_move_resize()[0]):
            if self._gesture_mode == False and self._motion_mode == False:
                logger.debug("MoveResizeFloatingOverlay: Requesting close after Mod release")
                self.layout.exit_overlay()
            return True
        return False


    def _exit_transition(self) -> tuple[Optional[LayoutState], float]:
        self.layout.update_cursor(True, (int(self._cursor[0]), int(self._cursor[1])))
        try:
            state = self.layout.state.copy()
            state.update_view_state(self.view, scale_origin=None)
            state.constrain()
            return state, conf_anim_t()
        except Exception:
            logger.warn("Unexpected: Error accessing view %s state", self.view)
            return None, 0
