"""
Farmer tabular import pipeline.

Phase 1: surface every transformation, loud-fail on unparseable values,
         write an auditable FarmerImportLog.
Phase 2: XLSX upload — parse_tabular_file() routes CSV and XLSX through the
         same validate_farmer_row() pipeline unchanged.
Phase 3 (future): column-mapping wizard.
"""
import csv
import datetime
import io
import re

from django.db import transaction

from .models import Farmer, FarmerImportLog, _normalise_ng_phone


MAX_FARMER_IMPORT_BYTES = 5 * 1024 * 1024

ENCODING_CHAIN = ('utf-8', 'utf-8-sig', 'cp1252', 'latin-1')

CONSENT_DATE_FORMATS = (
    '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y',
    '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y',
)

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

# XLSX files are ZIP archives and always start with this magic sequence.
XLSX_MAGIC = b'PK\x03\x04'


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


def _parse_xlsx(raw_bytes):
    """
    Parse an XLSX file into a list of row dicts (first row = headers).
    Returns (rows, sheet_warning_or_None).
    Uses read_only + data_only mode for memory safety on large files.
    """
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), read_only=True, data_only=True)
    sheet_names = wb.sheetnames

    sheet_warning = None
    if len(sheet_names) > 1:
        preview = ', '.join(sheet_names[:3]) + ('…' if len(sheet_names) > 3 else '')
        sheet_warning = (
            f"Your file has {len(sheet_names)} sheets ({preview}). "
            f"We imported the first sheet ({sheet_names[0]!r}). "
            f"If your data is on a different sheet, move it to the first position and re-upload."
        )

    ws = wb.worksheets[0]
    all_rows = list(ws.rows)
    wb.close()

    if not all_rows:
        return [], sheet_warning

    headers = [
        str(cell.value).strip() if cell.value is not None else ''
        for cell in all_rows[0]
    ]

    result = []
    for row in all_rows[1:]:
        row_dict = {}
        for header, cell in zip(headers, row):
            if header:
                row_dict[header] = str(cell.value).strip() if cell.value is not None else ''
        result.append(row_dict)

    return result, sheet_warning


def parse_tabular_file(raw_bytes, content_type, filename):
    """
    Detect format from magic bytes and file extension; parse into row dicts.

    Returns (rows, encoding, decode_warning, sheet_warning):
      rows          list[dict]   one dict per data row (header stripped)
      encoding      str          e.g. 'utf-8', 'cp1252', or 'xlsx'
      decode_warning str|None    set when CSV encoding fallback triggered
      sheet_warning  str|None    set when XLSX file has multiple sheets

    Raises ValueError for unrecognised or mismatched format.
    Raises UnicodeDecodeError if CSV bytes cannot be decoded by any chain member.
    """
    ext = ''
    if filename and '.' in filename:
        ext = filename.lower().rsplit('.', 1)[-1]

    if ext not in ('csv', 'xlsx', ''):
        raise ValueError(
            f"Unsupported file type (.{ext}). Please upload a .csv or .xlsx file."
        )

    magic = raw_bytes[:4] if len(raw_bytes) >= 4 else raw_bytes

    if magic == XLSX_MAGIC:
        if ext == 'csv':
            raise ValueError(
                "The file looks like an Excel spreadsheet but has a .csv extension. "
                "Open it in Excel, save as .xlsx, and re-upload."
            )
        rows, sheet_warning = _parse_xlsx(raw_bytes)
        return rows, 'xlsx', None, sheet_warning

    # CSV path — let decode_csv_bytes surface encoding issues clearly.
    text, encoding, decode_warning = decode_csv_bytes(raw_bytes)
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    return rows, encoding, decode_warning, None


def _parse_consent_date(raw):
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
    if not raw:
        return ''
    return re.sub(r'[^A-Z0-9]', '', raw.strip().upper())


def validate_farmer_row(raw_row, row_num):
    """
    Pure function — no DB access. Takes a row dict, returns a result dict.

    Result keys:
      row              int            1-based row number (header = 1)
      raw              dict           echo of every field's raw input
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

    first_name = raw['first_name']
    if not first_name:
        errors.append({
            'row': row_num, 'field': 'first_name', 'value': '',
            'reason': 'first_name is required',
        })

    last_name = raw['last_name']

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
        gender = ''

    phone_raw  = raw['phone']
    phone_norm = _normalise_ng_phone(phone_raw) if phone_raw else ''
    if phone_raw and phone_norm and phone_norm != phone_raw:
        transformations.append({
            'row': row_num, 'farmer': f"{first_name} {last_name}".strip(),
            'field': 'phone', 'from': phone_raw, 'to': phone_norm,
            'reason': 'e164_normalisation', 'severity': 'info',
            'ts': _utc_now_iso(),
        })

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


def run_farmer_import(company, file_bytes, filename, content_type='', uploaded_by=None):
    """
    Orchestrator. Accepts CSV or XLSX bytes. Returns a result dict and
    persists a FarmerImportLog row. Caller (the view) handles HTTP.

    Result dict keys:
      total, created, auto_corrected, duplicates, errors, warning_count,
      error_detail, warning_detail, transformation_log,
      encoding, decode_warning, sheet_warning, log_id
    """
    rows, encoding, decode_warning, sheet_warning = parse_tabular_file(
        file_bytes, content_type, filename
    )

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

    # File-level warnings go in first so they appear at the top of the warning table.
    if sheet_warning:
        warning_detail.append({
            'row': 0, 'field': 'sheet_selection', 'value': '',
            'reason': sheet_warning,
        })
    if decode_warning:
        warning_detail.append({
            'row': 1, 'field': 'file_encoding', 'value': encoding,
            'reason': decode_warning,
        })

    batch_nins      = set()
    batch_name_keys = set()

    row_num = 1  # header row = 1; first data row = 2
    for raw_row in rows:
        row_num += 1
        result = validate_farmer_row(raw_row, row_num)

        if result['errors']:
            reasons = '; '.join(e['reason'] for e in result['errors'])
            error_detail.append({**result['raw'], 'row': row_num, 'error_reason': reasons})
            continue

        f = result['fields']

        if f['nin']:
            if f['nin'] in existing_nins or f['nin'] in batch_nins:
                duplicate_count += 1
                continue
            batch_nins.add(f['nin'])

        if f['first_name'] and f['village'] and f['lga']:
            key = (f['first_name'].lower(), f['last_name'].lower(),
                   f['village'].lower(), f['lga'].lower())
            if key in existing_name_keys or key in batch_name_keys:
                duplicate_count += 1
                continue
            batch_name_keys.add(key)

        if result['transformations']:
            transformation_log.extend(result['transformations'])
            auto_corrected += 1
        if result['warnings']:
            warning_detail.extend(result['warnings'])
            rows_with_warnings += 1

        to_create.append(Farmer(company=company, **f))

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
        'sheet_warning':      sheet_warning,
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
