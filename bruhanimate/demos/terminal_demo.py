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

"""A pipe-based console over snow. Escape quits; q remains shell input."""

from bruhanimate import Buffer, Layer, Player, Scene, Screen, SnowEffect, TerminalEffect


def run(*, frames=None, fps=30):
    def show(screen):
        terminal = TerminalEffect(Buffer(screen.height, screen.width))
        scene = Scene(
            SnowEffect(Buffer(screen.height, screen.width), " "),
            Layer(terminal, transparent=True),
        )
        return Player(
            screen,
            scene,
            frames=frames,
            fps=fps,
            updates_per_second=30,
            event_handler=terminal.handle_event,
        ).run()

    return Screen.show(show)


if __name__ == "__main__":
    run()
