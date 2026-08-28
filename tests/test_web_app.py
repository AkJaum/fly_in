"""Structural tests for the browser viewport and fullscreen presentation."""

import inspect
import unittest

from src.web_app import FlyInWebView, PAGE_STYLES, VIEWPORT_SCRIPT


class WebAppPresentationTests(unittest.TestCase):
    """Keep fullscreen layout and camera behavior aligned with the contract."""

    def test_fullscreen_mode_keeps_only_utility_bar_and_graph(self) -> None:
        """Hide secondary page chrome while the simulation fills the screen."""
        self.assertIn("body.flyin-fullscreen .flyin-header", PAGE_STYLES)
        self.assertIn("body.flyin-fullscreen .below-fold-content", PAGE_STYLES)
        self.assertIn(
            "body.flyin-fullscreen .simulation-utility-bar",
            PAGE_STYLES,
        )
        self.assertIn("body.flyin-fullscreen .network-graph", PAGE_STYLES)
        self.assertIn("toggleFullscreen()", VIEWPORT_SCRIPT)
        self.assertIn("fullscreenchange", VIEWPORT_SCRIPT)

    def test_fullscreen_handler_is_deferred_until_click(self) -> None:
        """Defer fullscreen until click instead of invoking it on render."""
        source = inspect.getsource(FlyInWebView._build_view_controls)
        self.assertIn(
            '"() => window.flyinViewport?.toggleFullscreen()"',
            source,
        )
        self.assertNotIn(
            'js_handler="window.flyinViewport?.toggleFullscreen()"',
            source,
        )

    def test_zoom_uses_one_viewbox_camera(self) -> None:
        """Keep every SVG object anchored in one zoom coordinate system."""
        self.assertIn("const readBaseViewBox", VIEWPORT_SCRIPT)
        self.assertNotIn("const BASE_VIEWBOX", VIEWPORT_SCRIPT)
        self.assertIn(
            "svg.setAttribute(\n            'viewBox'",
            VIEWPORT_SCRIPT,
        )
        self.assertIn("updateDroneMarkers(svg, state.scale)", VIEWPORT_SCRIPT)
        self.assertIn("const DRONE_ZOOM_GROWTH = 0.35", VIEWPORT_SCRIPT)
        self.assertIn("scale(${markerScale})", VIEWPORT_SCRIPT)
        self.assertIn("previous.base.key !== base.key", VIEWPORT_SCRIPT)
        self.assertNotIn("--viewport-inverse-scale", PAGE_STYLES)
        self.assertNotIn("world.setAttribute", VIEWPORT_SCRIPT)
        self.assertNotIn(
            "scale(var(--viewport-inverse-scale))",
            PAGE_STYLES,
        )

    def test_zoom_controls_are_deferred_client_callbacks(self) -> None:
        """Keep zoom responsive without a Python server round trip."""
        source = inspect.getsource(FlyInWebView._build_view_controls)
        self.assertIn(
            'js_handler="() => window.flyinViewport?.zoomBy(0.8)"',
            source,
        )
        self.assertIn(
            'js_handler="() => window.flyinViewport?.zoomBy(1.25)"',
            source,
        )
        self.assertIn(
            'js_handler="() => window.flyinViewport?.reset()"',
            source,
        )

    def test_map_selection_loads_without_a_separate_button(self) -> None:
        """Keep the selector and active simulation state synchronized."""
        source = inspect.getsource(FlyInWebView._build_controls)
        self.assertIn("on_change=self._load_selected_map", source)
        self.assertIn(
            "self.map_select.set_value(self.controller.selected_map)",
            inspect.getsource(FlyInWebView._load_selected_map),
        )
        self.assertNotIn('ui.button(\n                "Load"', source)
        self.assertNotIn("latest-movement-row", source)
        self.assertNotIn("movement_label", source)

    def test_controller_components_use_expanded_dimensions(self) -> None:
        """Keep controller fields, buttons, and metrics comfortably sized."""
        self.assertIn("max-width: 600px", PAGE_STYLES)
        self.assertIn("min-width: 420px", PAGE_STYLES)
        self.assertIn(
            ".utility-controls .q-btn:not(.q-btn--round)",
            PAGE_STYLES,
        )
        self.assertIn("min-height: 52px", PAGE_STYLES)
        self.assertIn("min-height: 88px", PAGE_STYLES)


if __name__ == "__main__":
    unittest.main()
