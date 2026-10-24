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

from typing import List

import pyfiglet

from .bruherrors import InvalidImageError
from .bruhtypes import Font, Image

bruh = [
    r"loading BRUH SHELL 2.0 loading BRUH SHELL 2.0 loading BRUH ",
    r"loading BRUH SHELL 2.0 loading BRUH SHELL 2.0 loading BRUH ",
    r"loading BRUH SHELL 2.0 loading BRUH SHELL 2.0 loading BRUH ",
    r"loading BRUH         _             _           oading BRUH ",
    r"loading BRUH       /\ \          / /\          oading BRUH ",
    r"loading BRUH      /  \ \        / /  \         oading BRUH ",
    r"loading BRUH     / /\ \ \      / / /\ \        oading BRUH ",
    r"loading BRUH     \/_/\ \ \    / / /\ \ \       oading BRUH ",
    r"loading BRUH         / / /   /_/ /  \ \ \      oading BRUH ",
    r"loading BRUH        / / /    \ \ \   \ \ \     oading BRUH ",
    r"loading BRUH       / / /  _   \ \ \   \ \ \    oading BRUH ",
    r"loading BRUH      / / /_/\_\ _ \ \ \___\ \ \   oading BRUH ",
    r"loading BRUH     / /_____/ //\_\\ \/____\ \ \  oading BRUH ",
    r"loading BRUH     \________/ \/_/ \_________\/  oading BRUH ",
    r"loading BRUH                                   oading BRUH ",
    r"loading BRUH SHELL 2.0 loading BRUH SHELL 2.0 loading BRUH ",
    r"loading BRUH SHELL 2.0 loading BRUH SHELL 2.0 loading BRUH ",
    r"loading BRUH SHELL 2.0 loading BRUH SHELL 2.0 loading BRUH ",
]

bruh_empty = [
    r"    _             _          ",
    r"  /\ \          / /\         ",
    r" /  \ \        / /  \        ",
    r"/ /\ \ \      / / /\ \       ",
    r"\/_/\ \ \    / / /\ \ \      ",
    r"    / / /   /_/ /  \ \ \     ",
    r"   / / /    \ \ \   \ \ \    ",
    r"  / / /  _   \ \ \   \ \ \   ",
    r" / / /_/\_\ _ \ \ \___\ \ \  ",
    r"/ /_____/ //\_\\ \/____\ \ \ ",
    r"\________/ \/_/ \_________\/ ",
]

bruh_computer = [
    "                       .,,uod8B8bou,,.                             ",
    "              ..,uod8BBBBBBBBBBBBBBBBRPFT?l!i:.                    ",
    "         ,=m8BBBBBBBBBBBBBBBRPFT?!||||||||||||||                   ",
    '         !...:!TVBBBRPFT||||||||||!!^^""\'    |||                   ',
    '         !.......:!?|||||!!^^""\'             |||                   ',
    "         !.........|||   ___ ___ _   _ _  _  |||                   ",
    "         !.........|||  | _ ) _ \\ | | | || | |||                   ",
    "         !.........|||  | _ \\   / |_| | __ | |||                   ",
    "         !.........|||  |___/_|_\\\\___/|_||_| |||                   ",
    "         !.........|||   ---   --            |||                   ",
    "         !.........|||  |_  ) /  \\           |||                   ",
    "         `.........|||   / / | () |        , |||                   ",
    "          .;.......|||  /___(_)__/     _.-!!||||                   ",
    "   .,uodWBBBBb.....|||        _.-!!|||||||||!:'                    ",
    "!YBBBBBBBBBBBBBBb..!|||:..-!!|||||||!iof68BBBBBb....               ",
    "!..YBBBBBBBBBBBBBBb!!||||||||!iof68BBBBBBRPFT?!::   `.             ",
    "!....YBBBBBBBBBBBBBBbaaitf68BBBBBBRPFT?!:::::::::     `.           ",
    '!......YBBBBBBBBBBBBBBBBBBBRPFT?!::::::;:!^"`;:::       `.         ',
    "!........YBBBBBBBBBBRPFT?!::::::::::^''...::::::;         iBBbo.   ",
    "`..........YBRPFT?!::::::::::::::::::::::::;iof68bo.      WBBBBbo. ",
    "  `..........:::::::::::::::::::::::;iof688888888888b.     `YBBBP^'",
    "    `........::::::::::::::::;iof688888888888888888888b.     `     ",
    "      `......:::::::::;iof688888888888888888888888888888b.         ",
    "        `....:::;iof688888888888888888888888888888888899fT!        ",
    "          `..::!8888888888888888888888888888888899fT|!^\"'          ",
    "            `' !!988888888888888888888888899fT|!^\"'                ",
    "                `!!8888888888888888899fT|!^\"'                      ",
    "                  `!988888888899fT|!^\"'                            ",
    "                    `!9899fT|!^\"'                                  ",
    "                      `!^\"'                                        ",
]

