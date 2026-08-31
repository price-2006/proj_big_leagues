"""Phase 11: save_model/load_model round-trip through a real joblib file
on disk (tmp_path, not MODELS_DIR — never touch the real trained-model
files a test run happens to find on disk)."""
from app.ml import model_registry


class _DummyEstimator:
    def __init__(self, coef: float) -> None:
        self.coef = coef

    def predict(self, x):
        return [v * self.coef for v in x]


def test_save_then_load_round_trips_estimator_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(model_registry, "MODELS_DIR", tmp_path)

    model_registry.save_model(
        model_type="dummy",
        estimator=_DummyEstimator(coef=2.0),
        feature_names=["a", "b"],
        hyperparameters={"coef": 2.0},
    )
    loaded = model_registry.load_model("dummy")

    assert loaded.model_type == "dummy"
    assert loaded.feature_names == ["a", "b"]
    assert loaded.hyperparameters == {"coef": 2.0}
    assert loaded.estimator.predict([1, 2]) == [2.0, 4.0]
    assert (tmp_path / "dummy.joblib").exists()
    assert (tmp_path / "dummy.json").exists()
