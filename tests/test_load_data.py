import warnings

import pandas as pd

from dashtoolsrecomendation.pages import load_data


def test_carregar_excel_suppresses_missing_default_style_warning(
    monkeypatch,
):
    expected = pd.DataFrame({"valor": [1]})

    def fake_read_excel(*args, **kwargs):
        warnings.warn_explicit(
            "Workbook contains no default style, apply openpyxl's default",
            UserWarning,
            filename="openpyxl/styles/stylesheet.py",
            lineno=237,
            module="openpyxl.styles.stylesheet",
        )
        return expected

    load_data.carregar_excel.clear()
    monkeypatch.setattr(load_data.pd, "read_excel", fake_read_excel)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        result = load_data.carregar_excel(b"workbook-without-default-style")

    pd.testing.assert_frame_equal(result, expected)
    assert captured == []
