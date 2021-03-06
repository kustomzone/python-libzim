# This file is part of python-libzim
# (see https://github.com/libzim/python-libzim)
#
# Copyright (c) 2020 Juan Diego Caballero <jdc@monadical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import re
import sys
import subprocess
import pathlib

import pytest

from libzim.writer import Article, Blob, Creator, Compression
from libzim.reader import File

# test files https://wiki.kiwix.org/wiki/Content_in_all_languages


# https://wiki.openzim.org/wiki/Metadata
@pytest.fixture(scope="session")
def metadata():
    return {
        # Mandatory
        "Name": "wikipedia_fr_football",
        "Title": "English Wikipedia",
        "Creator": "English speaking Wikipedia contributors",
        "Publisher": "Wikipedia user Foobar",
        "Date": "2009-11-21",
        "Description": "All articles (without images) from the english Wikipedia",
        "Language": "eng",
        # Optional
        "Longdescription": (
            "This ZIM file contains all articles (without images) from the english Wikipedia by 2009-11-10."
            " The topics are ..."
        ),
        "Licence": "CC-BY",
        "Tags": "wikipedia;_category:wikipedia;_pictures:no;_videos:no;_details:yes;_ftindex:yes",
        "Flavour": "nopic",
        "Source": "https://en.wikipedia.org/",
        "Counter": "image/jpeg=5;image/gif=3;image/png=2",
        "Scraper": "sotoki 1.2.3",
    }


@pytest.fixture(scope="session")
def article_content():
    content = """<!DOCTYPE html>
        <html class="client-js">
        <head><meta charset="UTF-8">
        <title>Monadical</title>
        </head>
        <h1> ñññ Hello, it works ñññ </h1></html>"""
    url = "A/Monadical_SAS"
    title = "Monadical SAS"
    mime_type = "text/html"
    return (content, url, title, mime_type)


class SimpleArticle(Article):
    def __init__(self, content, url, title, mime_type):
        Article.__init__(self)
        self.content = content
        self.url = url
        self.title = title
        self.mime_type = mime_type

    def is_redirect(self):
        return False

    @property
    def can_write(self):
        return True

    def get_url(self):
        return self.url

    def get_title(self):
        return self.title

    def get_mime_type(self):
        return self.mime_type

    def get_filename(self):
        return ""

    def should_compress(self):
        return True

    def should_index(self):
        return True

    def get_data(self):
        return Blob(self.content.encode("UTF-8"))

    def get_size(self):
        return self.get_data().size()


class OverridenArticle(Article):
    def __init__(self, removed_method):
        super().__init__()
        self.removed_method = removed_method

    def get_url(self) -> str:
        return "N/u"

    def get_title(self) -> str:
        return ""

    def is_redirect(self) -> bool:
        return self.removed_method == "get_redirect_url"

    def get_mime_type(self) -> str:
        return "text/plain"

    def get_filename(self) -> str:
        return ""

    def should_compress(self) -> bool:
        return False

    def should_index(self) -> bool:
        return False

    def get_redirect_url(self) -> str:
        return "N/u"

    def get_data(self) -> Blob:
        return Blob("")

    def get_size(self):
        # with 0, there's no call to get_data()
        return 1 if self.removed_method == "get_data" else 0


@pytest.fixture(scope="session")
def article(article_content):
    return SimpleArticle(*article_content)


def test_write_article(tmpdir, article):
    with Creator(
        tmpdir / "test.zim", main_page="welcome", index_language="eng", min_chunk_size=2048,
    ) as zim_creator:
        zim_creator.add_article(article)
        zim_creator.update_metadata(
            creator="python-libzim",
            description="Created in python",
            name="Hola",
            publisher="Monadical",
            title="Test Zim",
        )


def test_article_metadata(tmpdir, metadata):
    with Creator(
        tmpdir / "test.zim", main_page="welcome", index_language="eng", min_chunk_size=2048,
    ) as zim_creator:
        zim_creator.update_metadata(**metadata)
        assert zim_creator._metadata == metadata


