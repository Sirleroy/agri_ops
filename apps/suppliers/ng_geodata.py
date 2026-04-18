"""
Nigerian geodata — canonical LGA and State lookup for data normalisation.

Usage:
    from apps.suppliers.ng_geodata import canonicalise_lga_state, normalise_commodity

canonicalise_lga_state('kaduna south', 'kaduna')
    → ('Kaduna South', 'Kaduna')

canonicalise_lga_state('jos north', '')
    → ('Jos North', 'Plateau')   ← state auto-filled from LGA

normalise_commodity('soy beans')
    → 'Soybeans'
"""
import difflib


# ── Canonical state names ─────────────────────────────────────────────────────

NIGERIA_STATES = [
    'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue',
    'Borno', 'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu', 'FCT',
    'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 'Kogi',
    'Kwara', 'Lagos', 'Nasarawa', 'Niger', 'Ogun', 'Ondo', 'Osun', 'Oyo',
    'Plateau', 'Rivers', 'Sokoto', 'Taraba', 'Yobe', 'Zamfara',
]

_STATE_VARIANTS = {
    'abuja': 'FCT',
    'fct abuja': 'FCT',
    'federal capital territory': 'FCT',
    'cross river state': 'Cross River',
    'akwa ibom state': 'Akwa Ibom',
    'rivers state': 'Rivers',
}
_STATE_LOWER = {s.lower(): s for s in NIGERIA_STATES}
_STATE_LOWER.update(_STATE_VARIANTS)


# ── LGA → State map ───────────────────────────────────────────────────────────
# Format: 'lowercase lga name': ('Canonical LGA', 'Canonical State')

