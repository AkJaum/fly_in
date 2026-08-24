"""NiceGUI browser interface for the Fly-in simulation."""

import argparse
import html
from collections.abc import Sequence
from pathlib import Path

from nicegui import ui
from nicegui.elements.html import Html
from nicegui.elements.label import Label
from nicegui.elements.log import Log
from nicegui.elements.select import Select
from nicegui.elements.timer import Timer

from src.visualization import BrowserSimulation, SvgMapRenderer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INITIAL_MAP: Path | None = None
INITIAL_TURN = 0
PAGE_STYLES = """
body {
    background: #050b14;
    color: #e2e8f0;
    overflow-x: hidden;
}
.flyin-shell {
    width: min(1500px, 100%);
    margin: 0 auto;
    padding: 0 20px 24px;
}
.flyin-header {
    height: 64px;
    min-height: 64px;
}
.simulation-cockpit {
    display: grid;
    gap: 10px;
    grid-template-rows: auto auto minmax(0, 1fr);
    height: calc(100dvh - 64px);
    min-height: 0;
    padding: 10px 0 12px;
    width: 100%;
}
.cockpit-controls {
    padding: 10px 14px;
}
.latest-movement-row {
    align-items: center;
    border-top: 1px solid #1e293b;
    display: flex;
    gap: 10px;
    margin-top: 8px;
    min-height: 25px;
    padding-top: 7px;
    width: 100%;
}
.latest-movement-label {
    color: #94a3b8;
    flex: 0 0 auto;
    font-size: 11px;
    letter-spacing: .06em;
    text-transform: uppercase;
}
.status-strip {
    display: grid;
    gap: 8px;
    grid-template-columns: 1.25fr repeat(6, 1fr);
    width: 100%;
}
.metric-card {
    min-width: 0;
    padding: 8px 12px;
}
.network-card {
    display: flex !important;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    padding: 8px;
}
.network-heading {
    align-items: center;
    display: flex;
    flex: 0 0 auto;
    justify-content: space-between;
    min-height: 38px;
    padding: 2px 10px 6px;
}
.network-graph {
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
    width: 100%;
}
.below-fold-content {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-top: 16px;
    width: 100%;
}
.flyin-card {
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid #1e293b;
    border-radius: 18px;
    box-shadow: 0 18px 45px rgba(0, 0, 0, 0.22);
}
.flyin-map {
    --viewport-inverse-scale: 1;
    cursor: grab;
    display: block;
    height: 100%;
    max-height: 100%;
    min-height: 0;
    touch-action: none;
    user-select: none;
    width: 100%;
}
.flyin-map.is-panning { cursor: grabbing; }
.flyin-map .map-world { transform-origin: 0 0; }
.flyin-map .zone-node,
.flyin-map .connection-badge,
.flyin-map .connection-label,
.flyin-map .transit-location,
.flyin-map .transit-count,
.flyin-map .drone-silhouette,
.flyin-map .occupancy-overflow,
.flyin-map .departure-beacon,
.flyin-map .arrival-beacon {
    transform: scale(var(--viewport-inverse-scale));
    transform-box: fill-box;
    transform-origin: center;
}
.flyin-map line,
.flyin-map .movement-path {
    vector-effect: non-scaling-stroke;
}
.flyin-map.zoom-overview .zone-detail,
.flyin-map.zoom-overview .connection-badge,
.flyin-map.zoom-overview .connection-label,
.flyin-map.zoom-overview .drone-id { display: none; }
.flyin-map.map-complex:not(.zoom-medium) .zone-detail,
.flyin-map.map-complex:not(.zoom-medium) .drone-id,
.flyin-map.map-complex:not(.zoom-medium) .drone-id-plate {
    display: none;
}
.flyin-map.map-complex:not(.zoom-detail) .connection-badge,
.flyin-map.map-complex:not(.zoom-detail) .connection-label {
    display: none;
}
.visual-grid {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
    gap: 1rem;
}
.visual-table {
    width: 100%;
    border-collapse: collapse;
    font: 500 13px system-ui, sans-serif;
}
.visual-table th {
    color: #94a3b8;
    font-size: 11px;
    letter-spacing: .06em;
    padding: 8px 10px;
    text-align: left;
    text-transform: uppercase;
}
.visual-table td {
    border-top: 1px solid #1e293b;
    padding: 9px 10px;
    vertical-align: top;
}
.movement-arrow {
    color: #67e8f9;
    font-weight: 800;
    padding: 0 5px;
}
.state-active { color: #e2e8f0; }
.state-transit { color: #facc15; }
.state-delivered { color: #4ade80; }
.legend-dot {
    border: 3px solid #07111f;
    border-radius: 999px;
    display: inline-block;
    height: 18px;
    margin-right: 6px;
    vertical-align: -4px;
    width: 18px;
}
.visual-empty {
    color: #94a3b8;
    padding: 12px 4px;
}
@media (max-width: 900px) {
    .visual-grid { grid-template-columns: 1fr; }
    .flyin-shell { padding: 0 10px 16px; }
    .simulation-cockpit {
        height: auto;
        min-height: calc(100dvh - 56px);
    }
    .flyin-header { height: 56px; min-height: 56px; }
    .status-strip { grid-template-columns: repeat(4, 1fr); }
    .network-card { min-height: 62vh; }
}
@media (max-height: 760px) and (min-width: 901px) {
    .flyin-header { height: 54px; min-height: 54px; padding-block: 6px; }
    .simulation-cockpit {
        height: calc(100dvh - 54px);
        padding-top: 7px;
    }
    .cockpit-controls { padding-block: 7px; }
    .metric-card { padding-block: 5px; }
    .network-heading { min-height: 30px; }
    .header-subtitle, .network-subtitle { display: none; }
}
.zone-label, .connection-label, .empty-label {
    fill: #cbd5e1;
    font: 600 16px system-ui, sans-serif;
    paint-order: stroke;
    stroke: #07111f;
    stroke-width: 5px;
}
.connection-label {
    fill: #94a3b8;
    font-size: 12px;
}
.zone-detail {
    fill: #94a3b8;
    font: 500 12px system-ui, sans-serif;
    paint-order: stroke;
    stroke: #07111f;
    stroke-width: 4px;
}
.map-caption {
    fill: #e2e8f0;
    font: 700 18px system-ui, sans-serif;
}
.type-symbol {
    fill: #07111f;
    font: 800 17px system-ui, sans-serif;
}
.transit-count, .overflow-count {
    fill: #07111f;
    font: 800 11px system-ui, sans-serif;
}
.drone-id {
    fill: #f8fafc;
    font: 900 10px system-ui, sans-serif;
    paint-order: stroke;
    stroke: #07111f;
    stroke-width: 3px;
}
.drone-body {
    fill: #cbd5e1;
    stroke: #07111f;
    stroke-width: 2.5px;
}
.drone-arm {
    stroke: #cbd5e1;
    stroke-linecap: round;
    stroke-width: 3px;
}
.drone-rotor {
    fill: #07111f;
    stroke: #e2e8f0;
    stroke-width: 2px;
}
.drone-status-light {
    animation: status-blink 1.15s ease-in-out infinite;
    filter: url(#drone-glow);
}
.drone-id-plate {
    fill: #07111f;
    stroke: #38bdf8;
    stroke-width: 1.5px;
}
.drone-transit .drone-status-light {
    animation-duration: .55s;
    fill: #facc15;
}
.drone-transit .drone-body { fill: #fde68a; }
.drone-transit .drone-id-plate { stroke: #facc15; }
.drone-delivered .drone-status-light {
    animation-duration: 1.8s;
    fill: #22c55e;
}
.drone-delivered .drone-body { fill: #86efac; }
.drone-delivered .drone-id-plate { stroke: #22c55e; }
.drone-zone .drone-status-light { fill: #38bdf8; }
.drone-moved .drone-status-light { fill: #67e8f9; }
.drone-moved .drone-body { fill: #a5f3fc; }
.drone-moved .drone-id-plate { stroke: #67e8f9; }
.drone-waiting .drone-status-light {
    animation-duration: 1.55s;
    fill: #fb7185;
}
.drone-waiting .drone-body { fill: #fecdd3; }
.drone-waiting .drone-id-plate { stroke: #fb7185; }
.drone-moved {
    animation: reveal-arrived-drone .16s ease-out 1.05s forwards;
    opacity: 0;
}
.animated-drone .drone-status-light {
    animation-duration: .35s;
    fill: #67e8f9;
}
.animated-drone .drone-body { fill: #a5f3fc; }
.animated-drone.restricted-flight .drone-body { fill: #fde68a; }
.animated-drone.restricted-flight .drone-status-light { fill: #facc15; }
.animated-drone {
    animation: retire-moving-drone .14s ease-in 1.05s forwards;
}
.movement-path {
    animation: reveal-movement-path .2s ease-out forwards;
    opacity: .78;
}
.departure-beacon {
    animation: departure-beacon .55s ease-out forwards;
}
.arrival-beacon {
    animation: arrival-beacon .72s ease-out .72s forwards;
    opacity: 0;
}
.destination-pulse {
    animation: destination-pulse 1.1s ease-out infinite;
    transform-box: fill-box;
    transform-origin: center;
}
@keyframes destination-pulse {
    from { opacity: .95; transform: scale(.9); }
    to { opacity: .1; transform: scale(1.18); }
}
@keyframes status-blink {
    0%, 100% { opacity: .28; }
    50% { opacity: 1; }
}
@keyframes reveal-arrived-drone {
    from { opacity: 0; }
    to { opacity: 1; }
}
@keyframes retire-moving-drone {
    from { opacity: 1; }
    to { opacity: 0; }
}
@keyframes reveal-movement-path {
    from { opacity: 0; stroke-dashoffset: 44; }
    to { opacity: .78; stroke-dashoffset: 0; }
}
@keyframes departure-beacon {
    from { opacity: 1; r: 8px; }
    to { opacity: 0; r: 24px; }
}
@keyframes arrival-beacon {
    from { opacity: 0; r: 8px; }
    45% { opacity: 1; }
    to { opacity: 0; r: 27px; }
}
"""

