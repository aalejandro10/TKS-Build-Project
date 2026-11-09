# LHS 1140 b transit simulator.
import math
import pygame

# Values from my article and its sources.
PERIOD_DAYS = 24.73723
PLANET_RADIUS_KM = 11017.0
STAR_RADIUS_SOLAR = 0.2159
STAR_MASS_SOLAR = 0.1844
INCLINATION_DEGREES = 89.86
PUBLISHED_AXIS_AU = 0.0946

G = 6.67430e-11
AU_METRES = 149_597_870_700.0
SUN_RADIUS_KM = 695_700.0
SOLAR_MASS_KG = 1.98847e30
DAY_SECONDS = 86400.0

BACKGROUND = (15, 20, 30)
PANEL = (25, 33, 47)
PLOT = (12, 18, 28)
GRID = (48, 60, 78)
WHITE = (232, 237, 245)
GREY = (153, 166, 185)
BLUE = (77, 190, 230)
STAR = (255, 210, 110)
PLANET = (106, 151, 235)


def calculate_axis_au(period_days, star_mass_solar):
    # Use Kepler's third law and ignore the planet's small mass.
    period = period_days * DAY_SECONDS
    star_mass = star_mass_solar * SOLAR_MASS_KG
    axis_metres = (G * star_mass * period**2 / (4 * math.pi**2)) ** (1 / 3)
    return axis_metres / AU_METRES


# Calculate the orbit size with Kepler's third law.
SEMI_MAJOR_AU = calculate_axis_au(PERIOD_DAYS, STAR_MASS_SOLAR)
STAR_RADIUS_AU = STAR_RADIUS_SOLAR * SUN_RADIUS_KM / (AU_METRES / 1000)
PLANET_RADIUS_AU = PLANET_RADIUS_KM / (AU_METRES / 1000)
IMPACT_AU = SEMI_MAJOR_AU * math.cos(math.radians(INCLINATION_DEGREES))

OUTER_TRANSIT_DAYS = math.asin(
    math.sqrt((STAR_RADIUS_AU + PLANET_RADIUS_AU) ** 2 - IMPACT_AU**2)
    / SEMI_MAJOR_AU
) / (2 * math.pi / PERIOD_DAYS)

INNER_TRANSIT_DAYS = math.asin(
    math.sqrt((STAR_RADIUS_AU - PLANET_RADIUS_AU) ** 2 - IMPACT_AU**2)
    / SEMI_MAJOR_AU
) / (2 * math.pi / PERIOD_DAYS)


def phase_to_graph_position(time_from_transit):
    # Spread ingress and egress across more screen space.
    knots = [
        (-OUTER_TRANSIT_DAYS, 0.15),
        (-INNER_TRANSIT_DAYS, 0.32),
        (0.0, 0.50),
        (INNER_TRANSIT_DAYS, 0.68),
        (OUTER_TRANSIT_DAYS, 0.85),
    ]

    if time_from_transit < knots[0][0] or time_from_transit > knots[-1][0]:
        return None

    for (t1, x1), (t2, x2) in zip(knots, knots[1:]):
        if t1 <= time_from_transit <= t2:
            fraction = (time_from_transit - t1) / (t2 - t1)
            return x1 + fraction * (x2 - x1)

    return None


def graph_position_to_phase(position_in_orbit):
    # Map each graph dip back to its time around transit.
    knots = [
        (0.15, -OUTER_TRANSIT_DAYS),
        (0.32, -INNER_TRANSIT_DAYS),
        (0.50, 0.0),
        (0.68, INNER_TRANSIT_DAYS),
        (0.85, OUTER_TRANSIT_DAYS),
    ]

    for (x1, t1), (x2, t2) in zip(knots, knots[1:]):
        if x1 <= position_in_orbit <= x2:
            fraction = (position_in_orbit - x1) / (x2 - x1)
            return t1 + fraction * (t2 - t1)

    return None