_LGA_MAP = {
    # ── Plateau State (17 LGAs) ──
    'barkin ladi':      ('Barkin Ladi',     'Plateau'),
    'bassa':            ('Bassa',           'Plateau'),
    'bokkos':           ('Bokkos',          'Plateau'),
    'jos east':         ('Jos East',        'Plateau'),
    'jos north':        ('Jos North',       'Plateau'),
    'jos south':        ('Jos South',       'Plateau'),
    'kanam':            ('Kanam',           'Plateau'),
    'kanke':            ('Kanke',           'Plateau'),
    'langtang north':   ('Langtang North',  'Plateau'),
    'langtang south':   ('Langtang South',  'Plateau'),
    'mangu':            ('Mangu',           'Plateau'),
    'mikang':           ('Mikang',          'Plateau'),
    'pankshin':         ('Pankshin',        'Plateau'),
    "qua'an pan":       ("Qua'an Pan",      'Plateau'),
    'quaan pan':        ("Qua'an Pan",      'Plateau'),
    'quan pan':         ("Qua'an Pan",      'Plateau'),
    'riyom':            ('Riyom',           'Plateau'),
    'shendam':          ('Shendam',         'Plateau'),
    'wase':             ('Wase',            'Plateau'),

    # ── Kaduna State (23 LGAs) ──
    'birnin gwari':     ('Birnin Gwari',    'Kaduna'),
    'chikun':           ('Chikun',          'Kaduna'),
    'giwa':             ('Giwa',            'Kaduna'),
    'igabi':            ('Igabi',           'Kaduna'),
    'ikara':            ('Ikara',           'Kaduna'),
    'jaba':             ('Jaba',            'Kaduna'),
    "jema'a":           ("Jema'a",          'Kaduna'),
    'jemaa':            ("Jema'a",          'Kaduna'),
    'kachia':           ('Kachia',          'Kaduna'),
    'kaduna north':     ('Kaduna North',    'Kaduna'),
    'kaduna south':     ('Kaduna South',    'Kaduna'),
    'kagarko':          ('Kagarko',         'Kaduna'),
    'kajuru':           ('Kajuru',          'Kaduna'),
    'kaura':            ('Kaura',           'Kaduna'),
    'kauru':            ('Kauru',           'Kaduna'),
    'kubau':            ('Kubau',           'Kaduna'),
    'kudan':            ('Kudan',           'Kaduna'),
    'lere':             ('Lere',            'Kaduna'),
    'makarfi':          ('Makarfi',         'Kaduna'),
    'sabon gari':       ('Sabon Gari',      'Kaduna'),
    'sanga':            ('Sanga',           'Kaduna'),
    'soba':             ('Soba',            'Kaduna'),
    'zangon kataf':     ('Zangon Kataf',    'Kaduna'),
    'zaria':            ('Zaria',           'Kaduna'),

    # ── Benue State (23 LGAs) ──
    'ado':              ('Ado',             'Benue'),
    'agatu':            ('Agatu',           'Benue'),
    'apa':              ('Apa',             'Benue'),
    'buruku':           ('Buruku',          'Benue'),
    'gboko':            ('Gboko',           'Benue'),
    'guma':             ('Guma',            'Benue'),
    'gwer east':        ('Gwer East',       'Benue'),
    'gwer west':        ('Gwer West',       'Benue'),
    'katsina-ala':      ('Katsina-Ala',     'Benue'),
    'katsina ala':      ('Katsina-Ala',     'Benue'),
    'konshisha':        ('Konshisha',       'Benue'),
    'kwande':           ('Kwande',          'Benue'),
    'logo':             ('Logo',            'Benue'),
    'makurdi':          ('Makurdi',         'Benue'),
    'obi':              ('Obi',             'Benue'),
    'ogbadibo':         ('Ogbadibo',        'Benue'),
    'ohimini':          ('Ohimini',         'Benue'),
    'oju':              ('Oju',             'Benue'),
    'okpokwu':          ('Okpokwu',         'Benue'),
    'otukpo':           ('Otukpo',          'Benue'),
    'tarka':            ('Tarka',           'Benue'),
    'ukum':             ('Ukum',            'Benue'),
    'ushongo':          ('Ushongo',         'Benue'),
    'vandeikya':        ('Vandeikya',       'Benue'),

    # ── Nasarawa State (13 LGAs) ──
    'akwanga':          ('Akwanga',         'Nasarawa'),
    'awe':              ('Awe',             'Nasarawa'),
    'doma':             ('Doma',            'Nasarawa'),
    'karu':             ('Karu',            'Nasarawa'),
    'keana':            ('Keana',           'Nasarawa'),
    'keffi':            ('Keffi',           'Nasarawa'),
    'kokona':           ('Kokona',          'Nasarawa'),
    'lafia':            ('Lafia',           'Nasarawa'),
    'nasarawa':         ('Nasarawa',        'Nasarawa'),
    'nasarawa egon':    ('Nasarawa Egon',   'Nasarawa'),
    'obi nasarawa':     ('Obi',             'Nasarawa'),
    'toto':             ('Toto',            'Nasarawa'),
    'wamba':            ('Wamba',           'Nasarawa'),

    # ── Niger State (25 LGAs) ──
    'agaie':            ('Agaie',           'Niger'),
    'agwara':           ('Agwara',          'Niger'),
    'bida':             ('Bida',            'Niger'),
    'borgu':            ('Borgu',           'Niger'),
    'bosso':            ('Bosso',           'Niger'),
    'chanchaga':        ('Chanchaga',       'Niger'),
    'edati':            ('Edati',           'Niger'),
    'gbako':            ('Gbako',           'Niger'),
    'gurara':           ('Gurara',          'Niger'),
    'katcha':           ('Katcha',          'Niger'),
    'kontagora':        ('Kontagora',       'Niger'),
    'lapai':            ('Lapai',           'Niger'),
    'lavun':            ('Lavun',           'Niger'),
    'magama':           ('Magama',          'Niger'),
    'mariga':           ('Mariga',          'Niger'),
    'mashegu':          ('Mashegu',         'Niger'),
    'mokwa':            ('Mokwa',           'Niger'),
    'moya':             ('Moya',            'Niger'),
    'paikoro':          ('Paikoro',         'Niger'),
    'rafi':             ('Rafi',            'Niger'),
    'rijau':            ('Rijau',           'Niger'),
    'shiroro':          ('Shiroro',         'Niger'),
    'suleja':           ('Suleja',          'Niger'),
    'tafa':             ('Tafa',            'Niger'),
    'wushishi':         ('Wushishi',        'Niger'),

    # ── Taraba State (16 LGAs) ──
    'ardo-kola':        ('Ardo-Kola',       'Taraba'),
    'ardo kola':        ('Ardo-Kola',       'Taraba'),
    'bali':             ('Bali',            'Taraba'),
    'donga':            ('Donga',           'Taraba'),
    'gashaka':          ('Gashaka',         'Taraba'),
    'gassol':           ('Gassol',          'Taraba'),
    'ibi':              ('Ibi',             'Taraba'),
    'jalingo':          ('Jalingo',         'Taraba'),
    'karim lamido':     ('Karim Lamido',    'Taraba'),
    'kurmi':            ('Kurmi',           'Taraba'),
    'lau':              ('Lau',             'Taraba'),
    'sardauna':         ('Sardauna',        'Taraba'),
    'takum':            ('Takum',           'Taraba'),
    'ussa':             ('Ussa',            'Taraba'),
    'wukari':           ('Wukari',          'Taraba'),
    'yorro':            ('Yorro',           'Taraba'),
    'zing':             ('Zing',            'Taraba'),

    # ── Bauchi State (20 LGAs) ──
    'alkaleri':         ('Alkaleri',        'Bauchi'),
    'bauchi':           ('Bauchi',          'Bauchi'),
    'bogoro':           ('Bogoro',          'Bauchi'),
    'damban':           ('Damban',          'Bauchi'),
    'darazo':           ('Darazo',          'Bauchi'),
    'dass':             ('Dass',            'Bauchi'),
    'gamawa':           ('Gamawa',          'Bauchi'),
    'ganjuwa':          ('Ganjuwa',         'Bauchi'),
    'giade':            ('Giade',           'Bauchi'),
    "itas/gadau":       ("Itas/Gadau",      'Bauchi'),
    'itas gadau':       ("Itas/Gadau",      'Bauchi'),
    "jama'are":         ("Jama'are",        'Bauchi'),
    'jamaare':          ("Jama'are",        'Bauchi'),
    'katagum':          ('Katagum',         'Bauchi'),
    'kirfi':            ('Kirfi',           'Bauchi'),
    'misau':            ('Misau',           'Bauchi'),
    'ningi':            ('Ningi',           'Bauchi'),
    'shira':            ('Shira',           'Bauchi'),
    'tafawa balewa':    ('Tafawa Balewa',   'Bauchi'),
    'toro':             ('Toro',            'Bauchi'),
    'warji':            ('Warji',           'Bauchi'),
    'zaki':             ('Zaki',            'Bauchi'),

    # ── Adamawa State (21 LGAs) ──
    'demsa':            ('Demsa',           'Adamawa'),
    'fufure':           ('Fufure',          'Adamawa'),
    'ganye':            ('Ganye',           'Adamawa'),
    'gayuk':            ('Gayuk',           'Adamawa'),
    'gombi':            ('Gombi',           'Adamawa'),
    'grie':             ('Grie',            'Adamawa'),
    'hong':             ('Hong',            'Adamawa'),
    'jada':             ('Jada',            'Adamawa'),
    'lamurde':          ('Lamurde',         'Adamawa'),
    'madagali':         ('Madagali',        'Adamawa'),
    'maiha':            ('Maiha',           'Adamawa'),
    'mayo-belwa':       ('Mayo-Belwa',      'Adamawa'),
    'mayo belwa':       ('Mayo-Belwa',      'Adamawa'),
    'michika':          ('Michika',         'Adamawa'),
    'mubi north':       ('Mubi North',      'Adamawa'),
    'mubi south':       ('Mubi South',      'Adamawa'),
    'numan':            ('Numan',           'Adamawa'),
    'shelleng':         ('Shelleng',        'Adamawa'),
    'song':             ('Song',            'Adamawa'),
    'toungo':           ('Toungo',          'Adamawa'),
    'yola north':       ('Yola North',      'Adamawa'),
    'yola south':       ('Yola South',      'Adamawa'),

    # ── Gombe State (11 LGAs) ──
    'akko':             ('Akko',            'Gombe'),
    'balanga':          ('Balanga',         'Gombe'),
    'billiri':          ('Billiri',         'Gombe'),
    'dukku':            ('Dukku',           'Gombe'),
    'funakaye':         ('Funakaye',        'Gombe'),
    'gombe':            ('Gombe',           'Gombe'),
    'kaltungo':         ('Kaltungo',        'Gombe'),
    'kwami':            ('Kwami',           'Gombe'),
    'nafada':           ('Nafada',          'Gombe'),
    'shomgom':          ('Shomgom',         'Gombe'),
    'yamaltu/deba':     ('Yamaltu/Deba',    'Gombe'),
    'yamaltu deba':     ('Yamaltu/Deba',    'Gombe'),

    # ── Kano State (44 LGAs — selected key ones) ──
    'ajingi':           ('Ajingi',          'Kano'),
    'albasu':           ('Albasu',          'Kano'),
    'bagwai':           ('Bagwai',          'Kano'),
    'bebeji':           ('Bebeji',          'Kano'),
    'bichi':            ('Bichi',           'Kano'),
    'bunkure':          ('Bunkure',         'Kano'),
    'dala':             ('Dala',            'Kano'),
    'dambatta':         ('Dambatta',        'Kano'),
    'dawakin kudu':     ('Dawakin Kudu',    'Kano'),
    'dawakin tofa':     ('Dawakin Tofa',    'Kano'),
    'doguwa':           ('Doguwa',          'Kano'),
    'fagge':            ('Fagge',           'Kano'),
    'gabasawa':         ('Gabasawa',        'Kano'),
    'garko':            ('Garko',           'Kano'),
    'garun mallam':     ('Garun Mallam',    'Kano'),
    'gaya':             ('Gaya',            'Kano'),
    'gezawa':           ('Gezawa',          'Kano'),
    'gwale':            ('Gwale',           'Kano'),
    'gwarzo':           ('Gwarzo',          'Kano'),
    'kabo':             ('Kabo',            'Kano'),
    'kano municipal':   ('Kano Municipal',  'Kano'),
    'karaye':           ('Karaye',          'Kano'),
    'kibiya':           ('Kibiya',          'Kano'),
    'kiru':             ('Kiru',            'Kano'),
    'kumbotso':         ('Kumbotso',        'Kano'),
    'kunchi':           ('Kunchi',          'Kano'),
    'kura':             ('Kura',            'Kano'),
    'madobi':           ('Madobi',          'Kano'),
    'makoda':           ('Makoda',          'Kano'),
    'minjibir':         ('Minjibir',        'Kano'),
    'nasarawa kano':    ('Nasarawa',        'Kano'),
    'rano':             ('Rano',            'Kano'),
    'rimin gado':       ('Rimin Gado',      'Kano'),
    'rogo':             ('Rogo',            'Kano'),
    'shanono':          ('Shanono',         'Kano'),
    'sumaila':          ('Sumaila',         'Kano'),
    'takai':            ('Takai',           'Kano'),
    'tarauni':          ('Tarauni',         'Kano'),
    'tofa':             ('Tofa',            'Kano'),
    'tsanyawa':         ('Tsanyawa',        'Kano'),
    'tudun wada':       ('Tudun Wada',      'Kano'),
    'ungogo':           ('Ungogo',          'Kano'),
    'warawa':           ('Warawa',          'Kano'),
    'wudil':            ('Wudil',           'Kano'),

    # ── FCT Abuja (6 area councils) ──
    'abaji':            ('Abaji',           'FCT'),
    'abuja municipal':  ('Abuja Municipal', 'FCT'),
    'amac':             ('Abuja Municipal', 'FCT'),
    'bwari':            ('Bwari',           'FCT'),
    'gwagwalada':       ('Gwagwalada',      'FCT'),
    'kuje':             ('Kuje',            'FCT'),
    'kwali':            ('Kwali',           'FCT'),
}

