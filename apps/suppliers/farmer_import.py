"""
Farmer CSV import pipeline.

Phase 1 of the farmer-import redesign: surface every transformation,
loud-fail on unparseable values, and write an auditable FarmerImportLog.

Future phases extend this module with an XLSX parser layer (Phase 2)
and a column-mapping wizard (Phase 3).
"""
import csv
import datetime
import io
import re

from django.db import transaction

from .models import Farmer, FarmerImportLog, _normalise_ng_phone


# Hard cap on uploaded file size. Even a cooperative with 25 000 farmers
# fits comfortably under 5 MB; anything larger is almost certainly a wrong
# file. Surfaced as a friendly error instead of Django's default 2.5 MB
# DataUploadHandler exception.
MAX_FARMER_IMPORT_BYTES = 5 * 1024 * 1024

# Encoding fallback chain. UTF-8 covers modern exports; UTF-8-sig handles
# Excel's BOM; CP1252 / latin-1 cover legacy Windows spreadsheets that
# crop up on co-op laptops.
ENCODING_CHAIN = ('utf-8', 'utf-8-sig', 'cp1252', 'latin-1')

# Date formats accepted for consent_date. Matches the farm importer's
# _parse_mapping_date list so operators learn one set of conventions.
CONSENT_DATE_FORMATS = (
    '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y',
    '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y',
)

# Column aliases: AgriOps template name + SW Maps export name.
FIELD_ALIASES = {
    'first_name':   ('first_name', 'First Name', 'first name'),
    'last_name':    ('last_name',  'Last Name',  'last name'),
    'gender':       ('gender',     'Gender'),
    'phone':        ('phone',      'Phone Number', 'phone_number', 'phone number'),
    'village':      ('village',    'Village'),
    'lga':          ('lga',        'LGA'),
    'nin':          ('nin',        'NIN'),
    'crops':        ('crops',      'Commodity', 'commodity'),
    'consent_date': ('consent_date', 'Consent Date', 'consent date'),
}


def _pick(row, field):
    for alias in FIELD_ALIASES[field]:
        if alias in row and row[alias] is not None:
            return str(row[alias]).strip()
    return ''


def _utc_now_iso():
    return datetime.datetime.utcnow().isoformat() + 'Z'


def decode_csv_bytes(raw_bytes):
    """
    Try each encoding in order. Returns (text, encoding_used, warning_or_None).

    A warning is returned when we fell back past UTF-8-sig — the operator
    should know their file wasn't standard UTF-8 in case they re-export it.
    Raises UnicodeDecodeError only if every encoding in the chain fails.
    """
    last_error = None
    for enc in ENCODING_CHAIN:
        try:
            text = raw_bytes.decode(enc)
            warning = None
            if enc in ('cp1252', 'latin-1'):
                warning = (
                    f"File was read as {enc.upper()} (Windows / legacy encoding). "
                    f"For cleanest results, re-save your spreadsheet as UTF-8 CSV."
                )
            return text, enc, warning
        except UnicodeDecodeError as e:
            last_error = e
            continue
    raise last_error  # noqa — every encoding failed


def _parse_consent_date(raw):
    """
    Try every accepted format. Returns (date_or_None, error_message_or_None).
    Empty input returns (None, None) — not an error, just absent.
    """
    if not raw:
        return None, None
    for fmt in CONSENT_DATE_FORMATS:
        try:
            return datetime.datetime.strptime(raw, fmt).date(), None
        except ValueError:
            continue
    return None, (
        f"consent_date '{raw}' is not a recognised date format "
        f"(expected YYYY-MM-DD, DD/MM/YYYY, or similar)"
    )


def _clean_nin(raw):
    """Mirror Farmer.save()'s NIN normalisation so we can surface the diff."""
    if not raw:
        return ''
    return re.sub(r'[^A-Z0-9]', '', raw.strip().upper())


