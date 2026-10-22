# Copyright 2024 Anri Dellal
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Final

from pmb.helpers import logging

"""
Helper used to configure locale-related settings in pmOS installation.

Locale and layout information is taken from:
* https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes
* https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
* Xkb source code: /usr/share/X11/xkb/rules/base.lst
"""


class XkbLayout:
    primary_layouts: Final[frozenset[str]] = frozenset(
        [
            "at",
            "au",
            "br",
            "ca",
            "ch",
            "de",
            "dk",
            "ee",
            "es",
            "fi",
            "fo",
            "fr",
            "gb",
            "ie",
            "is",
            "it",
            "latam",
            "lt",
            "mt",
            "nz",
            "pl",
            "pt",
            "ro",
            "se",
            "sk",
            "tr",
            "us",
            "vn",
        ]
    )

    def __init__(self, layout: str = "us", variant: str = "") -> None:
        self.layout = layout
        self.variant = variant
        self.options = ""
        self.layout_list: list[str] = []
        self.variant_list: list[str] = []
        if layout in XkbLayout.primary_layouts:
            self.layout_list.append(layout)
            if variant:
                self.variant_list.append(variant)
        elif not self.is_default():
            self.layout_list.extend(["us", layout])
            if variant:
                self.variant_list.extend(["", variant])
            self.options = "grp:alt_shift_toggle"

    def is_default(self) -> bool:
        return self.layout == "us" and not self.variant

    def get_profile_vars(self) -> str | None:
        if self.is_default():
            return None
        template = "XKB_DEFAULT_LAYOUT=" + ",".join(self.layout_list)
        if self.variant_list:
            template += "\nXKB_DEFAULT_VARIANT=" + ",".join(self.variant_list)
        if self.options:
            template += "\nXKB_DEFAULT_OPTIONS=" + self.options
        return template

    def get_keyboard_config(self) -> str | None:
        if self.is_default() or not self.layout_list:
            return None
        template = f"""Section "InputClass"
\tIdentifier "keyboard"
\tMatchIsKeyboard "on"
\tOption "XkbLayout" "{",".join(self.layout_list)}"\n"""
        if self.variant_list:
            template += f'\tOption "XkbVariants" "{",".join(self.variant_list)}"\n'
        if self.options:
            template += f'\tOption "XkbOptions" "{self.options}"\n'
        template += "EndSection"
        return template

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, XkbLayout):
            return False
        return self.layout == other.layout and self.variant == other.variant


