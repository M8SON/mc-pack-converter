import pytest

from mc_pack_converter.webui.sky_composite import (
    DAY, brightness, parse_time)


# The four reference points OptiFine's own sky.properties doc states:
#   Sunrise = 6:00 = /time set 0      Noon     = 12:00 = /time set 6000
#   Sunset  = 18:00 = /time set 12000 Midnight =  0:00 = /time set 18000
@pytest.mark.parametrize("text, ticks", [
    ("6:00", 0), ("12:00", 6000), ("18:00", 12000), ("0:00", 18000),
])
def test_a_clock_time_becomes_the_tick_the_doc_says_it_is(text, ticks):
    assert parse_time(text) == ticks


def test_the_day_is_one_full_cycle_of_ticks():
    assert DAY == 24000


# --- the fade curve, ported from CustomSkyLayer.getFadeBrightness ------------
#
# if between(t, startFadeIn, endFadeIn):   t-startFadeIn  / endFadeIn-startFadeIn
# if between(t, endFadeIn, startFadeOut):  1
# if between(t, startFadeOut, endFadeOut): 1 - (t-startFadeOut / endFadeOut-startFadeOut)
# else:                                    0

FULL = {"startFadeIn": "6:00", "endFadeIn": "7:00",
        "startFadeOut": "17:00", "endFadeOut": "18:00"}


def test_a_layer_is_dark_outside_its_window():
    assert brightness(FULL, parse_time("3:00")) == 0.0


def test_a_layer_is_full_between_its_fades():
    assert brightness(FULL, parse_time("12:00")) == 1.0


def test_a_layer_ramps_up_across_its_fade_in():
    assert brightness(FULL, parse_time("6:30")) == pytest.approx(0.5, abs=0.01)


def test_a_layer_ramps_down_across_its_fade_out():
    assert brightness(FULL, parse_time("17:30")) == pytest.approx(0.5, abs=0.01)


def test_the_missing_fourth_key_is_derived_not_required():
    """1778 of the 2120 sky layers in the 173-pack corpus ship exactly three
    of the four fade keys -- startFadeOut is the one they leave out, and
    CustomSkyLayer.isValid derives it rather than rejecting the layer."""
    three = {"startFadeIn": "6:00", "endFadeIn": "7:00", "endFadeOut": "18:00"}
    assert brightness(three, parse_time("12:00")) == 1.0
    assert brightness(three, parse_time("3:00")) == 0.0


# --- blending ---------------------------------------------------------------

def _flat(rgb, size=(2, 2)):
    from PIL import Image
    return Image.new("RGB", size, rgb)


def _pixel(im):
    return im.convert("RGB").getpixel((0, 0))


def test_one_layer_at_full_brightness_is_itself_over_black():
    from mc_pack_converter.webui.sky_composite import composite
    assert _pixel(composite([(_flat((10, 200, 30)), "add", 1.0)])) == (10, 200, 30)


def test_fading_a_layer_out_dims_it():
    from mc_pack_converter.webui.sky_composite import composite
    assert _pixel(composite([(_flat((200, 200, 200)), "add", 0.5)])) == (100, 100, 100)


def test_replace_takes_the_whole_pixel_and_ignores_the_layer_below():
    """OptiFine: "There is no gradual fading with this method; if brightness
    computed from the fade times is > 0, the full pixel value is used." So a
    half-faded replace is still the full colour, not a half one."""
    from mc_pack_converter.webui.sky_composite import composite
    out = composite([(_flat((255, 0, 0)), "add", 1.0),
                     (_flat((0, 0, 255)), "replace", 0.5)])
    assert _pixel(out) == (0, 0, 255)


def test_layers_stack_in_the_order_given():
    from mc_pack_converter.webui.sky_composite import composite
    out = composite([(_flat((10, 0, 0)), "add", 1.0),
                     (_flat((0, 20, 0)), "add", 1.0)])
    assert _pixel(out) == (10, 20, 0)