def validate_farmer_row(raw_row, row_num):
    """
    Pure function — no DB access. Takes a CSV row dict, returns a result
    dict the orchestrator can act on.

    Result keys:
      row              int            CSV row number (1-based, header is row 1)
      raw              dict           echo of every field's raw input (for error CSV)
      fields           dict           normalised values, ready for Farmer(**)
      transformations  list of dicts  field-level normalisations that changed the value
      warnings         list of dicts  non-fatal issues (e.g. NIN too short)
      errors           list of dicts  fatal issues — non-empty means reject this row
    """
    raw = {
        'first_name':   _pick(raw_row, 'first_name'),
        'last_name':    _pick(raw_row, 'last_name'),
        'gender':       _pick(raw_row, 'gender'),
        'phone':        _pick(raw_row, 'phone'),
        'village':      _pick(raw_row, 'village'),
        'lga':          _pick(raw_row, 'lga'),
        'nin':          _pick(raw_row, 'nin'),
        'crops':        _pick(raw_row, 'crops'),
        'consent_date': _pick(raw_row, 'consent_date'),
    }

    transformations = []
    warnings        = []
    errors          = []

    # ── first_name (required) ────────────────────────────────────────────────
    first_name = raw['first_name']
    if not first_name:
        errors.append({
            'row': row_num, 'field': 'first_name', 'value': '',
            'reason': 'first_name is required',
        })

    last_name = raw['last_name']

    # ── gender (M/F only — model dropped O) ──────────────────────────────────
    gender_raw = raw['gender']
    gender     = gender_raw.upper()
    if gender_raw and gender not in ('M', 'F'):
        errors.append({
            'row': row_num, 'field': 'gender', 'value': gender_raw,
            'reason': (
                f"gender '{gender_raw}' is not recognised "
                f"(expected M, F, or blank)"
            ),
        })
        gender = ''  # keep blank in fields so the dict is still safe to read

    # ── phone (E.164 normalisation surfaced as transformation) ───────────────
    phone_raw  = raw['phone']
    phone_norm = _normalise_ng_phone(phone_raw) if phone_raw else ''
    if phone_raw and phone_norm and phone_norm != phone_raw:
        transformations.append({
            'row': row_num, 'farmer': f"{first_name} {last_name}".strip(),
            'field': 'phone', 'from': phone_raw, 'to': phone_norm,
            'reason': 'e164_normalisation', 'severity': 'info',
            'ts': _utc_now_iso(),
        })

    # ── NIN (strip + uppercase; length warning) ──────────────────────────────
    nin_raw  = raw['nin']
    nin_norm = _clean_nin(nin_raw)
    if nin_raw and nin_norm != nin_raw:
        transformations.append({
            'row': row_num, 'farmer': f"{first_name} {last_name}".strip(),
            'field': 'nin', 'from': nin_raw, 'to': nin_norm,
            'reason': 'strip_non_alphanumeric', 'severity': 'info',
            'ts': _utc_now_iso(),
        })
    if nin_norm and len(nin_norm) != 11:
        warnings.append({
            'row': row_num, 'farmer': f"{first_name} {last_name}".strip(),
            'field': 'nin', 'value': nin_norm,
            'reason': f"NIN is {len(nin_norm)} characters (expected 11) — verify",
        })

    # ── consent_date (loud-fail on unparseable) ──────────────────────────────
    consent_raw         = raw['consent_date']
    consent_date, c_err = _parse_consent_date(consent_raw)
    if c_err:
        errors.append({
            'row': row_num, 'field': 'consent_date', 'value': consent_raw,
            'reason': c_err,
        })

    fields = {
        'first_name':    first_name,
        'last_name':     last_name,
        'gender':        gender,
        'phone':         phone_norm,
        'village':       raw['village'],
        'lga':           raw['lga'],
        'nin':           nin_norm,
        'crops':         raw['crops'],
        'consent_given': bool(consent_date),
        'consent_date':  consent_date,
    }

    return {
        'row':             row_num,
        'raw':             raw,
        'fields':          fields,
        'transformations': transformations,
        'warnings':        warnings,
        'errors':          errors,
    }