computer = [
    "                       .,,uod8B8bou,,.                             ",
    "              ..,uod8BBBBBBBBBBBBBBBBRPFT?l!i:.                    ",
    "         ,=m8BBBBBBBBBBBBBBBRPFT?!||||||||||||||                   ",
    '         !...:!TVBBBRPFT||||||||||!!^^""\'    |||                   ',
    '         !.......:!?|||||!!^^""\'             |||                   ',
    "         !.........|||                       |||                   ",
    "         !.........|||                       |||                   ",
    "         !.........|||                       |||                   ",
    "         !.........|||                       |||                   ",
    "         !.........|||                       |||                   ",
    "         !.........|||                       |||                   ",
    "         `.........|||                     , |||                   ",
    "          .;.......|||                 _.-!!||||                   ",
    "   .,uodWBBBBb.....|||        _.-!!|||||||||!:'                    ",
    "!YBBBBBBBBBBBBBBb..!|||:..-!!|||||||!iof68BBBBBb....               ",
    "!..YBBBBBBBBBBBBBBb!!||||||||!iof68BBBBBBRPFT?!::   `.             ",
    "!....YBBBBBBBBBBBBBBbaaitf68BBBBBBRPFT?!:::::::::     `.           ",
    '!......YBBBBBBBBBBBBBBBBBBBRPFT?!::::::;:!^"`;:::       `.         ',
    "!........YBBBBBBBBBBRPFT?!::::::::::^''...::::::;         iBBbo.   ",
    "`..........YBRPFT?!::::::::::::::::::::::::;iof68bo.      WBBBBbo. ",
    "  `..........:::::::::::::::::::::::;iof688888888888b.     `YBBBP^'",
    "    `........::::::::::::::::;iof688888888888888888888b.     `     ",
    "      `......:::::::::;iof688888888888888888888888888888b.         ",
    "        `....:::;iof688888888888888888888888888888888899fT!        ",
    "          `..::!8888888888888888888888888888888899fT|!^\"'          ",
    "            `' !!988888888888888888888888899fT|!^\"'                ",
    "                `!!8888888888888888899fT|!^\"'                      ",
    "                  `!988888888899fT|!^\"'                            ",
    "                    `!9899fT|!^\"'                                  ",
    "                      `!^\"'                                        ",
]

hey = [
    "    __  __          ",
    "   / / / /__  __  __",
    "  / /_/ / _ \\/ / / /",
    " / __  /  __/ /_/ / ",
    "/_/ /_/\\___/\\__, /  ",
    "           /____/   ",
]

twopoint = [
    r"                                                                               ",
    r"   ____________ _   _ _   _  _____ _   _  _____ _      _       _____  _____    ",
    r"   | ___ \ ___ \ | | | | | |/  ___| | | ||  ___| |    | |     / __  \|  _  |   ",
    r"   | |_/ / |_/ / | | | |_| |\ `--.| |_| || |__ | |    | |     `' / /'| |/' |   ",
    r"   | ___ \    /| | | |  _  | `--. \  _  ||  __|| |    | |       / /  |  /| |   ",
    r"   | |_/ / |\ \| |_| | | | |/\__/ / | | || |___| |____| |____ ./ /___\ |_/ /   ",
    r"   \____/\_| \_|\___/\_| |_/\____/\_| |_/\____/\_____/\_____/ \_____(_)___/    ",
    r"                                                                               ",
]

christmas = [
    r"                ",
    r"      _\/_      ",
    r"       /\       ",
    r"       /\       ",
    r"      /  \      ",
    r"      /~~\ o    ",
    r"     / o  \     ",
    r"    /~~*~~~\    ",
    r"  o /    o \    ",
    r"   /~~~~~~~~\~` ",
    r"  /__*_______\  ",
    r"       ||       ",
    r"     \====/     ",
    r"      \__/      ",
    r"                ",
]

image_mappings = {
    "bruh": bruh,
    "bruh_empty": bruh_empty,
    "bruh_computer": bruh_computer,
    "computer": computer,
    "hey": hey,
    "twopoint": twopoint,
    "christmas": christmas,
}


def get_image(name: Image = "hey") -> List[str]:
    """
    Retrieves one of the pre-defined ASCII art images based on the given name.

    Args:
        name (Image): The name of the image to retrieve.

    Returns:
        List[str]: A list of strings representing the ASCII art image.

    Raises:
        InvalidImageError: If the image name is not known or registered.
    """
    if name not in image_mappings:
        raise InvalidImageError(f"Unknown / non-registered image: {name}")
    return image_mappings.get(name)


def text_to_image(
    text: str,
    font: Font = pyfiglet.DEFAULT_FONT,
    padding_top_bottom: int = 0,
    padding_left_right: int = 0,
) -> List[str]:
    """
    Converts text into ASCII art using the specified font and padding.

    Args:
        text (str): The text to convert into ASCII art.
        font (Font): The font to use for the ASCII art.
        padding_top_bottom (int): Number of empty lines to add above and below the ASCII art.
        padding_left_right (int): Number of spaces to add on the left and right of each line.

    Returns:
        List[str]: A list of strings representing the ASCII art with padding.
    """
    try:
        img_flat = pyfiglet.Figlet(font).renderText(text)
    except pyfiglet.FontError:
        img_flat = pyfiglet.Figlet("standard").renderText(text)

    img = img_flat.splitlines()

    largest_row = max([len(row) for row in img])
    for idx in range(len(img)):
        img[idx] += " " * (largest_row - len(img[idx]))

    if padding_top_bottom > 0:
        empty_line = " " * len(img[0])
        img = (
            [empty_line] * padding_top_bottom + img + [empty_line] * padding_top_bottom
        )

    if padding_left_right > 0:
        padding = " " * padding_left_right
        img = [f"{padding}{line}{padding}" for line in img]

    return img
