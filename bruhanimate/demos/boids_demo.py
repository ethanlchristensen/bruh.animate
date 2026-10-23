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

from bruhanimate import play
from bruhanimate.bruheffect import BoidsSettings

TARGET_FPS = 30


def run(*, frames=None, fps=TARGET_FPS):
    return play(
        "boids",
        frames=frames,
        fps=fps,
        updates_per_second=30,
        background=" ",
        settings=BoidsSettings(
            num_boids=80, color=True, max_speed=1.5, perception=12.0
        ),
    )


if __name__ == "__main__":
    run()