def test_creator_params(tmpdir):
    path = tmpdir / "test.zim"
    main_page = "welcome"
    main_page_url = f"A/{main_page}"
    index_language = "eng"
    with Creator(
        path, main_page=main_page_url, index_language=index_language, min_chunk_size=2048
    ) as zim_creator:
        zim_creator.add_article(
            SimpleArticle(title="Welcome", mime_type="text/html", content="", url=main_page_url)
        )

    zim = File(path)
    assert zim.filename == path
    assert zim.main_page_url == main_page_url
    assert bytes(zim.get_article("/M/Language").content).decode("UTF-8") == index_language


def test_segfault_on_realloc(tmpdir):
    """ assert that we are able to delete an unclosed Creator #31 """
    creator = Creator(tmpdir / "test.zim", "welcome", "eng")
    del creator  # used to segfault


def test_noleftbehind_empty(tmpdir):
    """ assert that ZIM with no articles don't leave files behind #41 """
    fname = "test_empty.zim"
    with Creator(
        tmpdir / fname, main_page="welcome", index_language="eng", min_chunk_size=2048,
    ) as zim_creator:
        print(zim_creator)

    assert len([p for p in tmpdir.listdir() if p.basename.startswith(fname)]) == 1


def test_double_close(tmpdir):
    creator = Creator(tmpdir / "test.zim", "welcome", "eng")
    creator.close()
    with pytest.raises(RuntimeError):
        creator.close()


def test_default_creator_params(tmpdir):
    """ ensure we can init a Creator without specifying all params """
    creator = Creator(tmpdir / "test.zim", "welcome")
    assert True  # we could init the Creator without specifying other params
    assert creator.language == "eng"
    assert creator.main_page == "welcome"


def test_filename_param_types(tmpdir):
    path = tmpdir / "test.zim"
    with Creator(path, "welcome") as creator:
        assert creator.filename == path
        assert isinstance(creator.filename, pathlib.Path)
    with Creator(str(path), "welcome") as creator:
        assert creator.filename == path
        assert isinstance(creator.filename, pathlib.Path)


def test_in_article_exceptions(tmpdir):
    """ make sure we raise RuntimeError from article's virtual methods """

    class BoolErrorArticle(SimpleArticle):
        def is_redirect(self):
            raise RuntimeError("OUPS Redirect")

    class StringErrorArticle(SimpleArticle):
        def get_url(self):
            raise IOError

    class BlobErrorArticle(SimpleArticle):
        def get_data(self):
            raise IOError

    path, main_page = tmpdir / "test.zim", "welcome"
    args = {"title": "Hello", "mime_type": "text/html", "content": "", "url": "welcome"}

    with Creator(path, main_page) as zim_creator:
        # make sure we can can exception of all types (except int, not used)
        with pytest.raises(RuntimeError, match="OUPS Redirect"):
            zim_creator.add_article(BoolErrorArticle(**args))
        with pytest.raises(RuntimeError, match="in get_url"):
            zim_creator.add_article(StringErrorArticle(**args))
        with pytest.raises(RuntimeError, match="IOError"):
            zim_creator.add_article(BlobErrorArticle(**args))
        with pytest.raises(RuntimeError, match="NotImplementedError"):
            zim_creator.add_article(Article())

    # make sure we can catch it from outside creator
    with pytest.raises(RuntimeError):
        with Creator(path, main_page) as zim_creator:
            zim_creator.add_article(BlobErrorArticle(**args))