def run_farmer_csv_import(company, file_bytes, filename, uploaded_by=None):
    """
    Orchestrator. Takes the uploaded bytes, returns a result dict and
    persists a FarmerImportLog row. Caller (the view) handles HTTP.

    Result dict:
      total           int    rows scanned (excluding header)
      created         int    rows that produced a Farmer (includes auto-corrected)
      auto_corrected  int    subset of created where at least one transformation fired
      duplicates      int    rows that matched an existing farmer (NIN or name+village+LGA)
      errors          int    rows rejected (sum of len(errors) over rejected rows)
      warning_count   int    rows that carry at least one warning
      error_detail        list  echo of rejected raw rows + reason strings (downloadable as CSV)
      warning_detail      list  per-row warning entries
      transformation_log  list  per-row transformation entries
      encoding            str   which encoding decoded the file
      decode_warning      str   set when fallback past UTF-8-sig triggered
    """
    text, encoding, decode_warning = decode_csv_bytes(file_bytes)
    reader = csv.DictReader(io.StringIO(text))

    # Pre-load existing NINs + name keys so dedup is one SELECT, not N
    existing_nins = set(
        Farmer.objects.filter(company=company)
        .exclude(nin='')
        .values_list('nin', flat=True)
    )
    existing_name_keys = set(
        (f['first_name'].lower(), (f['last_name'] or '').lower(),
         (f['village'] or '').lower(), (f['lga'] or '').lower())
        for f in Farmer.objects.filter(company=company)
        .values('first_name', 'last_name', 'village', 'lga')
    )

    to_create          = []
    error_detail       = []
    warning_detail     = []
    transformation_log = []
    duplicate_count    = 0
    auto_corrected     = 0
    rows_with_warnings = 0

    # Intra-batch dedup so the same row pasted twice doesn't slip through
    batch_nins      = set()
    batch_name_keys = set()

    row_num = 1  # header is row 1; first data row is 2
    for raw_row in reader:
        row_num += 1
        result = validate_farmer_row(raw_row, row_num)

        if decode_warning and row_num == 2:
            # Attach the decode warning to the first data row so it appears
            # alongside per-row warnings in the result UI.
            warning_detail.append({
                'row': 1, 'field': 'file_encoding', 'value': encoding,
                'reason': decode_warning,
            })

        # Rejected — collect raw + reason, skip
        if result['errors']:
            reasons = '; '.join(e['reason'] for e in result['errors'])
            error_detail.append({**result['raw'], 'row': row_num, 'error_reason': reasons})
            continue

        f = result['fields']

        # NIN dedup (DB + intra-batch)
        if f['nin']:
            if f['nin'] in existing_nins or f['nin'] in batch_nins:
                duplicate_count += 1
                continue
            batch_nins.add(f['nin'])

        # Name+village+LGA dedup (DB + intra-batch)
        if f['first_name'] and f['village'] and f['lga']:
            key = (f['first_name'].lower(), f['last_name'].lower(),
                   f['village'].lower(), f['lga'].lower())
            if key in existing_name_keys or key in batch_name_keys:
                duplicate_count += 1
                continue
            batch_name_keys.add(key)

        # Survivor — record transformations + warnings, queue for creation
        if result['transformations']:
            transformation_log.extend(result['transformations'])
            auto_corrected += 1
        if result['warnings']:
            warning_detail.extend(result['warnings'])
            rows_with_warnings += 1

        to_create.append(Farmer(company=company, **f))

    # Atomic bulk-create — partial commits would defeat the rollback story
    with transaction.atomic():
        Farmer.objects.bulk_create(to_create, batch_size=100)
    created_count = len(to_create)

    result_dict = {
        'total':              row_num - 1,
        'created':            created_count,
        'auto_corrected':     auto_corrected,
        'duplicates':         duplicate_count,
        'errors':             len(error_detail),
        'warning_count':      rows_with_warnings,
        'error_detail':       error_detail,
        'warning_detail':     warning_detail,
        'transformation_log': transformation_log,
        'encoding':           encoding,
        'decode_warning':     decode_warning,
    }

    log = FarmerImportLog.objects.create(
        company=company,
        uploaded_by=uploaded_by,
        filename=filename[:255] if filename else '',
        total=result_dict['total'],
        created=created_count,
        duplicates=duplicate_count,
        errors=len(error_detail),
        warning_count=rows_with_warnings,
        auto_corrected=auto_corrected,
        error_detail=error_detail,
        warning_detail=warning_detail,
        transformation_log=transformation_log,
    )
    result_dict['log_id'] = log.pk
    return result_dict
