import csv

from scripts.data import load_to_postgres
from app.models.city import City
from app.models.destination import Destination
from app.models.place import Place
from app.models.restaurant import Restaurant


def test_missing_restaurant_dataset_is_skipped_without_clearing_rows(
    tmp_path, monkeypatch, caplog
):
    monkeypatch.setattr(load_to_postgres, "PROCESSED_DIR", tmp_path)
    caplog.set_level("INFO", logger=load_to_postgres.__name__)

    class Session:
        def query(self, _model):
            raise AssertionError("Missing optional data must not query or clear restaurants.")

    assert load_to_postgres.load_restaurants(Session()) is None
    assert "optional dataset not present" in caplog.text


def test_count_verification_skips_missing_optional_restaurants(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(load_to_postgres, "PROCESSED_DIR", tmp_path)
    counts_by_model = {
        City: 3200,
        Destination: 100,
        Place: 1050,
    }

    class Query:
        def __init__(self, count):
            self.value = count

        def count(self):
            return self.value

    class Session:
        def query(self, model):
            if model is Restaurant:
                raise AssertionError("Missing optional data must not count restaurants.")
            return Query(counts_by_model[model])

    all_ok, counts = load_to_postgres.verify_counts(Session())

    assert all_ok
    assert counts == {
        "cities": 3200,
        "destinations": 100,
        "places": 1050,
        "restaurants": None,
    }
    assert "Restaurants: skipped — optional dataset not present" in capsys.readouterr().out


def test_restaurant_loading_stops_at_configured_limit(tmp_path, monkeypatch, caplog):
    restaurant_file = tmp_path / "restaurants.csv"
    with restaurant_file.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["id"])
        writer.writeheader()
        writer.writerows({"id": f"restaurant-{index}"} for index in range(3_500))

    monkeypatch.setattr(load_to_postgres, "PROCESSED_DIR", tmp_path)
    caplog.set_level("INFO", logger=load_to_postgres.__name__)

    class Query:
        def __init__(self, session):
            self.session = session

        def delete(self):
            return None

        def count(self):
            return len(self.session.inserted)

    class Session:
        def __init__(self):
            self.inserted = []
            self.batch_sizes = []

        def query(self, _model):
            return Query(self)

        def flush(self):
            return None

        def bulk_save_objects(self, records):
            self.batch_sizes.append(len(records))
            self.inserted.extend(records)

    session = Session()

    loaded = load_to_postgres.load_restaurants(session)

    assert loaded == 3_000
    assert len(session.inserted) == 3_000
    assert session.batch_sizes == [500] * 6
    assert "Restaurants loaded: 3000 (limit: 3000)" in caplog.text
