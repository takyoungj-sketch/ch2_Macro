from app.rent.sale_join import JOIN_ASSETS, sale_join


class _Conn:
    def __init__(self, tables: set[str], map_row=None, as_of=None, mart=None):
        self.tables = tables
        self.map_row = map_row
        self.as_of = as_of
        self.mart = mart

    def execute(self, stmt, params=None):
        sql = str(stmt).lower()
        if "to_regclass" in sql:
            name = (params or {}).get("t", "")
            return _Rows([{"ok": name in self.tables}])
        if "rent_sale_building_map" in sql:
            return _Rows([self.map_row] if self.map_row else [])
        if "max(as_of_month)" in sql:
            return _Scalar(self.as_of)
        if "rent_building_stats" in sql:
            return _Rows([self.mart] if self.mart else [])
        return _Rows([])


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _Scalar:
    def __init__(self, v):
        self._v = v

    def scalar(self):
        return self._v

    def mappings(self):
        return _Rows([])


class _Db:
    def __init__(self, conn: _Conn):
        self._conn = conn

    def connection(self):
        return self._conn


def test_presale_out_of_scope():
    out = sale_join(_Db(_Conn(set())), sale_building_key="x" * 64, asset_type="presale", window_years=5)
    assert out.joined is False
    assert out.reason == "asset_not_in_scope"


def test_map_missing():
    out = sale_join(_Db(_Conn(set())), sale_building_key="a" * 64, asset_type="apartment", window_years=5)
    assert out.joined is False
    assert out.reason == "map_missing"


def test_no_join_when_map_empty():
    conn = _Conn({"public.rent_sale_building_map"})
    out = sale_join(_Db(conn), sale_building_key="a" * 64, asset_type="apartment", window_years=5)
    assert out.joined is False
    assert out.reason == "no_join"


def test_join_assets():
    assert JOIN_ASSETS == ("apartment", "rowhouse", "officetel")
