"""rent 마트·원장 공통 SQL 조각."""


def building_key_sql(alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    return f"""
COALESCE(
  NULLIF(btrim({p}building_key::text), ''),
  encode(
    sha256(
      convert_to(
        concat_ws(
          '|',
          coalesce({p}asset_type, ''),
          coalesce({p}addr1, ''),
          coalesce({p}addr2, ''),
          coalesce({p}addr3, ''),
          coalesce({p}lot_number, ''),
          coalesce({p}road_name, '')
        ),
        'UTF8'
      )
    ),
    'hex'
  )
)
""".strip()
