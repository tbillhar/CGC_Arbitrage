from pathlib import Path

from database import AppSettings, Database


def test_app_settings_round_trip(tmp_path: Path) -> None:
    db = Database(tmp_path / "scanner.sqlite3")

    db.save_app_settings(
        AppSettings(
            selling_fee_rate=0.125,
            payment_fee_rate=0.031,
            shipping_cost=22.5,
            default_profit_margin=0.18,
        )
    )

    settings = db.get_app_settings()
    db.close()

    assert settings["selling_fee_rate"] == "0.125"
    assert settings["payment_fee_rate"] == "0.031"
    assert settings["shipping_cost"] == "22.5"
    assert settings["default_profit_margin"] == "0.18"


def test_app_settings_update_existing_values(tmp_path: Path) -> None:
    db = Database(tmp_path / "scanner.sqlite3")

    db.save_app_settings(AppSettings(0.10, 0.03, 18.0, 0.20))
    db.save_app_settings(AppSettings(0.12, 0.04, 20.0, 0.15))

    settings = db.get_app_settings()
    db.close()

    assert settings["selling_fee_rate"] == "0.12"
    assert settings["payment_fee_rate"] == "0.04"
    assert settings["shipping_cost"] == "20.0"
    assert settings["default_profit_margin"] == "0.15"