def test_add_saturates_rather_than_wrapping():
    from mc_pack_converter.webui.sky_composite import composite
    out = composite([(_flat((200, 0, 0)), "add", 1.0),
                     (_flat((200, 0, 0)), "add", 1.0)])
    assert _pixel(out) == (255, 0, 0)


def test_multiply_darkens_by_the_layer():
    from mc_pack_converter.webui.sky_composite import composite
    out = composite([(_flat((255, 255, 255)), "replace", 1.0),
                     (_flat((128, 128, 128)), "multiply", 1.0)])
    assert _pixel(out)[0] == pytest.approx(128, abs=1)


def test_screen_lightens_and_cannot_exceed_white():
    from mc_pack_converter.webui.sky_composite import composite
    out = composite([(_flat((128, 128, 128)), "replace", 1.0),
                     (_flat((128, 128, 128)), "screen", 1.0)])
    assert _pixel(out)[0] == pytest.approx(191, abs=2)


def test_an_unknown_blend_mode_falls_back_to_add():
    """One corpus pack writes `blend=blend`. OptiFine documents add as the
    default, so an unrecognised name behaves as an unset one."""
    from mc_pack_converter.webui.sky_composite import composite
    out = composite([(_flat((10, 20, 30)), "blend", 1.0)])
    assert _pixel(out) == (10, 20, 30)


def test_compositing_nothing_is_an_error_not_a_black_square():
    from mc_pack_converter.webui.sky_composite import composite
    with pytest.raises(ValueError):
        composite([])


def test_a_transparent_layer_adds_nothing():
    """The sunflare case: 83.6% transparent, blend=add. Ignoring alpha turns
    the clear region into opaque white and blows the whole sky out."""
    from PIL import Image
    from mc_pack_converter.webui.sky_composite import composite
    base = Image.new("RGBA", (2, 2), (20, 40, 60, 255))
    clear = Image.new("RGBA", (2, 2), (255, 255, 255, 0))
    out = composite([(base, "replace", 1.0), (clear, "add", 1.0)])
    assert _pixel(out) == (20, 40, 60)


def test_a_half_transparent_layer_adds_half_of_itself():
    from PIL import Image
    from mc_pack_converter.webui.sky_composite import composite
    base = Image.new("RGBA", (2, 2), (0, 0, 0, 255))
    half = Image.new("RGBA", (2, 2), (200, 200, 200, 128))
    out = composite([(base, "replace", 1.0), (half, "add", 1.0)])
    assert _pixel(out)[0] == pytest.approx(100, abs=2)


# --- picking the times, from the pack rather than from the clock -------------

ALL_DAY = {"startFadeIn": "5:30", "endFadeIn": "6:00",
           "startFadeOut": "17:30", "endFadeOut": "18:20", "blend": "replace"}
DUSK_ONLY = {"startFadeIn": "17:30", "endFadeIn": "18:00",
             "startFadeOut": "19:00", "endFadeOut": "19:10", "blend": "replace"}
NIGHT = {"startFadeIn": "18:00", "endFadeIn": "19:00",
         "endFadeOut": "5:25", "blend": "screen"}


def test_a_single_all_day_layer_needs_only_one_sample():
    from mc_pack_converter.webui.sky_composite import sample_times
    assert len(sample_times([(1, ALL_DAY)])) == 1


def test_every_layer_is_shown_at_least_once():
    """The reference pack's failure: sky1 and sky2 carry the red sunrise and
    sunset art (cloud2, mean RGB 85/10/0 against cloud1's 125/141/180) but are
    only visible 18:20-19:10 and 4:45-5:25. Fixed samples at 6:00/12:00/18:00
    all landed inside sky3's 5:30-18:20 replace, so all three tiles were the
    same blue picture and the red sky was never shown at all.
    """
    from mc_pack_converter.webui.sky_composite import sample_times
    layers = [(1, ALL_DAY), (2, DUSK_ONLY), (3, NIGHT)]
    shown = {n for _, numbers in sample_times(layers) for n in numbers}
    assert shown == {1, 2, 3}


