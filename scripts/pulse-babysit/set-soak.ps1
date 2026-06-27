param(
    [double]$Hours,
    [int]$Minutes = 120
)
$ErrorActionPreference = "Stop"
$statePath = Join-Path $PSScriptRoot "state.json"
$durMinutes = if ($PSBoundParameters.ContainsKey('Hours')) { [int][math]::Round($Hours * 60.0) } else { $Minutes }
$durHours = [math]::Round($durMinutes / 60.0, 4)
python -c @"
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
p = Path(r'$statePath')
st = json.loads(p.read_text(encoding='utf-8-sig'))
now = datetime.now(timezone.utc)
st['soak_hours'] = $durHours
st['soak_minutes'] = $durMinutes
st['phase'] = 'soak'
st['deployed_at'] = now.isoformat()
st['soak_until'] = (now + timedelta(minutes=$durMinutes)).isoformat()
p.write_text(json.dumps(st, indent=2) + '\n', encoding='utf-8')
print(f'Soak set: {$durMinutes} min until {st[\"soak_until\"]} UTC')
"@