def get_xkb_layout(locale: str) -> XkbLayout:
    """
    Get Xkb layout for the given locale.

    :param locale: Locale to get XkbLayout for.
    :return: XkbLayout for the given locale.
    """
    try:
        (language, territory) = locale.split("_")
    except ValueError:
        logging.warning(f'Keyboard config for locale "{locale}" cannot be provided')
        return XkbLayout()

    if language in lang_layouts:
        return XkbLayout(language)
    elif language in lang_to_layout:
        return XkbLayout(lang_to_layout[language])

    match language:
        case "af":
            return XkbLayout("za")
        case "ak":
            return XkbLayout("gh", "akan")
        case "ar":
            if territory == "DZ":
                return XkbLayout("dz", "ar")
            elif territory == "EG":
                return XkbLayout("eg")
            elif territory == "IQ":
                return XkbLayout("iq")
            elif territory == "MA":
                return XkbLayout("ma")
            elif territory == "SY":
                return XkbLayout("sy")
            else:
                return XkbLayout("ara")
        case "as":
            return XkbLayout("in", "asm-kagapa")
        case "ast":
            return XkbLayout("es", "ast")
        case "ber":
            if territory == "DZ":
                return XkbLayout("dz")
            else:  # "MA"
                return XkbLayout("ma")
        case "bo":
            return XkbLayout("cn", "tib")
        case "ca":
            return XkbLayout("es", "cat")
        case "chr":
            return XkbLayout("us", "chr")
        case "crh":
            return XkbLayout("ua", "crh")
        case "de":
            if territory == "AT":
                return XkbLayout("at")
            elif territory == "CH":
                return XkbLayout("ch")
            else:
                return XkbLayout("de")
        case "en":
            if territory == "AU":
                return XkbLayout("au")
            elif territory == "CA":
                return XkbLayout("ca", "eng")
            elif territory == "GB":
                return XkbLayout("gb")
            elif territory == "IN":
                return XkbLayout("in", "eng")
            elif territory == "NG":
                return XkbLayout("ng")
            elif territory == "NZ":
                return XkbLayout("nz")
            elif territory == "ZA":
                return XkbLayout("za")
            else:
                return XkbLayout("us")
        case "es":
            if territory in latam_es_territories:
                return XkbLayout("latam")
            else:  # "ES", "US"
                return XkbLayout("es")
        case "fr":
            if territory == "CA":
                return XkbLayout("ca")
            elif territory == "CH":
                return XkbLayout("ch", "fr")
            else:  # "FR"
                return XkbLayout("fr")
        case "fur":
            return XkbLayout("it", "fur")
        case "gu":
            return XkbLayout("in", "guj")
        case "gv":
            return XkbLayout("gb", "gla")
        case "ha":
            return XkbLayout("ng", "hausa")
        case "hif" | "hne":
            return XkbLayout("in")
        case "ig":
            return XkbLayout("ng", "igbo")
        case "iu":
            return XkbLayout("ca", "ike")
        case "kab":
            return XkbLayout("dz", "azerty-deadkeys")
        case "kn":
            return XkbLayout("in", "kan")
        case "ku":
            return XkbLayout("tr", "ku")
        case "mhr":
            return XkbLayout("ru", "chm")
        case "ml":
            return XkbLayout("in", "mal")
        case "mni":
            return XkbLayout("in", "mni")
        case "mnw":
            return XkbLayout("mm", "mnw")
        case "mr":
            return XkbLayout("in", "marathi")
        case "nan":
            return XkbLayout("cn")  # Min Nan Chinese
        case "nds":
            return XkbLayout("de")  # Low German
        case "oc":
            return XkbLayout("fr", "oci")
        case "or":
            return XkbLayout("in", "ori")
        case "os":
            return XkbLayout("ru", "os_winkeys")
        case "pa":
            return XkbLayout("in", "guru")
        case "ps":
            return XkbLayout("af", "ps")
        case "pt":
            if territory == "BR":
                return XkbLayout("br")
            else:  # if territory == "PT":
                return XkbLayout("pt")
        case "sa":
            return XkbLayout("in", "sas")
        case "sah":
            return XkbLayout("ru", "sah")
        case "sat":
            return XkbLayout("in", "sat")
        case "sd":
            return XkbLayout("in", "sdh")
        case "se":
            return XkbLayout("no", "smi")
        case "sgs":
            return XkbLayout("lt", "sgs")
        case "shn":
            return XkbLayout("mm", "shn")
        case "si":
            return XkbLayout("pk", "snd")
        case "sw":
            if territory == "KE":
                return XkbLayout("ke")
            else:  # "TZ"
                return XkbLayout("tz")
        case "szl":
            return XkbLayout("pl", "szl")
        case "ta":
            if territory == "LK":
                return XkbLayout("lk", "tam_unicode")
            else:  # "IN"
                return XkbLayout("in", "tamilnet")
        case "te":
            return XkbLayout("in", "tel")
        case "tt":
            return XkbLayout("ru", "tt")
        case "ug":
            return XkbLayout("cn", "ug")
        case "ur":
            return XkbLayout("pak", "urd-nla")
        case "yo":
            return XkbLayout("ng", "yoruba")
        case _:
            pass
    if language not in locales_without_layout:
        logging.warning(f'Language "{language}" not found in language list')
    return XkbLayout()  # return default layout if no layout was found