# Pre-built lowercase key list for fuzzy matching
_LGA_KEYS = list(_LGA_MAP.keys())


# ── Commodity normalisation map ───────────────────────────────────────────────

_COMMODITY_MAP = {
    # Soybeans
    'soy':          'Soybeans',
    'soya':         'Soybeans',
    'soybean':      'Soybeans',
    'soy bean':     'Soybeans',
    'soy beans':    'Soybeans',
    'soybeans':     'Soybeans',
    'soya beans':   'Soybeans',
    'soya bean':    'Soybeans',
    'soyabeans':    'Soybeans',
    'soyabean':     'Soybeans',
    # Cocoa
    'cocoa':        'Cocoa',
    'cacao':        'Cocoa',
    'kakao':        'Cocoa',
    # Coffee
    'coffee':       'Coffee',
    'coffea':       'Coffee',
    # Oil Palm
    'oil palm':     'Oil Palm',
    'palm oil':     'Oil Palm',
    'palm':         'Oil Palm',
    'palm tree':    'Oil Palm',
    'elaeis':       'Oil Palm',
    # Rubber
    'rubber':       'Rubber',
    'natural rubber': 'Rubber',
    'hevea':        'Rubber',
    # Cattle
    'cattle':       'Cattle',
    'beef':         'Cattle',
    'cow':          'Cattle',
    'cows':         'Cattle',
    'bovine':       'Cattle',
    # Maize
    'maize':        'Maize',
    'corn':         'Maize',
    'sweet corn':   'Maize',
    # Groundnut
    'groundnut':    'Groundnut',
    'groundnuts':   'Groundnut',
    'peanut':       'Groundnut',
    'peanuts':      'Groundnut',
    # Cassava
    'cassava':      'Cassava',
    'yuca':         'Cassava',
    # Yam
    'yam':          'Yam',
    'yams':         'Yam',
    # Rice
    'rice':         'Rice',
    # Sesame
    'sesame':       'Sesame',
    'beniseed':     'Sesame',
    'beni seed':    'Sesame',
    'sesame seed':  'Sesame',
    # Sorghum
    'sorghum':      'Sorghum',
    'guinea corn':  'Sorghum',
    'guinea corn/dawa': 'Sorghum',
    'dawa':         'Sorghum',
    # Millet
    'millet':       'Millet',
    'pearl millet': 'Millet',
    # Shea
    'shea':         'Shea',
    'shea butter':  'Shea',
    'shea nut':     'Shea',
    # Timber / Wood
    'wood':         'Wood',
    'timber':       'Wood',
    'logs':         'Wood',
}


