import pytest

from sipl import SiplSyntaxError, parse
from conftest import list_examples, read_example

VALID = list_examples("valid")
INVALID = list_examples("invalid")


def test_examples_count():
    assert len(VALID) == 12
    assert len(INVALID) == 12


@pytest.mark.parametrize("name", VALID)
def test_valid_program(name):
    parse(read_example("valid", name))


@pytest.mark.parametrize("name", INVALID)
def test_invalid_program(name):
    source = read_example("invalid", name)
    first_line = source.split("\n")[0]
    expected_line = int(first_line.split(":")[1])
    with pytest.raises(SiplSyntaxError) as info:
        parse(source)
    assert info.value.diagnostic.span.line == expected_line


def test_keyword_cannot_be_variable():
    with pytest.raises(SiplSyntaxError):
        parse("begin end := 1 end")
    with pytest.raises(SiplSyntaxError):
        parse("begin while := 1 end")


def test_variable_can_start_with_keyword():
    parse("begin beginning := 1; endX := 2 end")


def test_comments():
    parse("// comment\nbegin skip // comment\nend")
