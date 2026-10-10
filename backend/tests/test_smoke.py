import pigeondome


def test_package_exposes_version() -> None:
    assert pigeondome.__version__ == "0.1.0"