def position(time_days):
    # Positive z points toward the observer.
    angle = 2 * math.pi * time_days / PERIOD_DAYS + math.pi / 2
    inclination = math.radians(INCLINATION_DEGREES)

    x = SEMI_MAJOR_AU * math.cos(angle)
    y = SEMI_MAJOR_AU * math.sin(angle) * math.cos(inclination)
    z = SEMI_MAJOR_AU * math.sin(angle) * math.sin(inclination)

    return x, y, z


def overlap_area(star_radius, planet_radius, distance):
    # Find the overlap between the star and planet as circles.
    if distance >= star_radius + planet_radius:
        return 0.0

    if distance <= abs(star_radius - planet_radius):
        return math.pi * min(star_radius, planet_radius) ** 2

    c1 = (distance**2 + star_radius**2 - planet_radius**2) / (
        2 * distance * star_radius
    )
    c2 = (distance**2 + planet_radius**2 - star_radius**2) / (
        2 * distance * planet_radius
    )

    root = max(
        0.0,
        (-distance + star_radius + planet_radius)
        * (distance + star_radius - planet_radius)
        * (distance - star_radius + planet_radius)
        * (distance + star_radius + planet_radius),
    )

    return (
        star_radius**2 * math.acos(max(-1.0, min(1.0, c1)))
        + planet_radius**2 * math.acos(max(-1.0, min(1.0, c2)))
        - 0.5 * math.sqrt(root)
    )


def relative_flux(time_days):
    # Calculate the star's brightness during the transit.
    x, y, z = position(time_days)

    if z <= 0:
        return 1.0

    star_radius = STAR_RADIUS_SOLAR * SUN_RADIUS_KM
    planet_radius = PLANET_RADIUS_KM
    separation = math.hypot(x, y) * AU_METRES / 1000
    blocked = overlap_area(star_radius, planet_radius, separation)

    return 1.0 - blocked / (math.pi * star_radius**2)


