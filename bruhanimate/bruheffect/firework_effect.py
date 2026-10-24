"""
Copyright 2023 Ethan Christensen

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import math
import random
from typing import List

from bruhcolor import bruhcolored as bc

from ..bruhutil.bruhffer import Buffer
from ..bruhutil.bruhtypes import (
    FireworkColorType,
    FireworkType,
    two_tone_colors,
    valid_firework_color_types,
    valid_firework_types,
)
from ._resize import raster
from .base_effect import BaseEffect
from .settings import FireworkSettings, validated_settings


class Particle:
    """
    Class representing a particle in a firework with optional trail effects.
    """

    def __init__(
        self,
        x: int,
        y: int,
        dx: float,
        dy: float,
        width: int,
        height: int,
        symbol: str = "*",
        life: int | None = None,
        trail_length: int = 0,
        *,
        rng: random.Random | None = None,
    ):
        """
        Initialize a particle with the given parameters.

        Args:
            x (int): The x position of the particle.
            y (int): The y position of the particle.
            dx (float): The horizontal velocity of the particle.
            dy (float): The vertical velocity of the particle.
            width (int): The width of the canvas or screen.
            height (int): The height of the canvas or screen.
            symbol (str, optional): The character that will be displayed to the screen. Defaults to "*".
            life (int, optional): How long this particle can live for (frames). Defaults to None.
            trail_length (int, optional): Length of the particle's trail. 0 means no trail. Defaults to 0.
            rng: Shared effect-local random stream, or a fresh stream when None.
        """
        self.rng = rng if rng is not None else random.Random()
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.width = width
        self.height = height
        self.life = life if life else self.rng.randint(8, 15)
        self.symbol = symbol

        # Trail-related attributes
        self.trail_length = trail_length
        self.trail = []  # Stores previous positions
        self.trail_symbols = [
            "·",
            "⋅",
            "∙",
            "°",
        ]  # Different symbols for trail fade effect

        # Initialize previous position (maintain backward compatibility)
        self.previous_x = x
        self.previous_y = y

    def update(self):
        """
        Function to update a particle and its parameters each frame.
        """
        # Store current position for trail if enabled
        if self.trail_length > 0:
            self.trail.append((self.x, self.y, self.symbol))
            # Keep trail at specified length
            if len(self.trail) > self.trail_length:
                self.trail.pop(0)

        # Update previous position (for backward compatibility)
        self.previous_x = self.x
        self.previous_y = self.y

        # Update current position
        self.x += self.dx
        self.y += self.dy
        self.dy += 0.05
        self.life -= 1

        # Flicker effect
        if self.rng.random() > 0.5:
            self.symbol = "*" if self.symbol == "." else "."

    def get_display_points(self):
        """
        Returns all points that should be displayed, including trails if enabled.

        Returns:
            list: List of tuples (x, y, symbol) for all points to display
        """
        points = [(self.x, self.y, self.symbol)]

        if self.trail_length > 0:
            # Add trail points with fading symbols
            trail_len = len(self.trail)
            for i, (trail_x, trail_y, _) in enumerate(reversed(self.trail)):
                # Adjust the fade effect based on trail position
                fade_factor = min(
                    i * len(self.trail_symbols) // trail_len,
                    len(self.trail_symbols) - 1,
                )
                symbol_index = len(self.trail_symbols) - fade_factor - 1
                points.append((trail_x, trail_y, self.trail_symbols[symbol_index]))

        return points

    def is_alive(self):
        """
        Whether or not the particle is still alive. A Particle is alive if it has life left and is within bounds.
        """
        return (
            self.life > 0
            and 0 <= int(self.x) < self.width
            and 0 <= int(self.y) < self.height
        )


class Firework:
    """
    The Firework class. Responsible for creating and updating fireworks.
    """

    def __init__(
        self,
        firework_type: FireworkType,
        height: int,
        width: int,
        firework_color_type: str | None = None,
        color_enabled: bool = False,
        allowed_firework_types: List[str] | None = None,
        *,
        rng: random.Random | None = None,
    ):
        """
        Initialize a Firework object.

        Args:
            firework_type (FireworkType): The type of firework this object should be. (eg. 'random', 'ring', 'snowflake').
            height (int): The height of the display area (generally the terminal window).
            width (int): The width of the display area (generally the terminal window).
            firework_color_type (str, optional): The type of color to be applied to the Firework. Defaults to None.
            color_enabled (bool, optional): Whether of not the Firework should have color. Defaults to False.
            allowed_firework_types (List[str], optional): List of allowed firework types in the instance firework_type is 'random'. Defaults to None.
            rng: Stream shared with spawned particles; None creates a fresh one.
        """
        self.rng = rng if rng is not None else random.Random()
        self.width = width
        self.height = height
        self.x = self.rng.randint(0, self.width - 1)
        self.y = height - 1
        self.previous_x = self.x
        self.previous_y = self.y
        max_peak = self.height // 2
        self.peak = self.rng.randint(min(5, max_peak), max_peak)
        self.exploded = False
        self.particles = []
        self.allowed_fire_work_types = allowed_firework_types or valid_firework_types
        self.explosion_type = (
            firework_type
            if (firework_type != "random" and firework_type in valid_firework_types)
            else self.rng.choice(self.allowed_fire_work_types)
        )
        self.clear_particles = []
        self.caught_last_trail = False
        self.speed = 3
        self.firework_color_type = firework_color_type
        self.colors = self.get_colors()
        self.color_enabled = color_enabled

        self.trajectory_type = self.rng.choice(["straight", "arc", "zigzag"])
        self.angle = self.rng.uniform(-0.5, 0.5)  # Angle for non-straight trajectories
        self.arc_direction = self.rng.choice([-1, 1])  # Direction of arc curve
        self.zigzag_phase = 0  # For zigzag pattern
        self.zigzag_amplitude = self.rng.uniform(0.2, 0.5)  # Width of zigzag

    def update(self):
        """
        Function to update the firework's state.
        If the firework hasn't exploded yet, then it's trail needs to be advanced.
        If the firework has exploded, then we need to update the particles that make
        up the firework.
        """
        if not self.exploded:
            # Store previous position
            self.previous_x = self.x
            self.previous_y = self.y

            # Update position based on trajectory type
            if self.trajectory_type == "straight":
                self.move_straight()
            elif self.trajectory_type == "arc":
                self.move_arc()
            else:  # zigzag
                self.move_zigzag()

            # Check if reached peak
            if self.y <= self.peak:
                self.exploded = True
                self.create_particles()
        else:
            # Update particles
            for particle in self.particles:
                particle.update()
            # Remove dead particles
            for p in self.particles:
                if not p.is_alive():
                    self.clear_particles.append(p)

            self.particles = [p for p in self.particles if p.is_alive()]

    def move_straight(self):
        """
        Function to move the firework trail straight up and down.
        """
        # Move upward with slight angle
        self.y -= self.speed
        self.x += math.sin(self.angle) * self.speed * 0.5

    def move_arc(self):
        """
        Function to move the firework trail in an arcing trajectory.
        """
        # Create arcing trajectory
        progress = (self.height - self.y) / (self.height - self.peak)
        arc_offset = math.sin(progress * math.pi) * 2.0
        self.y -= self.speed
        self.x += self.arc_direction * arc_offset * 0.2

    def move_zigzag(self):
        """
        Function to move the firework trail in a zigzag pattern.
        """
        # Create zigzag pattern
        self.zigzag_phase += 0.2
        self.y -= self.speed
        self.x += math.sin(self.zigzag_phase) * self.zigzag_amplitude

    def create_particles(self):
        """
        Function to create the particles for the firework after it has
        reached it's peak. It is determined by the firework_type parameter.
        """
        if self.explosion_type == "circular":
            self.circular_explosion()
        elif self.explosion_type == "ring":
            self.ring_explosion()
        elif self.explosion_type == "starburst":
            self.starburst_explosion()
        elif self.explosion_type == "cone":
            self.cone_explosion()
        elif self.explosion_type == "spiral":
            self.spiral_explosion()
        elif self.explosion_type == "wave":
            self.wave_explosion()
        elif self.explosion_type == "burst":
            self.burst_explosion()
        elif self.explosion_type == "cross":
            self.cross_explosion()
        elif self.explosion_type == "flower":
            self.flower_explosion()
        elif self.explosion_type == "doublering":
            self.double_ring_explosion()
        elif self.explosion_type == "heart":
            self.heart_explosion()
        elif self.explosion_type == "star":
            self.star_explosion()
        elif self.explosion_type == "fireball":
            self.fireball_explosion()
        elif self.explosion_type == "diamond":
            self.diamond_explosion()
        elif self.explosion_type == "shockwave":
            self.burst_with_shockwave_explosion()
        elif self.explosion_type == "snowflake":
            self.snowflake_explosion()
        elif self.explosion_type == "cluster":
            self.cluster_explosion()
        elif self.explosion_type == "comet":
            self.comet_tail_explosion()
        elif self.explosion_type == "willow":
            self.willow_explosion()
        elif self.explosion_type == "dna":
            self.dna_explosion()
        elif self.explosion_type == "infinity":
            self.infinity_explosion()
        elif self.explosion_type == "galaxy":
            self.galaxy_explosion()
        elif self.explosion_type == "phoenix":
            self.phoenix_explosion()
        elif self.explosion_type == "fountain":
            self.fountain_explosion()
        elif self.explosion_type == "butterfly":
            self.butterfly_explosion()
        elif self.explosion_type == "dragon":
            self.dragon_explosion()
        elif self.explosion_type == "tornado":
            self.tornado_explosion()
        elif self.explosion_type == "matrix":
            self.matrix_explosion()
        elif self.explosion_type == "portal":
            self.portal_explosion()
        elif self.explosion_type == "fractal":
            self.fractal_tree_explosion()
        elif self.explosion_type == "tessellation":
            self.tessellation_explosion()
        elif self.explosion_type == "quantum":
            self.quantum_explosion()
        elif self.explosion_type == "mandelbrot":
            self.mandelbrot_explosion()
        elif self.explosion_type == "hypercube":
            self.hypercube_explosion()
        elif self.explosion_type == "chaos":
            self.chaos_theory_explosion()
        elif self.explosion_type == "timewarp":
            self.time_warp_explosion()
        elif self.explosion_type == "interdimensional":
            self.interdimensional_portal_explosion()
        elif self.explosion_type == "blackhole":
            self.black_hole_singularity()
        elif self.explosion_type == "mtheory":
            self.m_theory_explosion()
        elif self.explosion_type == "realitywarp":
            self.reality_warping_tessellation()
        elif self.explosion_type == "noneuclidean":
            self.non_euclidean_explosion()
        elif self.explosion_type == "cosmicstring":
            self.cosmic_string_explosion()
        elif self.explosion_type == "fancytrailburst":
            self.fancy_trail_burst_explosion()

    def circular_explosion(self):
        """
        Creates a circular explosion effect.
        """
        for _ in range(30):
            angle = self.rng.uniform(0, 2 * math.pi)
            speed = self.rng.uniform(0.5, 1.5)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def ring_explosion(self):
        """
        Creates a ring explosion effect.
        """
        for angle in range(0, 360, 12):  # Ring pattern with evenly spaced particles
            rad = math.radians(angle)
            dx = math.cos(rad)
            dy = math.sin(rad)
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def starburst_explosion(self):
        """
        Creates a starburst explosion effect.
        """
        for angle in range(
            0, 360, 45
        ):  # Starburst with particles in specific directions
            rad = math.radians(angle)
            speed = self.rng.uniform(1, 1.5)
            dx = math.cos(rad) * speed
            dy = math.sin(rad) * speed
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def cone_explosion(self):
        """
        Creates a cone explosion effect.
        """
        for _ in range(20):
            angle = self.rng.uniform(
                -math.pi / 6, math.pi / 6
            )  # Narrow range for cone shape
            speed = self.rng.uniform(0.5, 1.5)
            dx = math.cos(angle) * speed
            dy = -abs(math.sin(angle) * speed)  # Force particles upward
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def spiral_explosion(self):
        """
        Creates a spiral explosion effect.
        """
        for i in range(20):
            angle = i * 0.3  # Gradually increasing angle for spiral effect
            speed = 0.1 * i  # Particles spread out as the spiral grows
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def wave_explosion(self):
        """
        Creates a wave explosion effect.
        """
        for i in range(30):
            angle = i * 0.2  # Slightly increase angle for wave effect
            speed = self.rng.uniform(0.5, 1.0)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed * 0.5  # Particles move slower upward
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def burst_explosion(self):
        """
        Creates a burst explosion effect.
        """
        for _ in range(20):
            angle = self.rng.uniform(0, 2 * math.pi)  # Random angles for burst
            speed = self.rng.uniform(0.5, 1.5)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )
        # Particles gradually fall downward after a burst
        for particle in self.particles:
            particle.dy += 0.5  # Increase downward velocity

    def cross_explosion(self):
        """
        Creates a cross explosion effect.
        """
        for angle in [0, 90, 180, 270]:  # Particles in cross directions
            rad = math.radians(angle)
            speed = self.rng.uniform(0.5, 1.5)
            dx = math.cos(rad) * speed
            dy = math.sin(rad) * speed
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def flower_explosion(self):
        """
        Creates a flower explosion effect.
        """
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            speed = self.rng.uniform(0.5, 1.0)
            dx = math.cos(rad) * speed
            dy = math.sin(rad) * speed
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )
            # Add smaller "petal" particles around each main particle
            for petal_angle in [-0.1, 0.1]:
                dx_petal = math.cos(rad + petal_angle) * (speed * 0.7)
                dy_petal = math.sin(rad + petal_angle) * (speed * 0.7)
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        dx_petal,
                        dy_petal,
                        self.width,
                        self.height,
                        rng=self.rng,
                    )
                )

    def double_ring_explosion(self):
        """
        Creates a double ring explosion effect.
        """
        for radius_multiplier in [0.8, 1.2]:  # Two rings at slightly different radii
            for angle in range(0, 360, 15):
                rad = math.radians(angle)
                speed = 1.0 * radius_multiplier
                dx = math.cos(rad) * speed
                dy = math.sin(rad) * speed
                self.particles.append(
                    Particle(
                        self.x, self.y, dx, dy, self.width, self.height, rng=self.rng
                    )
                )

    def heart_explosion(self):
        """
        Creates a heart explosion effect.
        """
        for t in range(0, 360, 10):  # Parametric heart shape
            rad = math.radians(t)
            dx = 16 * math.sin(rad) ** 3 * 0.1
            dy = (
                -(
                    13 * math.cos(rad)
                    - 5 * math.cos(2 * rad)
                    - 2 * math.cos(3 * rad)
                    - math.cos(4 * rad)
                )
                * 0.05
            )
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def star_explosion(self):
        """
        Creates a star explosion effect.
        """
        for i in range(5):  # 5-point star
            angle = i * 2 * math.pi / 5
            dx = math.cos(angle) * 1.5
            dy = math.sin(angle) * 1.5
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )
            # Add particles in opposite direction for a sharper effect
            self.particles.append(
                Particle(
                    self.x, self.y, -dx, -dy, self.width, self.height, rng=self.rng
                )
            )

    def fireball_explosion(self):
        """
        Creates a fireball explosion effect.
        """
        for _ in range(50):  # Dense number of particles
            angle = self.rng.uniform(0, 2 * math.pi)
            speed = self.rng.uniform(0.2, 1.5)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def diamond_explosion(self):
        """
        Creates a diamond explosion effect.
        """
        for angle in [45, 135, 225, 315]:  # Four main directions for diamond points
            rad = math.radians(angle)
            dx = math.cos(rad) * 1.5
            dy = math.sin(rad) * 1.5
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )
            # Add smaller particles near each main point for a thicker diamond shape
            for offset in [-0.1, 0.1]:
                dx_offset = math.cos(rad + offset) * 1.2
                dy_offset = math.sin(rad + offset) * 1.2
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        dx_offset,
                        dy_offset,
                        self.width,
                        self.height,
                        rng=self.rng,
                    )
                )

    def burst_with_shockwave_explosion(self):
        """
        Creates a burst with shockwave explosion effect.
        """
        # Main burst particles
        for angle in range(0, 360, 20):
            rad = math.radians(angle)
            speed = self.rng.uniform(0.8, 1.2)
            dx = math.cos(rad) * speed
            dy = math.sin(rad) * speed
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

        # Shockwave particles in a ring around the burst
        for angle in range(0, 360, 5):
            rad = math.radians(angle)
            dx = math.cos(rad) * 1.5
            dy = math.sin(rad) * 1.5
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    dx * 0.5,
                    dy * 0.5,
                    self.width,
                    self.height,
                    life=5,
                    rng=self.rng,
                )
            )  # Short lifespan for shockwave

    def snowflake_explosion(self):
        """
        Creates a snowflake explosion effect.
        """
        for angle in range(0, 360, 60):  # Six main directions
            rad = math.radians(angle)
            speed = self.rng.uniform(0.8, 1.0)
            dx = math.cos(rad) * speed
            dy = math.sin(rad) * speed
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

            # Small branches off each main point for the snowflake effect
            for branch_angle in [-15, 15]:  # Offset angles for branches
                rad_branch = rad + math.radians(branch_angle)
                dx_branch = math.cos(rad_branch) * (speed * 0.6)
                dy_branch = math.sin(rad_branch) * (speed * 0.6)
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        dx_branch,
                        dy_branch,
                        self.width,
                        self.height,
                        rng=self.rng,
                    )
                )

    def cluster_explosion(self):
        """
        Creates a cluster explosion effect with particles moving in different directions
        """
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            speed = 1.2
            dx = math.cos(rad) * speed
            dy = math.sin(rad) * speed
            main_particle = Particle(
                self.x, self.y, dx, dy, self.width, self.height, rng=self.rng
            )
            self.particles.append(main_particle)

            # Surround each main particle with smaller "cluster" particles
            for _ in range(6):
                offset_dx = dx + self.rng.uniform(-0.2, 0.2)
                offset_dy = dy + self.rng.uniform(-0.2, 0.2)
                self.particles.append(
                    Particle(
                        self.x + offset_dx,
                        self.y + offset_dy,
                        offset_dx * 0.5,
                        offset_dy * 0.5,
                        self.width,
                        self.height,
                        rng=self.rng,
                    )
                )

    def comet_tail_explosion(self):
        """
        Creates a comet tail explosion effect with particles following a comet-like path
        """
        # Main comet direction
        comet_angle = self.rng.choice(
            [45, 135, 225, 315]
        )  # Random diagonal angle for comet
        rad = math.radians(comet_angle)
        speed = 1.5
        main_dx = math.cos(rad) * speed
        main_dy = math.sin(rad) * speed

        for i in range(8):  # Comet particles along the main direction
            trail_dx = main_dx * (1 - i * 0.1)
            trail_dy = main_dy * (1 - i * 0.1)
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    trail_dx,
                    trail_dy,
                    self.width,
                    self.height,
                    rng=self.rng,
                )
            )

        # Small trailing particles
        for i in range(1, 5):
            trail_dx = main_dx * 0.3
            trail_dy = main_dy * 0.3
            self.particles.append(
                Particle(
                    self.x - trail_dx * i,
                    self.y - trail_dy * i,
                    trail_dx * 0.5,
                    trail_dy * 0.5,
                    self.width,
                    self.height,
                    rng=self.rng,
                )
            )

    def willow_explosion(self):
        """
        Creates a willow explosion effect with multiple branches extending from the center
        """
        num_arms = 10  # Number of branches in the willow effect
        angle_offset = 70  # Constrain angle range to mostly horizontal

        for i in range(num_arms):
            # Each arm has an angle mostly to the sides (slightly up or down)
            angle = (
                self.rng.uniform(-angle_offset, angle_offset)
                if i < num_arms / 2
                else self.rng.uniform(180 - angle_offset, 180 + angle_offset)
            )
            rad = math.radians(angle)
            initial_speed = self.rng.uniform(0.5, 1.0)

            # Calculate initial movement in a mostly horizontal direction
            dx = math.cos(rad) * initial_speed
            dy = (
                math.sin(rad) * initial_speed * 0.3
            )  # Smaller upward component for the drooping effect

            # Main particle at the start of each "arm"
            main_particle = Particle(
                self.x, self.y, dx, dy, self.width, self.height, life=25, rng=self.rng
            )
            self.particles.append(main_particle)

            # Trailing particles along each arm, curving downwards like branches
            for j in range(1, 6):
                # Reduce horizontal speed gradually, add downward pull for the arc
                arc_dx = dx * (
                    1 - j * 0.1
                )  # Slightly reduce horizontal speed over time
                arc_dy = dy + j * 0.1  # Increase downward speed to mimic gravity
                trail_particle = Particle(
                    self.x,
                    self.y,
                    arc_dx,
                    arc_dy,
                    self.width,
                    self.height,
                    life=25 - j * 8,
                    rng=self.rng,
                )
                self.particles.append(trail_particle)

    def dna_explosion(self):
        """
        Creates a double helix pattern resembling DNA structure
        """
        num_points = 30
        radius = 1.0
        vertical_stretch = 0.5

        for i in range(num_points):
            t = (i / num_points) * 4 * math.pi  # Two complete rotations

            # First strand
            dx1 = math.cos(t) * radius
            dy1 = -vertical_stretch * t  # Negative for upward movement
            self.particles.append(
                Particle(
                    self.x, self.y, dx1, dy1, self.width, self.height, rng=self.rng
                )
            )

            # Second strand (offset by pi)
            dx2 = math.cos(t + math.pi) * radius
            dy2 = -vertical_stretch * t
            self.particles.append(
                Particle(
                    self.x, self.y, dx2, dy2, self.width, self.height, rng=self.rng
                )
            )

            # "Bridges" between strands (occasional connectors)
            if i % 4 == 0:
                dx_bridge = (dx1 + dx2) / 2
                dy_bridge = dy1
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        dx_bridge,
                        dy_bridge,
                        self.width,
                        self.height,
                        symbol="-",
                        rng=self.rng,
                    )
                )

    def infinity_explosion(self):
        """
        Creates an infinity symbol (∞) pattern
        """
        num_points = 40
        size = 1.2

        for i in range(num_points):
            t = (i / num_points) * 2 * math.pi

            # Parametric equations for infinity symbol
            dx = size * math.cos(t) / (1 + math.sin(t) ** 2)
            dy = size * math.sin(t) * math.cos(t) / (1 + math.sin(t) ** 2)

            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

    def galaxy_explosion(self):
        """
        Creates a spiral galaxy pattern with arms and central bulge
        """
        # Central bulge
        for _ in range(20):
            angle = self.rng.uniform(0, 2 * math.pi)
            speed = self.rng.uniform(0.2, 0.5)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    dx,
                    dy,
                    self.width,
                    self.height,
                    symbol="·",
                    rng=self.rng,
                )
            )

        # Spiral arms
        arms = 2
        for arm in range(arms):
            start_angle = (2 * math.pi * arm) / arms
            for i in range(30):
                radius = 0.1 + (i * 0.05)
                angle = start_angle + (i * 0.3)
                dx = math.cos(angle) * radius
                dy = math.sin(angle) * radius
                self.particles.append(
                    Particle(
                        self.x, self.y, dx, dy, self.width, self.height, rng=self.rng
                    )
                )

    def phoenix_explosion(self):
        """
        Creates a rising phoenix pattern with wings and tail
        """
        # Central rising column
        for i in range(10):
            dy = -1.0 - (i * 0.1)  # Upward movement
            dx = self.rng.uniform(-0.2, 0.2)
            self.particles.append(
                Particle(self.x, self.y, dx, dy, self.width, self.height, rng=self.rng)
            )

        # Wings
        wing_span = 15
        for i in range(wing_span):
            # Left wing
            angle_left = math.radians(150 - (i * 4))  # Sweep from 150° to 90°
            dx_left = math.cos(angle_left) * (i * 0.1)
            dy_left = math.sin(angle_left) * (i * 0.1)
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    dx_left,
                    dy_left,
                    self.width,
                    self.height,
                    rng=self.rng,
                )
            )

            # Right wing
            angle_right = math.radians(30 + (i * 4))  # Sweep from 30° to 90°
            dx_right = math.cos(angle_right) * (i * 0.1)
            dy_right = math.sin(angle_right) * (i * 0.1)
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    dx_right,
                    dy_right,
                    self.width,
                    self.height,
                    rng=self.rng,
                )
            )

        # Tail feathers
        for i in range(5):
            angle = math.radians(270 + self.rng.uniform(-30, 30))
            speed = 0.5 + (i * 0.1)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    dx,
                    dy,
                    self.width,
                    self.height,
                    symbol="~",
                    rng=self.rng,
                )
            )

    def fountain_explosion(self):
        """
        Creates an upward-shooting fountain pattern with cascading particles
        """
        num_streams = 5
        particles_per_stream = 8

        for stream in range(num_streams):
            base_angle = -90 + self.rng.uniform(-15, 15)  # Mostly upward
            base_speed = self.rng.uniform(1.0, 1.5)

            for i in range(particles_per_stream):
                angle = math.radians(base_angle)
                speed = base_speed - (
                    i * 0.1
                )  # Particles get slower toward end of stream

                dx = math.cos(angle) * speed
                dy = math.sin(angle) * speed

                # Add some slight random variation to each particle
                dx += self.rng.uniform(-0.1, 0.1)
                dy += self.rng.uniform(-0.1, 0.1)

                particle = Particle(
                    self.x,
                    self.y,
                    dx,
                    dy,
                    self.width,
                    self.height,
                    symbol=":" if i < particles_per_stream // 2 else ".",
                    life=20 - i,  # Particles at end of stream die sooner
                    rng=self.rng,
                )
                self.particles.append(particle)

    def butterfly_explosion(self):
        """
        Creates a butterfly pattern with wings that flutter
        """
        # Wing shape parameters
        wing_points = 20
        flutter_speed = 0.2

        for i in range(wing_points):
            t = (i / wing_points) * 2 * math.pi

            # Parametric equations for wing shape (modified heart curve)
            base_dx = math.sin(t) * (math.exp(math.cos(t)) - 2 * math.cos(4 * t))
            base_dy = math.cos(t) * (math.exp(math.cos(t)) - 2 * math.cos(4 * t))

            # Create left and right wings with flutter effect
            for side in [-1, 1]:  # Left and right wings
                dx = base_dx * side * 0.3
                dy = base_dy * 0.3

                # Add flutter movement
                dx += math.sin(t * flutter_speed) * 0.1

                particle = Particle(
                    self.x,
                    self.y,
                    dx,
                    dy,
                    self.width,
                    self.height,
                    symbol="·" if i % 2 == 0 else "*",
                    life=self.rng.randint(15, 25),
                    rng=self.rng,
                )
                self.particles.append(particle)

            # Add body particles
            if i < 5:
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        0,
                        i * 0.1,
                        self.width,
                        self.height,
                        symbol="█",
                        rng=self.rng,
                    )
                )

    def dragon_explosion(self):
        """
        Creates a dragon shape with body, wings, and fire breath
        """
        # Body
        body_length = 15
        for i in range(body_length):
            angle = math.radians(self.rng.uniform(-10, 10))  # Slight wiggle
            dx = math.cos(angle) * 0.3
            dy = -0.5 + (i * 0.05)  # Curves upward
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    dx,
                    dy,
                    self.width,
                    self.height,
                    symbol="▲",
                    life=20,
                    rng=self.rng,
                )
            )

        # Wings
        wing_span = 12
        for i in range(wing_span):
            # Left and right wings
            for side in [-1, 1]:
                angle = math.radians(45 * side)
                dx = math.cos(angle) * (i * 0.15) * side
                dy = math.sin(angle) * (i * 0.1) - 0.5
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        dx,
                        dy,
                        self.width,
                        self.height,
                        symbol="*",
                        life=15,
                        rng=self.rng,
                    )
                )

        # Fire breath
        breath_particles = 20
        for i in range(breath_particles):
            angle = math.radians(self.rng.uniform(-30, 30))
            speed = self.rng.uniform(1.0, 2.0)
            dx = math.cos(angle) * speed
            dy = -math.sin(angle) * speed  # Upward fire breath
            symbol = self.rng.choice(["^", "*", "●"])
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    dx,
                    dy,
                    self.width,
                    self.height,
                    symbol=symbol,
                    life=10,
                    rng=self.rng,
                )
            )

    def tornado_explosion(self):
        """
        Creates a spinning tornado effect that grows wider at the top
        """
        height_layers = 15
        base_radius = 0.2

        for layer in range(height_layers):
            radius = base_radius + (layer * 0.1)  # Gets wider as it goes up
            particles_in_layer = int(6 + layer * 1.5)  # More particles in higher layers

            for p in range(particles_in_layer):
                angle = (p / particles_in_layer) * 2 * math.pi
                # Add spin effect
                angle += layer * 0.5

                dx = math.cos(angle) * radius
                dy = -1 + (layer * 0.1)  # Upward movement, slowing at top

                # Vary the symbols based on position
                symbol = "●" if layer < 3 else ("*" if layer < 10 else "·")

                particle = Particle(
                    self.x,
                    self.y,
                    dx,
                    dy,
                    self.width,
                    self.height,
                    symbol=symbol,
                    life=20 - layer,
                    rng=self.rng,
                )
                self.particles.append(particle)

    def matrix_explosion(self):
        """
        Creates a Matrix-style digital rain effect
        """
        num_streams = 15
        chars_per_stream = 8

        for stream in range(num_streams):
            # Calculate stream position
            angle = self.rng.uniform(0, 2 * math.pi)
            distance = self.rng.uniform(0.5, 2.0)
            base_dx = math.cos(angle) * distance
            base_dy = math.sin(angle) * distance

            for i in range(chars_per_stream):
                # Delay each character in stream
                dx = base_dx
                dy = base_dy + (i * 0.15)

                # Use Matrix-like symbols
                symbol = self.rng.choice(["0", "1", "█", "▀", "▄", "■", "░", "▒", "▓"])

                # Particles later in stream die sooner
                life = 20 - i

                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        dx,
                        dy,
                        self.width,
                        self.height,
                        symbol=symbol,
                        life=life,
                        rng=self.rng,
                    )
                )

    def portal_explosion(self):
        """
        Creates two connected portals with particles flowing between them
        """
        # Portal parameters
        portal_radius = 1.2
        num_particles = 50

        # Create two portal rings
        for portal in range(2):
            angle_offset = math.pi * portal  # Second portal on opposite side
            distance = 2.0  # Distance between portals

            # Portal position
            portal_x = math.cos(angle_offset) * distance
            portal_y = math.sin(angle_offset) * distance

            # Create portal ring
            for i in range(12):
                angle = (i / 12) * 2 * math.pi
                dx = portal_x + math.cos(angle) * portal_radius
                dy = portal_y + math.sin(angle) * portal_radius

                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        dx * 0.2,
                        dy * 0.2,
                        self.width,
                        self.height,
                        symbol="O",
                        life=25,
                        rng=self.rng,
                    )
                )

        # Particles flowing between portals
        for _ in range(num_particles):
            t = self.rng.uniform(0, 1)  # Position along path

            # Curved path between portals
            dx = math.cos(t * math.pi * 2) * portal_radius
            dy = math.sin(t * math.pi * 2) * portal_radius

            # Add some randomness to path
            dx += self.rng.uniform(-0.2, 0.2)
            dy += self.rng.uniform(-0.2, 0.2)

            symbol = self.rng.choice(["*", "·", "•", "+"])
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    dx * 0.3,
                    dy * 0.3,
                    self.width,
                    self.height,
                    symbol=symbol,
                    life=10,
                    rng=self.rng,
                )
            )

    def fractal_tree_explosion(self):
        """
        Creates a fractal tree pattern that branches out recursively
        """

        def add_branch(x, y, angle, depth, speed):
            if depth <= 0:
                return

            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed
            self.particles.append(
                Particle(x, y, dx, dy, self.width, self.height, rng=self.rng)
            )

            # Branch angles and reduced speed for sub-branches
            new_speed = speed * 0.7
            add_branch(x, y, angle - 0.5, depth - 1, new_speed)  # Left branch
            add_branch(x, y, angle + 0.5, depth - 1, new_speed)  # Right branch

        # Create initial branches
        for angle in range(0, 360, 45):
            add_branch(self.x, self.y, math.radians(angle), 4, 1.2)

    def tessellation_explosion(self):
        """
        Creates an Islamic geometric pattern-inspired explosion
        """
        num_layers = 3
        points_per_layer = 8

        for layer in range(num_layers):
            radius = 0.8 + layer * 0.4
            # Create regular polygon vertices
            for i in range(points_per_layer):
                base_angle = (2 * math.pi * i / points_per_layer) + (
                    layer * math.pi / points_per_layer
                )

                # Main point
                dx = math.cos(base_angle) * radius
                dy = math.sin(base_angle) * radius
                self.particles.append(
                    Particle(
                        self.x, self.y, dx, dy, self.width, self.height, rng=self.rng
                    )
                )

                # Connect to adjacent points with intermediate particles
                base_angle + (math.pi / points_per_layer)
                steps = 3
                for step in range(steps):
                    t = step / steps
                    dx = (
                        math.cos(base_angle + t * (math.pi / points_per_layer)) * radius
                    )
                    dy = (
                        math.sin(base_angle + t * (math.pi / points_per_layer)) * radius
                    )
                    self.particles.append(
                        Particle(
                            self.x,
                            self.y,
                            dx * 0.8,
                            dy * 0.8,
                            self.width,
                            self.height,
                            rng=self.rng,
                        )
                    )

    def quantum_explosion(self):
        """
        Creates a quantum probability cloud-like pattern with orbital shells
        """
        shells = 4
        electrons_per_shell = 8

        for shell in range(shells):
            radius = 0.5 + shell * 0.3
            for electron in range(electrons_per_shell):
                # Base orbital motion
                angle = 2 * math.pi * electron / electrons_per_shell

                # Add quantum uncertainty
                for uncertainty in range(3):
                    uncertain_radius = radius + self.rng.uniform(-0.1, 0.1)
                    uncertain_angle = angle + self.rng.uniform(-0.2, 0.2)

                    dx = math.cos(uncertain_angle) * uncertain_radius
                    dy = math.sin(uncertain_angle) * uncertain_radius

                    # Add some orbital velocity
                    orbital_dx = -dy * 0.3
                    orbital_dy = dx * 0.3

                    self.particles.append(
                        Particle(
                            self.x,
                            self.y,
                            dx + orbital_dx,
                            dy + orbital_dy,
                            self.width,
                            self.height,
                            rng=self.rng,
                        )
                    )

    def mandelbrot_explosion(self):
        """
        Creates an explosion pattern inspired by the Mandelbrot set
        """
        points = 40
        max_iterations = 3

        for i in range(points):
            angle = 2 * math.pi * i / points
            # Generate points along cardioid and main bulb shapes
            for iteration in range(max_iterations):
                # Cardioid
                t = angle + iteration * math.pi / 6
                r = 0.5 * (1 - math.cos(t))
                x = r * math.cos(t)
                y = r * math.sin(t)

                # Transform to velocity
                speed = 1.0 - (iteration * 0.2)
                dx = x * speed
                dy = y * speed

                self.particles.append(
                    Particle(
                        self.x, self.y, dx, dy, self.width, self.height, rng=self.rng
                    )
                )

                # Main bulb
                r2 = 0.25 * math.sqrt(abs(math.cos(2 * t)))
                x2 = r2 * math.cos(t)
                y2 = r2 * math.sin(t)
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        x2 * speed,
                        y2 * speed,
                        self.width,
                        self.height,
                        rng=self.rng,
                    )
                )

    def hypercube_explosion(self):
        """
        Creates a 4D hypercube projection explosion pattern
        """

        # Generate 4D hypercube vertices
        def rotate4d(point, angle):
            x, y, z, w = point
            # Rotate in xw plane
            xr = x * math.cos(angle) - w * math.sin(angle)
            wr = x * math.sin(angle) + w * math.cos(angle)
            return (xr, y, z, wr)

        vertices = []
        for x in [-1, 1]:
            for y in [-1, 1]:
                for z in [-1, 1]:
                    for w in [-1, 1]:
                        vertices.append((x * 0.5, y * 0.5, z * 0.5, w * 0.5))

        # Project and create particles
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            for vertex in vertices:
                # Rotate in 4D
                rotated = rotate4d(vertex, rad)
                # Project to 2D
                factor = 1 / (2 - rotated[3])  # Perspective projection
                x = rotated[0] * factor
                y = rotated[1] * factor

                speed = self.rng.uniform(0.8, 1.2)
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        x * speed,
                        y * speed,
                        self.width,
                        self.height,
                        rng=self.rng,
                    )
                )

    def chaos_theory_explosion(self):
        """
        A completely chaotic explosion that uses strange attractors and randomness
        """
        num_particles = 50
        for _ in range(num_particles):
            # Create chaotic initial conditions
            angle = self.rng.uniform(0, math.tau)  # tau = 2π
            speed = self.rng.uniform(0.2, 2.0)

            # Add some Lorenz attractor-inspired chaos
            x_offset = math.sin(angle * 3) * math.cos(angle * 2)
            y_offset = math.cos(angle * 4) * math.sin(angle * 5)

            dx = (math.cos(angle) + x_offset) * speed
            dy = (math.sin(angle) + y_offset) * speed

            # Add multiple particles with slightly varying trajectories
            for i in range(3):
                chaos_dx = dx + self.rng.uniform(-0.3, 0.3) * (i + 1)
                chaos_dy = dy + self.rng.uniform(-0.3, 0.3) * (i + 1)
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        chaos_dx,
                        chaos_dy,
                        self.width,
                        self.height,
                        rng=self.rng,
                    )
                )

    def time_warp_explosion(self):
        """
        Creates particles that appear to move through time differently
        """
        num_timelines = 20
        for timeline in range(num_timelines):
            # Create a base particle trajectory
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(0.5, 1.5)

            # Time dilation factor
            time_factor = self.rng.uniform(0.1, 2.0)

            # Create particles moving at different "time speeds"
            dx = math.cos(angle) * speed * time_factor
            dy = math.sin(angle) * speed * time_factor

            # Add temporal echo particles
            num_echoes = 5
            for echo in range(num_echoes):
                echo_factor = math.sin(timeline + echo / num_echoes * math.pi)
                echo_dx = dx * echo_factor
                echo_dy = dy * echo_factor

                # Add some spacetime distortion
                distortion = math.sin(timeline * 0.1) * 0.5
                echo_dx += distortion * self.rng.uniform(-1, 1)
                echo_dy += distortion * self.rng.uniform(-1, 1)

                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        echo_dx,
                        echo_dy,
                        self.width,
                        self.height,
                        rng=self.rng,
                    )
                )

    def interdimensional_portal_explosion(self):
        """
        Creates a swirling portal effect that seems to connect different dimensions
        """
        num_dimensions = 5  # Number of "dimensional layers"
        particles_per_dimension = 20

        for dimension in range(num_dimensions):
            dimension_offset = dimension * math.pi / num_dimensions

            for i in range(particles_per_dimension):
                # Create spiral pattern for each dimension
                angle = (i / particles_per_dimension * math.tau) + dimension_offset
                radius = 0.1 + dimension * 0.3

                # Add interdimensional drift
                drift_x = math.sin(angle * 3) * 0.5
                drift_y = math.cos(angle * 2) * 0.5

                # Calculate base velocities
                dx = math.cos(angle) * radius + drift_x
                dy = math.sin(angle) * radius + drift_y

                # Add some dimensional instability
                instability = self.rng.uniform(-0.2, 0.2)
                dx += instability * math.sin(dimension_offset)
                dy += instability * math.cos(dimension_offset)

                # Create particles with dimensional effects
                for _ in range(3):
                    # Add quantum tunneling effect
                    tunnel_dx = dx + self.rng.gauss(0, 0.1) * (dimension + 1)
                    tunnel_dy = dy + self.rng.gauss(0, 0.1) * (dimension + 1)

                    self.particles.append(
                        Particle(
                            self.x,
                            self.y,
                            tunnel_dx,
                            tunnel_dy,
                            self.width,
                            self.height,
                            rng=self.rng,
                        )
                    )

    def black_hole_singularity(self):
        """
        Creates a black hole effect that warps space around it and emits Hawking radiation
        """
        num_particles = 60

        # Create infalling particles
        for i in range(num_particles):
            angle = self.rng.uniform(0, math.tau)
            distance = self.rng.uniform(0.1, 2.0)

            # Calculate gravitational effects
            gravitational_strength = 1 / (distance + 0.1)  # Prevent division by zero

            # Spiral motion towards center
            dx = math.cos(angle) * distance * gravitational_strength
            dy = math.sin(angle) * distance * gravitational_strength

            # Add relativistic frame dragging effect
            frame_drag = math.atan2(dy, dx) * 0.3
            dx += math.cos(frame_drag)
            dy += math.sin(frame_drag)

            # Hawking radiation (particles that escape)
            if self.rng.random() < 0.2:  # 20% chance of radiation
                radiation_speed = self.rng.uniform(1.5, 2.0)
                self.particles.append(
                    Particle(
                        self.x,
                        self.y,
                        dx * radiation_speed,
                        dy * radiation_speed,
                        self.width,
                        self.height,
                        rng=self.rng,
                    )
                )

            # Infalling particles
            self.particles.append(
                Particle(
                    self.x,
                    self.y,
                    -dx * 0.5,
                    -dy * 0.5,
                    self.width,
                    self.height,
                    rng=self.rng,
                )
            )

    def m_theory_explosion(self):
        """
        Creates patterns inspired by 11-dimensional M-theory with membrane interactions
        """
        dimensions = 11  # M-theory's 11 dimensions
        particles_per_dim = 8

        for d in range(dimensions):
            phase = d * math.tau / dimensions

            # Create brane-like structures in higher dimensions
            for i in range(particles_per_dim):
                # Complex dimensional mapping
                angle1 = i * math.tau / particles_per_dim + phase
                angle2 = angle1 * math.pi / 2

                # Project from higher dimensions
                for j in range(3):  # Create multiple projections
                    # Use hyperbolic functions for exotic spatial effects
                    dx = math.sinh(angle1) * math.cosh(angle2) * (0.5 + j * 0.2)
                    dy = math.cosh(angle1) * math.sinh(angle2) * (0.5 + j * 0.2)

                    # Add quantum fluctuations
                    dx += self.rng.gauss(0, 0.1) * math.sin(d)
                    dy += self.rng.gauss(0, 0.1) * math.cos(d)

                    self.particles.append(
                        Particle(
                            self.x,
                            self.y,
                            dx,
                            dy,
                            self.width,
                            self.height,
                            rng=self.rng,
                        )
                    )

    def reality_warping_tessellation(self):
        """
        Creates a pattern that seems to fold and unfold reality itself
        """

        def create_tessellation_point(angle, radius, iteration):
            # Create golden ratio-based spiral
            golden_ratio = 1.618033988749895
            spiral_angle = angle * golden_ratio

            # Calculate base position with reality-warping effects
            x = math.cos(spiral_angle) * radius * math.sin(iteration * 0.1)
            y = math.sin(spiral_angle) * radius * math.cos(iteration * 0.1)

            # Add reality distortion
            distortion = math.sin(iteration * 0.3) * 0.5
            x += distortion * math.cos(spiral_angle * 2)
            y += distortion * math.sin(spiral_angle * 3)

            return x, y

        layers = 5
        points_per_layer = 12

        for layer in range(layers):
            radius = 0.3 + layer * 0.3
            for i in range(points_per_layer):
                angle = i * math.tau / points_per_layer

                # Create multiple folded reality versions
                for fold in range(3):
                    x1, y1 = create_tessellation_point(angle, radius, layer + fold)
                    x2, y2 = create_tessellation_point(
                        angle + 0.1, radius, layer + fold
                    )

                    # Create particles that follow the folds
                    speed = self.rng.uniform(0.5, 1.5)
                    self.particles.append(
                        Particle(
                            self.x,
                            self.y,
                            x1 * speed,
                            y1 * speed,
                            self.width,
                            self.height,
                            rng=self.rng,
                        )
                    )
                    self.particles.append(
                        Particle(
                            self.x,
                            self.y,
                            x2 * speed,
                            y2 * speed,
                            self.width,
                            self.height,
                            rng=self.rng,
                        )
                    )

    def non_euclidean_explosion(self):
        """
        Creates patterns that follow non-Euclidean geometry rules
        """

        def hyperbolic_transform(x, y, curvature):
            # Apply hyperbolic transformation
            r = math.sqrt(x * x + y * y)
            if r == 0:
                return x, y

            # Poincaré disk model transformation
            factor = 2.0 / (1.0 + curvature * r * r)
            return x * factor, y * factor

        base_particles = 40

        for i in range(base_particles):
            angle = self.rng.uniform(0, math.tau)
            radius = self.rng.uniform(0.1, 1.0)

            # Create base movement
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius

            # Apply various non-Euclidean transformations
            for curvature in [0.5, 1.0, 1.5]:  # Different space curvatures
                # Transform coordinates
                dx, dy = hyperbolic_transform(x, y, curvature)

                # Add Möbius transformation
                complex_z = complex(dx, dy)
                mobius_z = (complex_z + 0.2) / (1 - 0.3 * complex_z)

                # Convert back to real coordinates with scaling
                final_dx = mobius_z.real * 0.5
                final_dy = mobius_z.imag * 0.5

                # Add some quantum uncertainty to the geometry
                for _ in range(2):
                    uncertainty_dx = final_dx + self.rng.gauss(0, 0.1)
                    uncertainty_dy = final_dy + self.rng.gauss(0, 0.1)
                    self.particles.append(
                        Particle(
                            self.x,
                            self.y,
                            uncertainty_dx,
                            uncertainty_dy,
                            self.width,
                            self.height,
                            rng=self.rng,
                        )
                    )

    def cosmic_string_explosion(self):
        """
        Creates patterns based on theoretical cosmic strings and topological defects
        """
        num_strings = 8
        points_per_string = 15

        for string in range(num_strings):
            # Create a base cosmic string
            string_angle = string * math.tau / num_strings
            string_tension = self.rng.uniform(0.5, 1.5)

            for point in range(points_per_string):
                # Calculate string oscillation
                t = point / points_per_string
                wave = math.sin(t * math.pi * 2 + string_angle)

                # Add string vibration modes
                for mode in range(3):
                    mode_angle = string_angle + wave * 0.3 * (mode + 1)
                    mode_radius = 0.3 + mode * 0.2

                    # Calculate base velocities with string tension
                    dx = math.cos(mode_angle) * mode_radius * string_tension
                    dy = math.sin(mode_angle) * mode_radius * string_tension

                    # Add quantum fluctuations along the string
                    fluctuation = self.rng.gauss(0, 0.1)
                    dx += fluctuation * math.sin(mode_angle)
                    dy += fluctuation * math.cos(mode_angle)

                    # Create particles with varying energies
                    for energy in range(2):
                        energy_factor = 1.0 + energy * 0.5
                        self.particles.append(
                            Particle(
                                self.x,
                                self.y,
                                dx * energy_factor,
                                dy * energy_factor,
                                self.width,
                                self.height,
                                rng=self.rng,
                            )
                        )

    def fancy_trail_burst_explosion(self):
        """
        Creates a more complex explosion with varying trail lengths and spiral motion
        """
        num_particles = self.rng.randint(8, 20)

        for i in range(num_particles):
            # Calculate angle for even distribution
            angle = (i / num_particles) * math.tau

            # Create two layers of particles
            for layer in range(2):
                # Base velocity with spiral component
                speed = self.rng.uniform(0.6, 1.0) * (layer + 1)
                spiral_factor = 0.2  # Controls how much spiral motion

                dx = math.cos(angle) * speed + math.sin(angle) * spiral_factor
                dy = math.sin(angle) * speed - math.cos(angle) * spiral_factor

                # Vary trail length based on position in the explosion
                trail_length = int(
                    self.rng.randint(2, 5) * (layer + 1) * (1 + math.sin(angle))
                )

                # Choose different symbols for each layer
                symbol = "★" if layer == 0 else "✦"

                particle = Particle(
                    x=self.x,
                    y=self.y,
                    dx=dx,
                    dy=dy,
                    width=self.width,
                    height=self.height,
                    symbol=symbol,
                    trail_length=trail_length,
                    life=50,  # Longer life to see the spiral motion
                    rng=self.rng,
                )

                self.particles.append(particle)

    def is_active(self):
        """
        Returns True if the portal is active (emitting particles), False otherwise.

        Returns:
            bool: Whether or not the firework is still alive
        """
        # Firework is active if it has not exploded or if particles are still alive
        return not self.exploded or len(self.particles) > 0

    def get_colors(self):
        """
        Get the colors for the firework based on its color type.

        Returns:
            list[int]: List of colors that should be used to color the firework.
        """
        if self.firework_color_type == "solid":
            return [self.rng.randint(0, 255)]
        elif self.firework_color_type == "twotone":
            return self.rng.choice(two_tone_colors)
        elif self.firework_color_type == "random":
            return [
                self.rng.randint(0, 255),
                self.rng.randint(0, 255),
                self.rng.randint(0, 255),
                self.rng.randint(0, 255),
                self.rng.randint(0, 255),
                self.rng.randint(0, 255),
            ]
        elif self.firework_color_type == "rainbow":
            return [196, 208, 190, 46, 27, 92]

    def render(self, buffer: Buffer):
        """
        Render the firework to a Buffer object.

        Args:
            buffer (Buffer): Buffer used to house the image effect.
        """
        # Draw firework trail or particles in the buffer
        if not self.exploded:
            if 0 <= self.x < self.width and 0 <= self.y < self.height:
                buffer.put_char(int(self.x), int(self.y), val="|")
                buffer.put_char(int(self.previous_x), int(self.previous_y), val=" ")
            else:
                buffer.put_char(int(self.previous_x), int(self.previous_y), val=" ")
        else:
            if not self.caught_last_trail:
                self.caught_last_trail = True
                buffer.put_char(int(self.previous_x), int(self.previous_y), val=" ")

            for particle in self.particles:
                for x, y, symbol in particle.get_display_points():
                    buffer.put_char(int(x), int(y), symbol)
                px, py = int(particle.x), int(particle.y)
                if 0 <= px < self.width and 0 <= py < self.height:
                    if self.color_enabled:
                        color = self.rng.choice(self.colors)
                        buffer.put_char(
                            px, py, val=bc(particle.symbol, color=color).colored
                        )
                    else:
                        buffer.put_char(px, py, val=particle.symbol)
                    buffer.put_char(
                        int(particle.previous_x), int(particle.previous_y), val=" "
                    )
            for particle in self.clear_particles:
                buffer.put_char(
                    int(particle.previous_x), int(particle.previous_y), val=" "
                )


class FireworkEffect(BaseEffect):
    """
    A spectacular fireworks display effect that can create various types of firework patterns.

    This class provides a highly customizable fireworks display with support for different
    explosion patterns, colors, and special effects. It can render traditional circular bursts,
    as well as exotic patterns like fractals, quantum effects, and interdimensional portals.

    Example Usage::

        from bruhanimate import Buffer
        from bruhanimate.bruheffect import FireworkEffect

        # Create a basic fireworks display
        buffer = Buffer(width=80, height=24)
        fireworks = FireworkEffect(buffer=buffer, background=" ")

        # Configure the fireworks
        fireworks.set_firework_type("circular")
        fireworks.set_firework_rate(0.1)
        fireworks.set_firework_color_enabled(True)
        fireworks.set_firework_color_type("rainbow")

        # Render frames in your animation loop
        for frame in range(100):
            fireworks.update(1 / 30)
            buffer.display()

    Advanced Example::

        # Create a mixed fireworks display with specific types
        fireworks.set_firework_type("random")
        fireworks.set_allowed_firework_types([
            "circular", "starburst", "butterfly",
            "quantum", "galaxy"
        ])

    Warning:
        - High firework rates (>0.3) may impact performance on slower systems
        - Some exotic firework types may be CPU intensive
        - Color support requires a terminal that supports ANSI color codes

    Note:
        The firework patterns are designed to work best in terminals with aspect
        ratios close to 1:2 (height:width). Some patterns may appear distorted
        in terminals with very different aspect ratios.

    See Also:
        - :class:`BaseEffect`: The parent class for all effects
        - :class:`Buffer`: The buffer class used for rendering
    """

    def __init__(
        self, buffer: Buffer, background: str, settings: FireworkSettings | None = None
    ):
        """
        Initializes the FireworkEffect.

        Args:
            buffer (Buffer): Effect buffer to push updates to.
            background (str): Character or string to use as the background.
            settings (FireworkSettings, optional): Configuration for the firework effect. Defaults to None.
        """
        s = validated_settings(settings, FireworkSettings)
        super(FireworkEffect, self).__init__(buffer, background, seed=s.seed)
        self.firework_type: FireworkType = (
            s.firework_type
            if s.firework_type in valid_firework_types or s.firework_type == "random"
            else "circular"
        )
        self.firework_color_type: FireworkColorType = (
            s.color_type if s.color_type in valid_firework_color_types else "solid"
        )
        self.color_enabled: bool = s.color_enabled
        self.fireworks: list[Firework] = []
        self.firework_rate: float = s.rate
        self.allowed_firework_types = valid_firework_types

    def set_firework_type(self, firework_type: FireworkType):
        """
        Set the type of firework explosions to be created.

        Args:
            firework_type (FireworkType): The type of firework to create. Can be one of:
                - "circular": Traditional circular burst
                - "starburst": Radiating star pattern
                - "butterfly": Elegant butterfly pattern
                - "quantum": Quantum probability cloud
                ... and many more

        Example::

            fireworks.set_firework_type("butterfly")
            # Or use random for variety
            fireworks.set_firework_type("random")

        Warning:
            Some exotic firework types (like "quantum", "hypercube", etc.) may be
            more CPU intensive than traditional patterns.

        Note:
            When using "random" type, the actual patterns used will be limited to
            those specified in allowed_firework_types.
        """
        if firework_type in valid_firework_types or firework_type == "random":
            self.firework_type = firework_type

    def set_firework_color_enabled(self, color_enabled: bool):
        """Enable or disable ANSI colors for newly launched fireworks.

        Args:
            color_enabled (bool): Whether new fireworks use the selected palette.
        """
        self.color_enabled = color_enabled

    def set_firework_color_type(self, firework_color_type: FireworkColorType):
        """Select a supported palette for newly launched colored fireworks.

        Args:
            firework_color_type (FireworkColorType): Palette name, for example
                "rainbow" or "twotone". Unknown names leave the palette unchanged.
        """
        if firework_color_type in valid_firework_color_types:
            self.firework_color_type = firework_color_type

    def set_firework_rate(self, firework_rate: float):
        """Set launch probability per simulation update, independent of draw FPS.

        Args:
            firework_rate (float): A value in (0, 1]. Other values are ignored.
                FireworkSettings(rate=0) can disable launches at construction.
        """
        if firework_rate > 0.0 and firework_rate <= 1.0:
            self.firework_rate = firework_rate

    def set_allowed_firework_types(self, allowed_firework_types):
        """
        Specify which firework types can be used when type is set to "random".

        Args:
            allowed_firework_types (List[str]): List of firework type names to allow.
                Must be valid types from valid_firework_types.

        Example::

            # Create a show with only geometric patterns
            fireworks.set_allowed_firework_types([
                "circular", "ring", "diamond", "star"
            ])

            # Create a show with exotic effects
            fireworks.set_allowed_firework_types([
                "quantum", "hypercube", "galaxy",
                "interdimensional", "cosmic_string"
            ])

        Warning:
            - An empty list or list with no valid types will revert to all types
            - Invalid type names will be silently ignored
            - Some combinations of types may create visually jarring transitions

        Note:
            This setting only affects fireworks when type is set to "random".
            For consistent displays, choose types with similar visual characteristics.
        """
        allowed_firework_types = [
            ft for ft in allowed_firework_types if ft in valid_firework_types
        ]
        if len(allowed_firework_types) > 0:
            self.allowed_firework_types = allowed_firework_types

    def update(self, dt: float) -> None:
        """Advance one simulation tick; dt is measured in seconds."""

        if self.rng.random() < self.firework_rate:
            self.fireworks.append(
                Firework(
                    firework_type=self.firework_type,
                    height=self.buffer.height(),
                    width=self.buffer.width(),
                    firework_color_type=self.firework_color_type,
                    color_enabled=self.color_enabled,
                    allowed_firework_types=self.allowed_firework_types,
                    rng=self.rng,
                )
            )

        for firework in self.fireworks:
            firework.update()
            firework.render(self.buffer)

        self.fireworks = [
            firework for firework in self.fireworks if firework.is_active()
        ]

    def resize(self, size: tuple[int, int]) -> None:
        """Update launch/particle bounds without aging or recreating fireworks.

        Positions and trails retain their coordinates and clip to the raster.
        Peaks clamp below the new height; future launches use the new bounds.
        """
        self.buffer = raster(self.buffer, size, self.background)
        width, height = size
        for firework in self.fireworks:
            firework.width, firework.height = width, height
            firework.peak = min(firework.peak, height - 1)
            for particle in firework.particles:
                particle.width, particle.height = width, height
        super().resize(size)
