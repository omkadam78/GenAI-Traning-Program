# FasalBima Sathi — Day 2 and Day 3 files

## Included
- `data/sample_records.py`: 20 starter PMFBY records with official URLs.
- `app/records.py`: load, search, count and ID lookup functions.
- `app/cli.py`: command-line interface.
- `app/ingest.py`: validation and JSON export.
- `app/models.py`: typed `Record` dataclass.
- `app/fetch.py`: downloads three official source pages/PDFs.
- `tests/test_records.py`: basic assertions.

## Accuracy warning
This is a learning dataset, not legal or claim-decision advice. The PMFBY FAQ contains historical entries (including a Kharif 2016 deadline); that historical date is explicitly marked and must not be used as a current deadline. Premium rates, notified crops, claim windows and procedures must be checked against the current state/season notification and latest applicable guidelines.

## Windows PowerShell setup
```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

## Run in syllabus order
```powershell
python -m data.sample_records
python -m app.cli
python -m app.ingest
python tests/test_records.py
python -m app.fetch
```

Convert dictionaries to dataclass objects:
```python
from app.records import load_records
from app.models import Record

objects = [Record.from_dict(row) for row in load_records()]
print(objects[0])
```

Raw downloads are ignored by Git because PDFs may be large. Commit messages:
- `day-02: sample records and keyword search`
- `day-02: functions and project layout`
- `day-03: ingest real data`
- `day-03: dataclass model and data download`
