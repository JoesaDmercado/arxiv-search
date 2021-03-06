"""Helpers for building ES queries."""

import re
from typing import Any, Optional, Tuple, Union, List
from string import punctuation

from elasticsearch_dsl import Search, Q, SF

from search.domain import Query
from .exceptions import QueryError


# We'll compile this ahead of time, since it gets called quite a lot.
STRING_LITERAL = re.compile(r"([\"][^\"]*[\"])")
"""Pattern for string literals (quoted) in search queries."""

TEXISM = re.compile(r'(\$[^\$]+\$)')

# TODO: make this configurable.
MAX_RESULTS = 10_000
"""This is the maximum result offset for pagination."""

SPECIAL_CHARACTERS = ['+', '=', '&&', '||', '>', '<', '!', '(', ')', '{',
                      '}', '[', ']', '^', '~', ':', '\\', '/', '-']
DEFAULT_SORT = ['-announced_date_first', '_doc']

DATE_PARTIAL = r"(?:^|[\s])(\d{2})((?:0[1-9]{1})|(?:1[0-2]{1}))(?:$|[\s])"
"""Used to match parts of author IDs that encode the announcement date."""


def wildcardEscape(querystring: str) -> Tuple[str, bool]:
    """
    Detect wildcard characters, and escape any that occur within a literal.

    Parameters
    ----------
    querystring : str

    Returns
    -------
    str
        Query string with wildcard characters enclosed in literals escaped.
    bool
        If a non-literal wildcard character is present, returns True.

    """
    # This should get caught by the controller (form validation), but just
    # in case we should check for it here.
    if querystring.startswith('?') or querystring.startswith('*'):
        raise QueryError('Query cannot start with a wildcard')

    # Escape wildcard characters within string literals.
    # re.sub() can't handle the complexity, sadly...
    parts = re.split(STRING_LITERAL, querystring)
    parts = [part.replace('*', r'\*').replace('?', r'\?')
             if part.startswith('"') or part.startswith("'") else part
             for part in parts]
    querystring = "".join(parts)

    # Only unescaped wildcard characters should remain.
    wildcard = re.search(r'(?<!\\)([\*\?])', querystring) is not None
    return querystring, wildcard


def has_wildcard(term: str) -> bool:
    """Determine whether or not ``term`` contains a wildcard."""
    return (('*' in term or '?' in term) and not
            (term.startswith('*') or term.startswith('?')))


def is_literal_query(term: str) -> bool:
    """Determine whether the term is intended to be treated as a literal."""
    # return re.match('"[^"]+"', term) is not None
    return '"' in term


def is_tex_query(term: str) -> bool:
    """Determine whether the term is intended as a TeX query."""
    return re.match(TEXISM, term) is not None


def strip_tex(term: str) -> str:
    """Remove TeX-isms from a term."""
    return re.sub(TEXISM, '', term).strip()


def Q_(qtype: str, field: str, value: str, operator: str = 'or') -> Q:
    """Construct a :class:`.Q`, but handle wildcards first."""
    value, wildcard = wildcardEscape(value)
    if wildcard:
        return Q('wildcard', **{field: {'value': value.lower()}})
    if 'match' in qtype:
        return Q(qtype, **{field: value})
    return Q(qtype, **{field: value}, operator=operator)


def escape(term: str, quotes: bool = False) -> str:
    """Escape special characters."""
    escaped = []
    for i, char in enumerate(term):
        if char in SPECIAL_CHARACTERS or quotes and char == '"':
            escaped.append("\\")
        escaped.append(char)
    return "".join(escaped)


def strip_punctuation(s: str) -> str:
    """Remove all punctuation characters from a string."""
    return ''.join([c for c in s if c not in punctuation])


def remove_single_characters(term: str) -> str:
    """Remove any single characters in the search string."""
    return ' '.join([part for part in term.split()
                     if len(strip_punctuation(part)) > 1])


def sort(query: Query, search: Search) -> Search:
    """Apply sorting to a :class:`.Search`."""
    if not query.order:
        sort_params = DEFAULT_SORT
    else:
        direction = '-' if query.order.startswith('-') else ''
        sort_params = [query.order, f'{direction}paper_id_v']
    if sort_params is not None:
        search = search.sort(*sort_params)
    return search


def match_date_partial(term: str) -> Tuple[str, str]:
    """
    Attempt to find a four-digit ID date partial (year + month).

    This can be used to search for papers by announcement date.

    Parameters
    ----------
    term : str
        Search term.

    Returns
    -------
    tuple
        First element is date (str) in `yyyy-MM` format, second element is the
        remainder of `term` (without the partial).

    Raises
    ------
    ValueError
        Raised if no date partial is found in `term`.

    """
    match = re.search(DATE_PARTIAL, term)
    if match:
        year, month = match.groups()
        # This should be fine until 2091.
        century = 19 if int(year) >= 91 else 20
        date_partial = f"{century}{year}-{month}"   # year_month format in ES.
        remainder = term[:match.start()] + " " + term[match.end():]
        return date_partial, re.sub(r"\s+", " ", remainder).strip()
    raise ValueError('Does not include an ID date partial')