VIEWPORT_SCRIPT = """
<script>
(() => {
    if (window.flyinViewport) return;

    const clamp = (value, minimum, maximum) =>
        Math.min(maximum, Math.max(minimum, value));

    const getSvg = () =>
        document.querySelector('.network-graph svg.flyin-map');

    const getState = (svg) => {
        const container = svg.closest('.network-graph');
        if (!container) return null;
        if (!container.__flyinViewState) {
            container.__flyinViewState = {
                scale: 1,
                x: 0,
                y: 0,
                dragging: false,
            };
        }
        return container.__flyinViewState;
    };

    const updateSemanticZoom = (svg, scale) => {
        svg.classList.toggle('zoom-overview', scale < 0.78);
        svg.classList.toggle('zoom-medium', scale >= 1.28);
        svg.classList.toggle('zoom-detail', scale >= 1.72);
        const label = document.querySelector('.zoom-readout-ui');
        if (label) label.textContent = `${Math.round(scale * 100)}%`;
    };

    const apply = (svg, state) => {
        const world = svg.querySelector('.map-world');
        if (!world) return;
        world.setAttribute(
            'transform',
            `translate(${state.x} ${state.y}) scale(${state.scale})`,
        );
        const inverseScale = state.scale > 1 ? 1 / state.scale : 1;
        svg.style.setProperty(
            '--viewport-inverse-scale',
            inverseScale.toString(),
        );
        updateSemanticZoom(svg, state.scale);
    };

    const svgPoint = (svg, clientX, clientY) => {
        const point = svg.createSVGPoint();
        point.x = clientX;
        point.y = clientY;
        const matrix = svg.getScreenCTM();
        return matrix ? point.matrixTransform(matrix.inverse()) : point;
    };

    const zoomAt = (svg, state, factor, point) => {
        const nextScale = clamp(state.scale * factor, 0.45, 8);
        const worldX = (point.x - state.x) / state.scale;
        const worldY = (point.y - state.y) / state.scale;
        state.x = point.x - worldX * nextScale;
        state.y = point.y - worldY * nextScale;
        state.scale = nextScale;
        apply(svg, state);
    };

    const reset = (svg) => {
        const state = getState(svg);
        if (!state) return;
        Object.assign(state, {scale: 1, x: 0, y: 0});
        apply(svg, state);
    };

    const initialize = (svg) => {
        if (svg.dataset.viewportReady === 'true') return;
        svg.dataset.viewportReady = 'true';
        const state = getState(svg);
        if (!state) return;

        svg.addEventListener('wheel', (event) => {
            event.preventDefault();
            const point = svgPoint(svg, event.clientX, event.clientY);
            zoomAt(svg, state, event.deltaY < 0 ? 1.16 : 0.86, point);
        }, {passive: false});

        svg.addEventListener('pointerdown', (event) => {
            if (event.button !== 0) return;
            state.dragging = true;
            state.startX = event.clientX;
            state.startY = event.clientY;
            state.originX = state.x;
            state.originY = state.y;
            svg.classList.add('is-panning');
            svg.setPointerCapture(event.pointerId);
        });

        svg.addEventListener('pointermove', (event) => {
            if (!state.dragging) return;
            const box = svg.getBoundingClientRect();
            const viewBox = svg.viewBox.baseVal;
            state.x = state.originX +
                (event.clientX - state.startX) * viewBox.width / box.width;
            state.y = state.originY +
                (event.clientY - state.startY) * viewBox.height / box.height;
            apply(svg, state);
        });

        const stopDragging = (event) => {
            state.dragging = false;
            svg.classList.remove('is-panning');
            if (svg.hasPointerCapture(event.pointerId)) {
                svg.releasePointerCapture(event.pointerId);
            }
        };
        svg.addEventListener('pointerup', stopDragging);
        svg.addEventListener('pointercancel', stopDragging);
        svg.addEventListener('dblclick', () => reset(svg));
        apply(svg, state);
    };

    const initializeAll = () => {
        document.querySelectorAll('.network-graph svg.flyin-map')
            .forEach(initialize);
    };

    window.flyinViewport = {
        zoomBy(factor) {
            const svg = getSvg();
            if (!svg) return;
            const state = getState(svg);
            if (!state) return;
            const box = svg.viewBox.baseVal;
            zoomAt(
                svg,
                state,
                factor,
                {x: box.x + box.width / 2, y: box.y + box.height / 2},
            );
        },
        reset() {
            const svg = getSvg();
            if (svg) reset(svg);
        },
    };

    new MutationObserver(initializeAll).observe(
        document.documentElement,
        {childList: true, subtree: true},
    );
    requestAnimationFrame(initializeAll);
})();
</script>
"""