def normalise_commodity(raw):
    """
    Return canonical commodity name from any common variant.
    Falls back to title-case of the original if not recognised.
    """
    if not raw:
        return raw
    key = raw.strip().lower()
    return _COMMODITY_MAP.get(key, raw.strip().title())


# ── EUDR Annex I commodity scope ──────────────────────────────────────────────
# EU Regulation 2023/1115, Annex I: commodities whose production must not
# contribute to deforestation or forest degradation after 31 Dec 2020.
# This set uses canonical names as returned by normalise_commodity().
EUDR_ANNEX_I = {
    'Cattle',
    'Cocoa',
    'Coffee',
    'Palm Oil',
    'Soybeans',
    'Wood',
    'Rubber',
}


def is_eudr_commodity(commodity):
    """
    Return True if the canonical commodity name is covered by EUDR Annex I.
    Pass the result of normalise_commodity() — not the raw string.
    """
    return bool(commodity) and commodity in EUDR_ANNEX_I


def canonicalise_lga_state(lga_raw, state_raw=''):
    """
    Return (canonical_lga, canonical_state) for a Nigerian LGA/State pair.

    Resolution order:
    1. Exact match on LGA in _LGA_MAP → returns LGA + auto-fills state
    2. Fuzzy match on LGA (cutoff 0.75) → same
    3. Exact match on state in _STATE_LOWER (LGA title-cased as-is)
    4. Fuzzy match on state
    5. Return (title-case LGA, title-case state) unchanged

    Empty string is returned unchanged so callers can distinguish
    "we tried and failed" from "nothing was supplied".
    """
    lga_key   = lga_raw.strip().lower()   if lga_raw   else ''
    state_key = state_raw.strip().lower() if state_raw else ''

    # 1. Exact LGA match
    if lga_key and lga_key in _LGA_MAP:
        canonical_lga, canonical_state = _LGA_MAP[lga_key]
        return canonical_lga, canonical_state

    # 2. Fuzzy LGA match
    if lga_key:
        matches = difflib.get_close_matches(lga_key, _LGA_KEYS, n=1, cutoff=0.75)
        if matches:
            canonical_lga, canonical_state = _LGA_MAP[matches[0]]
            return canonical_lga, canonical_state

    # 3. Exact state match
    canonical_state = _STATE_LOWER.get(state_key, '')
    if not canonical_state and state_key:
        # 4. Fuzzy state match
        state_matches = difflib.get_close_matches(state_key, list(_STATE_LOWER.keys()), n=1, cutoff=0.75)
        if state_matches:
            canonical_state = _STATE_LOWER[state_matches[0]]

    # 5. Fall back to title-case originals
    out_lga   = lga_raw.strip().title()   if lga_raw   else ''
    out_state = canonical_state or (state_raw.strip().title() if state_raw else '')
    return out_lga, out_state
