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
