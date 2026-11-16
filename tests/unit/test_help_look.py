"""Help pages from outside zynthian-help (e.g. a widget's zyngui:help page) get the zynthian-help look & feel."""

import pytest
from bs4 import BeautifulSoup

zynthian_gui_help = pytest.importorskip("zyngui.zynthian_gui_help")
apply_help_look = zynthian_gui_help.apply_help_look
is_in_dir = zynthian_gui_help.is_in_dir

HELP_DIR = "/zynthian/zynthian-help"
STYLE = f"{HELP_DIR}/style.css"


def look(html):
    return apply_help_look(BeautifulSoup(html, "html.parser"), HELP_DIR)


def stylesheets(soup):
    return [link["href"] for link in soup.find_all("link", rel="stylesheet")]


def test_full_page_gets_stylesheet_and_body_class():
    soup = look("<html><head><title>T</title></head><body><h1>Widget</h1></body></html>")
    assert stylesheets(soup) == [STYLE]
    assert soup.body["class"] == ["help_ui"]
    assert soup.h1.get_text() == "Widget"


def test_page_stylesheet_comes_after_so_it_can_override():
    soup = look('<html><head><link rel="stylesheet" href="mine.css"></head><body></body></html>')
    assert stylesheets(soup) == [STYLE, "mine.css"]


def test_existing_body_classes_are_kept():
    soup = look('<html><head></head><body class="dark"><p>x</p></body></html>')
    assert soup.body["class"] == ["dark", "help_ui"]


def test_body_class_is_not_duplicated():
    soup = look('<html><head></head><body class="help_ui"></body></html>')
    assert soup.body["class"] == ["help_ui"]


def test_fragment_is_wrapped_in_a_document():
    soup = look("<h1>Tuner</h1><p>Plain fragment</p>")
    assert soup.html is not None and soup.head is not None
    assert stylesheets(soup) == [STYLE]
    assert soup.body["class"] == ["help_ui"]
    assert [t.name for t in soup.body.find_all(recursive=False)] == ["h1", "p"]


def test_page_without_head_gets_one():
    soup = look("<html><body><p>No head</p></body></html>")
    assert soup.head is not None
    assert stylesheets(soup) == [STYLE]


def test_body_without_html_tag_is_wrapped():
    soup = look("<body><p>Only body</p></body>")
    assert soup.html is not None
    assert stylesheets(soup) == [STYLE]
    assert soup.body.p.get_text() == "Only body"


def test_is_in_dir(tmp_path):
    (tmp_path / "help").mkdir()
    (tmp_path / "help-other").mkdir()
    assert is_in_dir(str(tmp_path / "help" / "page.html"), str(tmp_path / "help"))
    assert not is_in_dir(str(tmp_path / "help-other" / "page.html"), str(tmp_path / "help"))
    assert not is_in_dir("/elsewhere/page.html", str(tmp_path / "help"))