def test_a_layer_wiped_by_a_later_replace_is_not_claimed_as_visible():
    """sky1 is drawn before sky3 and sky3 is a replace, so at 18:00 sky1 is
    painted and immediately overwritten. Listing it would be a lie about what
    the tile shows."""
    from mc_pack_converter.webui.sky_composite import visible_at, parse_time
    layers = [(1, NIGHT), (2, ALL_DAY)]
    seen = [n for n, _, _ in visible_at(layers, parse_time("12:00"))]
    assert seen == [2]


def test_the_number_of_samples_is_capped():
    from mc_pack_converter.webui.sky_composite import sample_times
    many = [(i, {"startFadeIn": "%d:00" % i, "endFadeIn": "%d:10" % i,
                 "endFadeOut": "%d:50" % i, "blend": "replace"})
            for i in range(1, 13)]
    assert len(sample_times(many, cap=4)) <= 4


def test_samples_come_back_in_day_order():
    from mc_pack_converter.webui.sky_composite import sample_times
    ticks = [t for t, _ in sample_times([(1, ALL_DAY), (2, DUSK_ONLY), (3, NIGHT)])]
    assert ticks == sorted(ticks)


def test_the_sky_you_see_most_of_the_day_gets_its_own_tile():
    """Covering every layer in the fewest tiles is not the goal on its own.
    The reference pack's sky3 is up alone for twelve hours and sky6 for nine,
    and a pure coverage pick showed neither -- it spent all its tiles on the
    forty-minute transitions where several layers overlap, so the two skies
    you actually spend the day looking at were the ones missing.
    """
    from mc_pack_converter.webui.sky_composite import sample_times
    day = {"startFadeIn": "5:30", "endFadeIn": "6:00", "startFadeOut": "17:30",
           "endFadeOut": "18:20", "blend": "replace"}
    flare = {"startFadeIn": "17:50", "endFadeIn": "18:00",
             "endFadeOut": "19:20", "blend": "add"}
    night = {"startFadeIn": "18:00", "endFadeIn": "19:00",
             "endFadeOut": "5:25", "blend": "screen"}
    picked = sample_times([(3, day), (6, night), (7, flare)])
    sets = [tuple(n) for _, n in picked]
    assert (3,) in sets, "the twelve-hour daytime sky must be shown alone"
    assert (6,) in sets, "so must the nine-hour night sky"


def test_a_sample_time_shows_what_it_claims_to_show():
    """The invariant that catches an off-by-a-day. A stretch of sky that runs
    across tick 0 -- the reference pack's daytime sky is up 5:50 to 17:50, so
    it wraps -- gets merged into one run, and merging it to the wrong end made
    it 24150 ticks long, 100.6% of a day. Its midpoint then fell outside its
    own window, so the tile was rendered and labelled at a moment when a
    different set of layers was up.
    """
    from mc_pack_converter.webui.sky_composite import sample_times, visible_at
    # The reference pack's own six layers, verbatim from its .properties.
    layers = [
        (1, {"startFadeIn": "17:30", "endFadeIn": "18:45",
             "startFadeOut": "18:50", "endFadeOut": "19:10", "blend": "add"}),
        (2, {"startFadeIn": "4:45", "endFadeIn": "5:10",
             "startFadeOut": "5:40", "endFadeOut": "6:05", "blend": "add"}),
        (3, {"startFadeIn": "5:30", "endFadeIn": "6:00",
             "startFadeOut": "17:30", "endFadeOut": "18:20", "blend": "replace"}),
        (6, {"startFadeIn": "18:00", "endFadeIn": "19:00",
             "endFadeOut": "5:25", "blend": "screen"}),
        (7, {"startFadeIn": "17:50", "endFadeIn": "18:10",
             "endFadeOut": "19:20", "blend": "add"}),
        (8, {"startFadeIn": "4:40", "endFadeIn": "5:00",
             "endFadeOut": "5:50", "blend": "add"}),
    ]
    for ticks, numbers in sample_times(layers):
        actual = [n for n, _, _ in visible_at(layers, ticks)]
        assert actual == numbers, (
            f"at {ticks} the tile claims {numbers} but {actual} is up")