# Layouts which have same code as language
lang_layouts = [
    "az",
    "bg",
    "csb",
    "cv",
    "dsb",
    "fi",
    "fo",
    "hr",
    "hu",
    "id",
    "is",
    "it",
    "lt",
    "lv",
    "mk",
    "mn",
    "mt",
    "nl",
    "pl",
    "ro",
    "ru",
    "sk",
    "tg",
    "th",
    "tr",
    "uk",
    "uz",
]
lang_to_layout = {
    "am": "et",
    "be": "by",
    "bn": "bd",
    "br": "bre",
    "bs": "ba",
    "cmn": "cn",
    "cs": "cz",
    "da": "dk",
    "dz": "bt",
    "el": "gr",
    "eo": "epo",
    "et": "ee",
    "eu": "es",
    "fa": "ir",
    "fil": "ph",
    "ga": "ie",
    "gd": "gla",
    "hak": "cn",
    "he": "il",
    "hi": "in",
    "hy": "am",
    "ja": "jp",
    "ka": "ge",
    "kk": "kz",
    "km": "kh",
    "ko": "kr",
    "ky": "kg",
    "lo": "la",
    "lzh": "cn",
    "mai": "in",
    "mi": "mao",
    "ms": "my",
    "my": "mm",
    "nb": "no",
    "ne": "np",
    "nn": "no",
    "sl": "si",
    "sq": "al",
    "sr": "rs",
    "sv": "se",
    "tk": "tm",
    "tl": "in",
    "tn": "bw",
    "vi": "vn",
    "wo": "sn",
    "yi": "il",
    "yue": "cn",
    "zh": "cn",
}
# Locales which either have no layout or missing information about one
locales_without_layout = [
    "aa",  # Afar
    "agr",  # Aguaruna
    "an",  # Aragonese
    "anp",  # Angika
    "ayc",  # Aymara
    "bem",  # Bemba
    "bhb",  # Bhili
    "bho",  # Bhojpuri
    "bi",  # Bislama
    "bn",  # Bengali
    "brx",  # Bodo (India)
    "byn",  # Bilin
    "ce",  # Chechen
    "ch",  # Chamorro
    "cy",  # Wales
    "doi",  # Dogri
    "dv",  # Divehi
    "ff",  # Fulah
    "fy",  # Western Frisian
    "gez",  # Geez
    "gl",  # Galician
    "hsb",  # Upper Sorbian
    "ht",  # Haitian
    "ia",  # Interlingua
    "ik",  # Inupiaq
    "kl",  # Kalaallisut, Greenlandic
    "kok",  # Konkani
    "ks",  # Kashmiri
    "kw",  # Kinyarwanda
    "lb",  # Luxembourgish
    "lg",  # Ganda
    "li",  # Limburgish
    "lij",  # Ligurian
    "ln",  # Lingala
    "mfe",  # Morisyen
    "mg",  # Malagasy
    "miq",  # Miskito
    "mjw",  # Karbi
    "nhn",  # Nahuatl
    "niu",  # Niuean
    "nr",  # South Ndebele
    "nso",  # Northern Sotho
    "om",  # Oromo
    "pap",  # Papiamento
    "quz",  # Cusco Quechua
    "raj",  # Rajasthani
    "rw",  # Kinyarwanda
    "sc",  # Sardinian
    "shs",  # Shuswap
    "sid",  # Sidamo
    "sm",  # Samoan
    "so",  # Somali
    "ss",  # Swati
    "st",  # Southern Sotho
    "tcy",  # Tulu
    "the",  # Chitwania Tharu
    "ti",  # Tigrinya
    "tig",  # Tigre
    "to",  # Tonga
    "tpi",  # Tok Pisin
    "ts",  # Tsonga
    "unm",  # Unami
    "ve",  # Venda
    "wa",  # Walloon
    "wae",  # Walser
    "wal",  # Wolaitta
    "xh",  # Xhosa
    "yuw",  # Yau (Morobe province)
    "zu",  # Zulu
]
latam_es_territories = [
    "AR",
    "BO",
    "CL",
    "CO",
    "CR",
    "CU",
    "DO",
    "EC",
    "GT",
    "HN",
    "MX",
    "NI",
    "PA",
    "PE",
    "PR",
    "PY",
    "SV",
    "UY",
    "VE",
]
