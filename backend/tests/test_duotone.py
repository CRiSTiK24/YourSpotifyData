import pytest

from src.duotone import _grayscale_to_palette_gradient_luts, _hex_to_rgb, _luminance


@pytest.mark.parametrize(
    "hex_color, expected",
    [
        ("#000000", (0, 0, 0)),
        ("#ffffff", (255, 255, 255)),
        ("ff0000", (255, 0, 0)),
        ("#00ff00", (0, 255, 0)),
    ],
)
def test_hex_to_rgb_parses_with_or_without_leading_hash(hex_color, expected):
    assert _hex_to_rgb(hex_color) == expected


def test_luminance_ranks_white_brighter_than_black():
    assert _luminance((255, 255, 255)) > _luminance((0, 0, 0))


def test_luminance_weighs_green_more_than_red_or_blue():
    pure_green = _luminance((0, 255, 0))
    pure_red = _luminance((255, 0, 0))
    pure_blue = _luminance((0, 0, 255))
    assert pure_green > pure_red > pure_blue


def test_gradient_luts_map_darkest_input_to_the_darkest_palette_stop():
    lut_r, lut_g, lut_b = _grayscale_to_palette_gradient_luts(["#ffffff", "#000000"])
    assert (lut_r[0], lut_g[0], lut_b[0]) == (0, 0, 0)
    assert (lut_r[255], lut_g[255], lut_b[255]) == (255, 255, 255)


def test_gradient_luts_are_stop_order_independent_since_they_sort_by_luminance():
    forward = _grayscale_to_palette_gradient_luts(["#000000", "#ffffff"])
    reversed_input = _grayscale_to_palette_gradient_luts(["#ffffff", "#000000"])
    assert forward == reversed_input


def test_gradient_luts_produce_one_entry_per_possible_grayscale_value():
    lut_r, lut_g, lut_b = _grayscale_to_palette_gradient_luts(["#000000", "#ffffff"])
    assert len(lut_r) == len(lut_g) == len(lut_b) == 256
