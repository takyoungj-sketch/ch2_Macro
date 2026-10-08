"""Pure validation helpers shared by the offline Cheongju experiments."""
from datetime import date


def snapshot_cutoff(parcels):
    """Only release a whole candidate universe after both sources are observed.

    Missing or malformed dates fail closed rather than shrinking the universe
    and accidentally turning multiple candidates into a unique candidate.
    """
    dates = []
    for row in parcels.values():
        for field in ('trait_asof', 'plan_asof'):
            value = row.get(field, '')
            try:
                dates.append(date.fromisoformat(value).isoformat())
            except (ValueError, TypeError):
                return None
    return max(dates) if dates else None


def encode_category(train, test, minimum=30):
    """Pool rare levels; explicitly report unseen fallback when no pool exists."""
    train = train.fillna('UNKNOWN').replace({'': 'UNKNOWN', '지정되지않음': 'UNKNOWN'}).astype(str)
    test = test.fillna('UNKNOWN').replace({'': 'UNKNOWN', '지정되지않음': 'UNKNOWN'}).astype(str)
    counts = train.value_counts()
    keep = set(counts[counts >= minimum].index)
    pooled = train.where(train.isin(keep), 'OTHER')
    fallback = 'OTHER' if 'OTHER' in set(pooled) else pooled.value_counts().idxmax()
    unknown = ~test.isin(keep)
    encoded = test.where(~unknown, fallback)
    audit = {'unseen': int((~test.isin(set(train))).sum()),
             'fallback_rows': int(unknown.sum()), 'fallback_level': fallback,
             'fallback_policy': 'training_rare_pool' if fallback == 'OTHER' else 'training_mode_no_estimable_pool'}
    return pooled, encoded, audit
