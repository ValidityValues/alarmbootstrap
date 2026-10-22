# Copyright 2024 Anri Dellal
# SPDX-License-Identifier: GPL-3.0-or-later

from pmb.helpers.locale import XkbLayout, get_xkb_layout


def test_xkb_layout_class() -> None:
    # test primary layout
    layout_de = XkbLayout("de")
    assert layout_de.get_profile_vars() == "XKB_DEFAULT_LAYOUT=de"
    layout_de_keyboard_config = """Section "InputClass"
\tIdentifier "keyboard"
\tMatchIsKeyboard "on"
\tOption "XkbLayout" "de"
EndSection"""
    assert layout_de.get_keyboard_config() == layout_de_keyboard_config

    # test non-primary layout with variant
    layout_ru_chm = XkbLayout("ru", "chm")
    layout_ru_chm_profile_vars = """XKB_DEFAULT_LAYOUT=us,ru
XKB_DEFAULT_VARIANT=,chm
XKB_DEFAULT_OPTIONS=grp:alt_shift_toggle"""
    assert layout_ru_chm.get_profile_vars() == layout_ru_chm_profile_vars
    layout_ru_chm_keyboard_config = """Section "InputClass"
\tIdentifier "keyboard"
\tMatchIsKeyboard "on"
\tOption "XkbLayout" "us,ru"
\tOption "XkbVariants" ",chm"
\tOption "XkbOptions" "grp:alt_shift_toggle"
EndSection"""
    assert layout_ru_chm.get_keyboard_config() == layout_ru_chm_keyboard_config


def test_xkb_layout_getter() -> None:
    # Unsupported locale (incorrect input)
    assert get_xkb_layout("C") == XkbLayout()

    # locale where language code matches layout code
    assert get_xkb_layout("az_AZ") == XkbLayout("az")

    # locale where language code has layout code stored in dictionary
    assert get_xkb_layout("am_ET") == XkbLayout("et")

    # locale with more complicated rules
    assert get_xkb_layout("en_CA") == XkbLayout("ca", "eng")

    # Unsupported locale
    assert get_xkb_layout("abc_DE") == XkbLayout()