def test_dontcreatezim_onexception(tmpdir):
    """ make sure we can prevent ZIM file creation (workaround missing cancel())

        A new interpreter is instanciated to get a different memory space.
        This workaround is not safe and may segfault at GC under some circumstances

        Unless we get a proper cancel() on libzim, that's the only way to not create
        a ZIM file on error """
    path, main_page = tmpdir / "test.zim", "welcome"
    pycode = f"""
from libzim.writer import Creator
from libzim.writer import Article
class BlobErrorArticle(Article):
    def get_data(self):
        raise ValueError
zim_creator = Creator("{path}", "{main_page}")
try:
    zim_creator.add_article(BlobErrorArticle(**args))
except Exception:
    zim_creator._closed = True
"""

    py = subprocess.run([sys.executable, "-c", pycode])
    assert py.returncode == 0
    assert not path.exists()


def test_redirect_url(tmpdir):
    url = "A/welcome"
    redirect_url = "A/home"

    class RedirectArticle(SimpleArticle):
        def is_redirect(self):
            return True

        def get_redirect_url(self):
            return url

    path = tmpdir / "test.zim"
    with Creator(path, "welcome") as zim_creator:
        zim_creator.add_article(SimpleArticle(title="Hello", mime_type="text/html", content="", url=url))
        zim_creator.add_article(RedirectArticle(content="", title="", mime_type="", url=redirect_url))

    with File(path) as reader:
        assert reader.get_article(redirect_url).is_redirect
        assert reader.get_article(redirect_url).get_redirect_article().longurl == url


@pytest.mark.parametrize(
    "no_method", [m for m in dir(OverridenArticle) if m.split("_", 1)[0] in ("get", "is", "should")],
)
def test_article_overriding_required(tmpdir, monkeypatch, no_method):
    """ ensure we raise properly on not-implemented methods of Article """

    path, main_page = tmpdir / "test.zim", "welcome"
    pattern = re.compile(r"NotImplementedError.+must be implemented")
    monkeypatch.delattr(OverridenArticle, no_method)

    with pytest.raises(RuntimeError, match=pattern):
        with Creator(path, main_page) as zim_creator:
            zim_creator.add_article(OverridenArticle(no_method))


def test_repr():
    title = "Welcome !"
    url = "A/welcome"
    article = SimpleArticle("", url, title, "text/plain")
    assert title in repr(article)
    assert url in repr(article)


@pytest.mark.parametrize(
    "compression", Compression.__members__,
)
def test_compression_from_enum(tmpdir, compression):
    with Creator(tmpdir / "test.zim", "home", compression=compression) as zim_creator:
        zim_creator.add_article(SimpleArticle(title="Hello", mime_type="text/html", content="", url="A/home"))


@pytest.mark.parametrize(
    "compression", Compression.__members__.keys(),
)
def test_compression_from_string(tmpdir, compression):
    with Creator(tmpdir / "test.zim", "home", compression=compression) as zim_creator:
        zim_creator.add_article(SimpleArticle(title="Hello", mime_type="text/html", content="", url="A/home"))


def test_bad_compression(tmpdir):
    with pytest.raises(AttributeError):
        Creator(tmpdir / "test.zim", "welcome", compression="toto")


def test_filename_article(tmpdir):
    class FileArticle(Article):
        def __init__(self, fpath, url):
            super().__init__()
            self.fpath = fpath
            self.url = url

        def is_redirect(self):
            return False

        def get_url(self):
            return self.url

        def get_title(self):
            return ""

        def get_mime_type(self):
            return "text/plain"

        def get_filename(self):
            return str(self.fpath)

        def should_compress(self):
            return True

        def should_index(self):
            return True

        def get_size(self):
            return self.fpath.stat().size

    zim_path = tmpdir / "test.zim"
    article_path = tmpdir / "test.txt"
    article_url = "A/home"
    content = b"abc"

    # write content to physical file
    with open(article_path, "wb") as fh:
        fh.write(content)

    with Creator(zim_path, "home") as zim_creator:
        zim_creator.add_article(FileArticle(article_path, article_url))

    # ensure size on reader is correct
    with File(zim_path) as reader:
        assert reader.get_article(article_url).content.nbytes == len(content)
