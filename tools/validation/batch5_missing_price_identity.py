"""Read-only source check for the naturally unpriced real-panel player IDs."""
import asyncio
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.core.data_platform.provider_activation import (
    FANTASYCALC_URL, DYNASTYPROCESS_IDS_URL, DYNASTYPROCESS_VALUES_URL,
)


async def verify():
    async with httpx.AsyncClient(timeout=60) as client:
        urls = ['https://api.sleeper.app/v1/players/nfl', FANTASYCALC_URL,
                DYNASTYPROCESS_IDS_URL, DYNASTYPROCESS_VALUES_URL]
        responses = await asyncio.gather(*(client.get(url) for url in urls))
        for response in responses:
            response.raise_for_status()
        catalog, fc = responses[0].json(), responses[1].json()
        ids = list(csv.DictReader(io.StringIO(responses[2].text)))
        values = list(csv.DictReader(io.StringIO(responses[3].text)))
        rows = []
        for pid in ('11619', '10871'):
            player = catalog.get(pid) or {}
            name = player.get('full_name') or ' '.join(filter(None, (player.get('first_name'), player.get('last_name'))))
            crosswalk = [r for r in ids if str(r.get('sleeper_id')) == pid]
            fps = {str(r.get('fantasypros_id')) for r in crosswalk}
            rows.append({'player_id': pid, 'source_name': name, 'source_position': player.get('position'),
                         'catalog_identity_exists': bool(player),
                         'fantasycalc_id_matches': [r for r in fc if str((r.get('player') or {}).get('sleeperId')) == pid],
                         'fantasycalc_name_matches': [r for r in fc if str((r.get('player') or {}).get('name') or '').casefold() == name.casefold()],
                         'dp_identity_rows': crosswalk,
                         'dp_value_matches': [r for r in values if str(r.get('fp_id')) in fps or str(r.get('player') or '').casefold() == name.casefold()]})
        return {'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'source_sha256': {url: hashlib.sha256(r.content).hexdigest() for url, r in zip(urls, responses)},
                'scope': 'public-source identity/quote coverage only; no canonical writes', 'rows': rows}


if __name__ == '__main__':
    result = asyncio.run(verify())
    Path('.validation/batch5-real-missing-price-identity.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