class FlyInWebView:
    """Build and coordinate one browser client's simulation controls."""

    map_select: Select
    status_label: Label
    turn_label: Label
    delivered_label: Label
    active_label: Label
    transit_label: Label
    moved_label: Label
    waiting_label: Label
    movement_label: Label
    graph_view: Html
    movement_detail: Html
    drone_manifest: Html
    movement_log: Log
    timer: Timer

    def __init__(self) -> None:
        """Create a controller and all page elements for one client."""
        self.controller = BrowserSimulation(
            PROJECT_ROOT,
            PROJECT_ROOT / "outputs.txt",
            INITIAL_MAP,
        )
        self.renderer = SvgMapRenderer()
        self.controller.configure()
        for _ in range(INITIAL_TURN):
            if self.controller.snapshot().is_complete:
                break
            self.controller.step()
        self._build()

    def _build(self) -> None:
        """Create the initial responsive browser layout."""
        ui.page_title("Fly-in Visualizer")
        ui.add_css(PAGE_STYLES)
        ui.add_head_html(VIEWPORT_SCRIPT)
        ui.colors(primary="#38bdf8", secondary="#22c55e")

        with ui.header().classes(
            "flyin-header bg-slate-950/95 border-b border-slate-800 "
            "px-6 py-2"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("flight", size="32px", color="primary")
                with ui.column().classes("gap-0"):
                    ui.label("Fly-in").classes("text-2xl font-bold")
                    ui.label("Drone routing visualizer").classes(
                        "header-subtitle text-xs text-slate-400"
                    )

        with ui.column().classes("flyin-shell"):
            with ui.element("section").classes("simulation-cockpit"):
                self._build_controls()
                self._build_status_cards()
                with ui.card().classes("flyin-card network-card w-full"):
                    with ui.row().classes("network-heading w-full"):
                        with ui.column().classes("gap-0"):
                            ui.label("Live network").classes(
                                "text-base font-semibold"
                            )
                            ui.label(
                                "Shapes identify zone rules; drone lights "
                                "show live state."
                            ).classes(
                                "network-subtitle text-xs text-slate-400"
                            )
                        with ui.row().classes("items-center gap-1"):
                            ui.label("Wheel zoom · drag pan").classes(
                                "text-xs text-slate-400 mr-1"
                            )
                            ui.button(
                                icon="remove",
                                on_click=self._zoom_out,
                            ).props(
                                'flat dense round aria-label="Zoom out"'
                            )
                            ui.label("100%").classes(
                                "zoom-readout-ui text-xs text-slate-300 "
                                "w-10 text-center"
                            )
                            ui.button(
                                icon="add",
                                on_click=self._zoom_in,
                            ).props(
                                'flat dense round aria-label="Zoom in"'
                            )
                            ui.button(
                                icon="center_focus_strong",
                                on_click=self._reset_view,
                            ).props(
                                'flat dense round aria-label="Reset view"'
                            )
                    self.graph_view = ui.html(
                        self.renderer.render(
                            self.controller.simulation_or_raise(),
                            self.controller.last_transitions,
                        )
                    ).classes("network-graph")
            with ui.element("section").classes("below-fold-content"):
                with ui.card().classes("flyin-card w-full p-3"):
                    with ui.column().classes("gap-0"):
                        ui.label("Visual key").classes("font-semibold")
                        self._build_legend()
                with ui.element("div").classes("visual-grid w-full"):
                    with ui.card().classes("flyin-card w-full p-5"):
                        ui.label("This turn").classes(
                            "text-lg font-semibold"
                        )
                        ui.label(
                            "Every accepted movement, including both "
                            "restricted transit turns."
                        ).classes("text-xs text-slate-400 mb-2")
                        self.movement_detail = ui.html().classes("w-full")
                    with ui.card().classes("flyin-card w-full p-5"):
                        ui.label("Drone positions").classes(
                            "text-lg font-semibold"
                        )
                        ui.label(
                            "Exact current location and lifecycle of every "
                            "drone."
                        ).classes("text-xs text-slate-400 mb-2")
                        with ui.scroll_area().classes("w-full h-64"):
                            self.drone_manifest = ui.html().classes("w-full")
                with ui.card().classes("flyin-card w-full p-5"):
                    ui.label("Movement history").classes(
                        "text-lg font-semibold mb-2"
                    )
                    self.movement_log = ui.log(max_lines=250).classes(
                        "w-full h-48 bg-slate-950 rounded-lg p-3 font-mono"
                    )

        self.timer = ui.timer(
            1.35,
            self._automatic_step,
            active=False,
            immediate=False,
        )
        self._refresh()

    def _build_controls(self) -> None:
        """Create map selection and playback controls."""
        with ui.card().classes("flyin-card cockpit-controls w-full"):
            with ui.row().classes(
                "w-full items-end gap-3 flex-wrap"
            ):
                self.map_select = ui.select(
                    options={
                        name: self._map_label(name)
                        for name in self.controller.available_maps
                    },
                    value=self.controller.selected_map,
                    label="Map",
                ).classes("min-w-72 grow").props("dark outlined")
                ui.button(
                    "Load",
                    on_click=self._load_selected_map,
                    icon="folder_open",
                )
                ui.button(
                    "Step",
                    on_click=self._single_step,
                    icon="skip_next",
                ).props("outline")
                ui.button(
                    "Play",
                    on_click=self._play,
                    icon="play_arrow",
                    color="secondary",
                )
                ui.button(
                    "Pause",
                    on_click=self._pause,
                    icon="pause",
                ).props("flat")
                ui.button(
                    "Reset",
                    on_click=self._reset,
                    icon="restart_alt",
                ).props("flat")
            with ui.element("div").classes("latest-movement-row"):
                ui.label("Latest").classes("latest-movement-label")
                self.movement_label = ui.label().classes(
                    "font-mono text-xs break-all"
                )

    def _build_status_cards(self) -> None:
        """Create status, turn, and movement summaries."""
        with ui.element("div").classes("status-strip"):
            with ui.card().classes("flyin-card metric-card"):
                ui.label("Status").classes("text-xs text-slate-400")
                self.status_label = ui.label().classes(
                    "text-xl font-semibold"
                )
            with ui.card().classes("flyin-card metric-card"):
                ui.label("Turn").classes("text-xs text-slate-400")
                self.turn_label = ui.label().classes("text-xl font-semibold")
            with ui.card().classes("flyin-card metric-card"):
                ui.label("Delivered").classes("text-xs text-slate-400")
                self.delivered_label = ui.label().classes(
                    "text-xl font-semibold"
                )
            with ui.card().classes("flyin-card metric-card"):
                ui.label("Active").classes("text-xs text-slate-400")
                self.active_label = ui.label().classes(
                    "text-xl font-semibold"
                )
            with ui.card().classes("flyin-card metric-card"):
                ui.label("Moved this turn").classes(
                    "text-xs text-slate-400"
                )
                self.moved_label = ui.label().classes(
                    "text-xl font-semibold text-cyan-300"
                )
            with ui.card().classes("flyin-card metric-card"):
                ui.label("Restricted transit").classes(
                    "text-xs text-slate-400"
                )
                self.transit_label = ui.label().classes(
                    "text-xl font-semibold text-yellow-300"
                )
            with ui.card().classes("flyin-card metric-card"):
                ui.label("Waiting").classes("text-xs text-slate-400")
                self.waiting_label = ui.label().classes(
                    "text-xl font-semibold"
                )

    @staticmethod
    def _build_legend() -> None:
        """Explain every visual encoding used by the network view."""
        with ui.row().classes(
            "w-full gap-x-5 gap-y-2 flex-wrap pt-1 text-xs "
            "text-slate-300"
        ):
            ui.label("Zone: N normal · P priority · R restricted · X blocked")
            ui.html(
                '<span><span class="legend-dot" '
                'style="background:#38bdf8"></span>active drone</span>'
            )
            ui.html(
                '<span><span class="legend-dot" '
                'style="background:#fb7185"></span>waiting drone</span>'
            )
            ui.html(
                '<span><span class="legend-dot" '
                'style="background:#facc15"></span>in transit</span>'
            )
            ui.html(
                '<span><span class="legend-dot" '
                'style="background:#22c55e"></span>delivered</span>'
            )
            ui.label("Double ring: start/end · dashed ring: blocked")

    def _load_selected_map(self) -> None:
        """Load the map currently selected by the user."""
        selected_map = self.map_select.value
        if not isinstance(selected_map, str):
            self._show_error("Select a valid map before loading")
            return
        try:
            self.timer.deactivate()
            self.controller.configure(selected_map)
            self.movement_log.clear()
            self.movement_log.push(f"Loaded {selected_map}")
            self._refresh()
            self._reset_view()
        except (OSError, RuntimeError, ValueError) as error:
            self._show_error(str(error))

    def _single_step(self) -> None:
        """Pause playback and advance exactly one simulation turn."""
        self.timer.deactivate()
        self._advance()

    def _automatic_step(self) -> None:
        """Advance one turn while automatic playback is active."""
        self._advance()

    def _advance(self) -> None:
        """Advance safely and synchronize every visual component."""
        try:
            movement = self.controller.step()
            if movement:
                turn = self.controller.snapshot().turn
                self.movement_log.push(f"Turn {turn}: {movement}")
            if self.controller.snapshot().is_complete:
                self.timer.deactivate()
            self._refresh()
        except (OSError, RuntimeError, ValueError) as error:
            self.timer.deactivate()
            self._show_error(str(error))

    def _play(self) -> None:
        """Start automatic playback unless the map is complete."""
        if self.controller.snapshot().is_complete:
            ui.notify("Reset the map before playing again", type="warning")
            return
        self.timer.activate()
        self._refresh()

    def _pause(self) -> None:
        """Pause automatic playback without changing simulation state."""
        self.timer.deactivate()
        self._refresh()

    def _reset(self) -> None:
        """Reset the current map and clear its visible movement history."""
        try:
            self.timer.deactivate()
            self.controller.reset()
            self.movement_log.clear()
            self.movement_log.push("Simulation reset")
            self._refresh()
        except (OSError, RuntimeError, ValueError) as error:
            self._show_error(str(error))

    @staticmethod
    def _zoom_in() -> None:
        """Zoom the graphical board toward its center."""
        ui.run_javascript("window.flyinViewport?.zoomBy(1.2)")

    @staticmethod
    def _zoom_out() -> None:
        """Zoom the graphical board away from its center."""
        ui.run_javascript("window.flyinViewport?.zoomBy(0.8)")

    @staticmethod
    def _reset_view() -> None:
        """Restore the graphical board's fitted position."""
        ui.run_javascript("window.flyinViewport?.reset()")

    def _refresh(self) -> None:
        """Synchronize labels and SVG with the current domain state."""
        simulation = self.controller.simulation_or_raise()
        snapshot = self.controller.snapshot()
        if snapshot.is_complete:
            status = "Complete"
        elif self.timer.active:
            status = "Running"
        else:
            status = "Ready"
        self.status_label.set_text(status)
        self.turn_label.set_text(str(snapshot.turn))
        self.delivered_label.set_text(
            f"{snapshot.delivered_drones} / {snapshot.total_drones}"
        )
        self.active_label.set_text(str(snapshot.active_drones))
        self.moved_label.set_text(str(snapshot.moved_drones))
        self.transit_label.set_text(str(snapshot.in_transit_drones))
        self.waiting_label.set_text(str(snapshot.waiting_drones))
        self.movement_label.set_text(snapshot.last_movement)
        self.graph_view.set_content(
            self.renderer.render(simulation, self.controller.last_transitions)
        )
        self.movement_detail.set_content(self._movement_detail_markup())
        self.drone_manifest.set_content(self._drone_manifest_markup())

    def _movement_detail_markup(self) -> str:
        """Return an escaped table describing the latest turn."""
        if not self.controller.last_transitions:
            return (
                '<div class="visual-empty">No movement yet. Use Step to '
                'inspect one turn or Play for continuous animation.</div>'
            )
        rows = []
        for transition in self.controller.last_transitions:
            drone_id = html.escape(transition.drone_id)
            origin = html.escape(transition.origin.label)
            destination = html.escape(transition.destination.label)
            status = html.escape(transition.status)
            rows.append(
                '<tr><td><strong>'
                f'{drone_id}</strong></td><td>{origin}'
                '<span class="movement-arrow">→</span>'
                f'{destination}</td><td>{status}</td></tr>'
            )
        return (
            '<table class="visual-table"><thead><tr><th>Drone</th>'
            '<th>Movement</th><th>Meaning</th></tr></thead><tbody>'
            + "".join(rows)
            + "</tbody></table>"
        )

    def _drone_manifest_markup(self) -> str:
        """Return an escaped manifest of all current drone positions."""
        rows = []
        for drone_id, location, state in self.controller.drone_locations():
            safe_id = html.escape(drone_id)
            safe_location = html.escape(location.label)
            safe_state = html.escape(state)
            state_class = (
                "state-delivered"
                if state == "delivered"
                else "state-transit"
                if location.kind == "connection"
                else "state-active"
            )
            rows.append(
                f'<tr><td><strong>{safe_id}</strong></td>'
                f'<td>{safe_location}</td><td class="{state_class}">'
                f'{safe_state}</td></tr>'
            )
        return (
            '<table class="visual-table"><thead><tr><th>Drone</th>'
            '<th>Position</th><th>State</th></tr></thead><tbody>'
            + "".join(rows)
            + "</tbody></table>"
        )

    def _show_error(self, message: str) -> None:
        """Display a visible error instead of silently ignoring it."""
        self.status_label.set_text("Error")
        ui.notify(message, type="negative", close_button=True)

    @staticmethod
    def _map_label(map_name: str) -> str:
        """Convert a relative map path into a compact select label."""
        return map_name.removesuffix(".txt").replace("_", " ")


@ui.page("/")
def fly_in_page() -> None:
    """Create an isolated visual view for the connected browser client."""
    FlyInWebView()


def main(arguments: Sequence[str] | None = None) -> None:
    """Parse web-server options and run the browser interface."""
    global INITIAL_MAP, INITIAL_TURN
    parser = argparse.ArgumentParser(description="Fly-in browser visualizer")
    parser.add_argument("--map", default="map.txt")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--turn",
        type=int,
        default=0,
        help="start the visualization after this many simulated turns",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not open a browser automatically",
    )
    options = parser.parse_args(arguments)
    INITIAL_MAP = Path(options.map).resolve()
    if not INITIAL_MAP.is_file():
        parser.error(f"map file not found: {options.map}")
    if options.turn < 0:
        parser.error("turn must be zero or greater")
    INITIAL_TURN = options.turn
    ui.run(
        host=options.host,
        port=options.port,
        show=not options.no_open,
        reload=False,
        title="Fly-in Visualizer",
    )


if __name__ == "__main__":
    main()
