def test_smoke() -> None:
    """Import the package and check the version string shape."""
    import ws4

    assert ws4.__version__.count(".") == 2