class Simulator:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("LHS 1140 b — Transit Simulator")

        self.screen = pygame.display.set_mode((1120, 760), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("Arial", 16)
        self.small = pygame.font.SysFont("Arial", 13)
        self.heading = pygame.font.SysFont("Arial", 21, bold=True)

        self.orbit_count = 1
        self.time_days = 0.0
        self.playing = True
        self.buttons = {}
        self.running = True

    def label(self, text, x, y, color=WHITE, font=None):
        image = (font or self.font).render(str(text), True, color)
        self.screen.blit(image, (int(x), int(y)))

    def panel(self, rect, title):
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        self.label(title, rect.x + 14, rect.y + 10, WHITE, self.heading)

    def button(self, key, text, rect):
        rect = pygame.Rect(rect)
        self.buttons[key] = rect

        pygame.draw.rect(self.screen, (39, 54, 73), rect, border_radius=5)
        pygame.draw.rect(self.screen, GRID, rect, 1, border_radius=5)

        image = self.font.render(text, True, WHITE)
        self.screen.blit(image, image.get_rect(center=rect.center))

    def draw_orbit(self, rect, top_view):
        pygame.draw.rect(self.screen, PLOT, rect, border_radius=5)

        center = rect.center
        pixels_per_au = min(rect.w, rect.h) * 0.39 / SEMI_MAJOR_AU

        pygame.draw.line(
            self.screen, GRID, (rect.left, center[1]), (rect.right, center[1])
        )
        pygame.draw.line(
            self.screen, GRID, (center[0], rect.top), (center[0], rect.bottom)
        )

        orbit_points = []

        for i in range(181):
            time_days = PERIOD_DAYS * i / 180
            x, y, z = position(time_days)

            # Put the side facing Earth at the bottom of the top view.
            horizontal, vertical = (x, -z) if top_view else (x, y)
            orbit_points.append(
                (
                    int(center[0] + horizontal * pixels_per_au),
                    int(center[1] - vertical * pixels_per_au),
                )
            )

        pygame.draw.lines(
            self.screen, (75, 91, 116), True, orbit_points, 1
        )

        star_pixels = max(24, int(STAR_RADIUS_AU * pixels_per_au))
        pygame.draw.circle(self.screen, STAR, center, star_pixels)

        x, y, z = position(self.time_days)
        horizontal, vertical = (x, -z) if top_view else (x, y)

        planet_center = (
            int(center[0] + horizontal * pixels_per_au),
            int(center[1] - vertical * pixels_per_au),
        )

        # Draw both bigger, but keep the planet much smaller than the star.
        planet_pixels = 4

        # Hide the planet only while it is behind the star's disc.
        behind_star = (
            not top_view
            and z < 0
            and math.hypot(x, y) < STAR_RADIUS_AU + PLANET_RADIUS_AU
        )

        if not behind_star:
            pygame.draw.circle(
                self.screen, PLANET, planet_center, planet_pixels
            )

        self.label(
            "0.0946 AU orbit",
            rect.x + 8,
            rect.bottom - 22,
            GREY,
            self.small,
        )

    def draw_lightcurve(self, rect):
        pygame.draw.rect(self.screen, PLOT, rect, border_radius=5)

        graph = pygame.Rect(
            rect.x + 48,
            rect.y + 24,
            rect.w - 60,
            rect.h - 55,
        )

        # Repeat one readable transit curve for each orbit.
        low = 1.0 - (
            (PLANET_RADIUS_KM / (STAR_RADIUS_SOLAR * SUN_RADIUS_KM)) ** 2
        ) * 1.3
        high = 1.001

        for i in range(5):
            y = graph.y + graph.h * i / 4
            pygame.draw.line(
                self.screen, GRID, (graph.x, y), (graph.right, y), 1
            )

            flux = high - (high - low) * i / 4
            self.label(
                f"{flux:.3f}",
                rect.x + 5,
                y - 8,
                GREY,
                self.small,
            )

        # Keep each transit wide enough to see in the graph.
        cache_key = (
            graph.x,
            graph.y,
            graph.width,
            graph.height,
            self.orbit_count,
        )

        if getattr(self, "curve_cache_key", None) != cache_key:
            points = []
            samples = 300 * self.orbit_count

            for i in range(samples):
                orbit_position = (i / (samples - 1)) * self.orbit_count
                orbit_index = min(
                    self.orbit_count - 1, int(orbit_position)
                )
                within_orbit = orbit_position - orbit_index
                phase = graph_position_to_phase(within_orbit)

                if phase is not None:
                    flux = relative_flux(phase)
                else:
                    flux = 1.0

                x = graph.x + graph.w * i / (samples - 1)
                y = graph.y + (
                    high - max(low, min(high, flux))
                ) / (high - low) * graph.h
                points.append((int(x), int(y)))

            self.curve_cache = points
            self.curve_cache_key = cache_key

        pygame.draw.lines(self.screen, BLUE, False, self.curve_cache, 2)

        # Show the marker during each transit.
        total_days = PERIOD_DAYS * self.orbit_count
        orbit_time = self.time_days % total_days
        orbit_index = min(
            self.orbit_count - 1, int(orbit_time / PERIOD_DAYS)
        )
        phase_days = orbit_time - orbit_index * PERIOD_DAYS

        if phase_days > PERIOD_DAYS / 2:
            phase_days -= PERIOD_DAYS

        within_orbit = phase_to_graph_position(phase_days)

        if within_orbit is not None:
            cursor_x = graph.x + (
                (orbit_index + within_orbit) / self.orbit_count * graph.w
            )
            pygame.draw.line(
                self.screen,
                WHITE,
                (int(cursor_x), graph.y),
                (int(cursor_x), graph.bottom),
                1,
            )

        for i in range(self.orbit_count + 1):
            tick_x = graph.x + i * graph.w / self.orbit_count

            pygame.draw.line(
                self.screen,
                GRID,
                (int(tick_x), graph.y),
                (int(tick_x), graph.bottom),
                1,
            )

            if i < self.orbit_count:
                self.label(
                    f"{i + 1}",
                    tick_x + graph.w / self.orbit_count / 2 - 4,
                    graph.bottom + 3,
                    GREY,
                    self.small,
                )

        self.label("Relative flux", rect.x + 6, rect.y + 5, GREY, self.small)
        self.label(
            "Orbit number · transits expanded for visibility",
            rect.x + 48,
            graph.bottom + 20,
            GREY,
            self.small,
        )

    def draw(self):
        self.buttons.clear()

        width, height = self.screen.get_size()
        self.screen.fill(BACKGROUND)

        self.label(
            "LHS 1140 b — EXOPLANET TRANSIT",
            20,
            16,
            WHITE,
            self.heading,
        )
        self.label(
            "A fixed-data model. Change only the number of orbits shown.",
            22,
            45,
            GREY,
            self.small,
        )

        self.panel(
            pygame.Rect(16, 74, width - 32, 70),
            "ORBIT COUNT",
        )

        self.button("minus", "−", pygame.Rect(205, 96, 38, 32))
        self.label(str(self.orbit_count), 258, 99, WHITE, self.heading)
        self.button("plus", "+", pygame.Rect(300, 96, 38, 32))
        self.button(
            "play",
            "Pause" if self.playing else "Play",
            pygame.Rect(width - 122, 96, 96, 32),
        )

        gap = 12
        top = 156
        plot_height = int(height * 0.45)

        left_width = int((width - 44) * 0.34)
        middle_width = left_width
        right_width = width - 32 - left_width - middle_width - 2 * gap

        left = pygame.Rect(16, top, left_width, plot_height)
        middle = pygame.Rect(
            left.right + gap, top, middle_width, plot_height
        )
        right = pygame.Rect(
            middle.right + gap, top, right_width, plot_height
        )

        self.panel(left, "Top view")
        self.panel(middle, "Front view")
        self.panel(right, "Transit lightcurve")

        self.draw_orbit(
            pygame.Rect(
                left.x + 10, left.y + 44, left.w - 20, left.h - 56
            ),
            True,
        )
        self.draw_orbit(
            pygame.Rect(
                middle.x + 10,
                middle.y + 44,
                middle.w - 20,
                middle.h - 56,
            ),
            False,
        )
        self.draw_lightcurve(
            pygame.Rect(
                right.x + 10,
                right.y + 44,
                right.w - 20,
                right.h - 56,
            )
        )

        info_y = top + plot_height + 12
        info = pygame.Rect(
            16,
            info_y,
            width - 32,
            max(130, height - info_y - 16),
        )
        self.panel(info, "Fixed system data")

        self.label(
            "Planet: LHS 1140 b    Star: LHS 1140    "
            f"Planet radius: {PLANET_RADIUS_KM:,.0f} km (1.73 Earth radii)",
            info.x + 16,
            info.y + 48,
            WHITE,
            self.font,
        )
        self.label(
            f"Period: {PERIOD_DAYS:.5f} days    "
            f"Semi-major axis: {SEMI_MAJOR_AU:.5f} AU "
            f"(published ≈ {PUBLISHED_AXIS_AU:.4f})    "
            f"Star mass: {STAR_MASS_SOLAR:.4f} solar masses    "
            f"Star radius: {STAR_RADIUS_SOLAR:.4f} solar radii",
            info.x + 16,
            info.y + 76,
            WHITE,
            self.font,
        )
        self.label(
            "Transit depth uses the actual radii. "
            "Drawn sizes are adjusted for visibility.",
            info.x + 16,
            info.y + 105,
            GREY,
            self.small,
        )

        pygame.display.flip()

    def run(self):
        while self.running:
            delta = self.clock.tick(60) / 1000

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(
                        (max(800, event.w), max(620, event.h)),
                        pygame.RESIZABLE,
                    )

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    for name, rect in self.buttons.items():
                        if rect.collidepoint(event.pos):
                            if name == "minus":
                                self.orbit_count = max(
                                    1, self.orbit_count - 1
                                )
                            elif name == "plus":
                                self.orbit_count = min(
                                    10, self.orbit_count + 1
                                )
                            elif name == "play":
                                self.playing = not self.playing

                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    self.playing = not self.playing

            if self.playing:
                duration = PERIOD_DAYS * self.orbit_count
                self.time_days = (
                    self.time_days + delta * PERIOD_DAYS / 8
                ) % duration

            self.draw()

        pygame.quit()


if __name__ == "__main__":
    Simulator().run()