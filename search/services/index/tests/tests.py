"""Tests for :mod:`search.services.index`."""

from unittest import TestCase, mock
from datetime import date, datetime, timedelta
from pytz import timezone
from elasticsearch_dsl import Search, Q
from elasticsearch_dsl.query import Range, Match, Bool, Nested

from search.services import index
from search.services.index import advanced
from search.services.index.util import wildcardEscape, Q_
from search.domain import Query, FieldedSearchTerm, DateRange, Classification,\
    AdvancedQuery, FieldedSearchList, ClassificationList, SimpleQuery, \
    DocumentSet

EASTERN = timezone('US/Eastern')


class TestSearch(TestCase):
    """Tests for :func:`.index.search`."""

    @mock.patch('search.services.index.Search')
    @mock.patch('search.services.index.Elasticsearch')
    def test_advanced_query(self, mock_Elasticsearch, mock_Search):
        """:class:`.index.search` supports :class:`AdvancedQuery`."""
        mock_results = mock.MagicMock()
        mock_results.__getitem__.return_value = {'total': 53}
        mock_result = mock.MagicMock()
        mock_result.meta.score = 1
        mock_results.__iter__.return_value = [mock_result]
        mock_Search.execute.return_value = mock_results

        # Support the chaining API for py-ES.
        mock_Search.return_value = mock_Search
        mock_Search.filter.return_value = mock_Search
        mock_Search.highlight.return_value = mock_Search
        mock_Search.highlight_options.return_value = mock_Search
        mock_Search.query.return_value = mock_Search
        mock_Search.sort.return_value = mock_Search
        mock_Search.__getitem__.return_value = mock_Search

        query = AdvancedQuery(
            order='relevance',
            page_size=10,
            date_range=DateRange(
                start_date=datetime.now() - timedelta(days=5),
                end_date=datetime.now()
            ),
            primary_classification=ClassificationList([
                Classification(
                    group='physics',
                    archive='physics',
                    category='hep-th'
                )
            ]),
            terms=FieldedSearchList([
                FieldedSearchTerm(operator='AND', field='title', term='foo'),
                FieldedSearchTerm(operator='AND', field='author', term='joe'),
                FieldedSearchTerm(operator='OR', field='abstract', term='hmm'),
                FieldedSearchTerm(operator='NOT', field='comments', term='eh'),
                FieldedSearchTerm(operator='AND', field='journal_ref',
                                  term='jref (1999) 1:2-3'),
                FieldedSearchTerm(operator='AND', field='acm_class',
                                  term='abc123'),
                FieldedSearchTerm(operator='AND', field='msc_class',
                                  term='abc123'),
                FieldedSearchTerm(operator='OR', field='report_num',
                                  term='abc123'),
                FieldedSearchTerm(operator='OR', field='doi',
                                  term='10.01234/56789'),
                FieldedSearchTerm(operator='OR', field='orcid',
                                  term='0000-0000-0000-0000'),
                FieldedSearchTerm(operator='OR', field='author_id',
                                  term='Bloggs_J'),
            ])
        )
        document_set = index.search(query)
        self.assertIsInstance(document_set, DocumentSet)
        self.assertEqual(document_set.metadata['start'], 0)
        self.assertEqual(document_set.metadata['total'], 53)
        self.assertEqual(document_set.metadata['current_page'], 1)
        self.assertEqual(document_set.metadata['total_pages'], 6)
        self.assertEqual(document_set.metadata['page_size'], 10)
        self.assertEqual(len(document_set.results), 1)

    @mock.patch('search.services.index.Search')
    @mock.patch('search.services.index.Elasticsearch')
    def test_simple_query(self, mock_Elasticsearch, mock_Search):
        """:class:`.index.search` supports :class:`SimpleQuery`."""
        mock_results = mock.MagicMock()
        mock_results.__getitem__.return_value = {'total': 53}
        mock_result = mock.MagicMock()
        mock_result.meta.score = 1
        mock_results.__iter__.return_value = [mock_result]
        mock_Search.execute.return_value = mock_results

        # Support the chaining API for py-ES.
        mock_Search.return_value = mock_Search
        mock_Search.filter.return_value = mock_Search
        mock_Search.highlight.return_value = mock_Search
        mock_Search.highlight_options.return_value = mock_Search
        mock_Search.query.return_value = mock_Search
        mock_Search.sort.return_value = mock_Search
        mock_Search.__getitem__.return_value = mock_Search

        query = SimpleQuery(
            order='relevance',
            page_size=10,
            search_field='title',
            value='foo title'
        )
        document_set = index.search(query)
        self.assertIsInstance(document_set, DocumentSet)
        self.assertEqual(document_set.metadata['start'], 0)
        self.assertEqual(document_set.metadata['total'], 53)
        self.assertEqual(document_set.metadata['current_page'], 1)
        self.assertEqual(document_set.metadata['total_pages'], 6)
        self.assertEqual(document_set.metadata['page_size'], 10)
        self.assertEqual(len(document_set.results), 1)


class TestWildcardSearch(TestCase):
    """A wildcard [*?] character is present in a querystring."""

    def test_match_any_wildcard_is_present(self):
        """A * wildcard is present in the query."""
        qs = "Foo t*"
        qs_escaped, wildcard = wildcardEscape(qs)

        self.assertTrue(wildcard, "Wildcard should be detected")
        self.assertEqual(qs, qs_escaped, "The querystring should be unchanged")
        self.assertIsInstance(
            Q_('match', 'title', qs),
            type(index.Q('wildcard', title=qs)),
            "Wildcard Q object should be generated"
        )

    def test_match_any_wildcard_in_literal(self):
        """A * wildcard is present in a string literal."""
        qs = '"Foo t*"'
        qs_escaped, wildcard = wildcardEscape(qs)

        self.assertEqual(qs_escaped, '"Foo t\*"', "Wildcard should be escaped")
        self.assertFalse(wildcard, "Wildcard should not be detected")
        self.assertIsInstance(
            Q_('match', 'title', qs),
            type(index.Q('match', title='"Foo t\*"')),
            "Wildcard Q object should not be generated"
        )

    def test_multiple_match_any_wildcard_in_literal(self):
        """Multiple * wildcards are present in a string literal."""
        qs = '"Fo*o t*"'
        qs_escaped, wildcard = wildcardEscape(qs)

        self.assertEqual(qs_escaped, '"Fo\*o t\*"',
                         "Both wildcards should be escaped")
        self.assertFalse(wildcard, "Wildcard should not be detected")
        self.assertIsInstance(
            Q_('match', 'title', qs),
            type(index.Q('match', title='"Fo\*o t\*"')),
            "Wildcard Q object should not be generated"
        )

    def test_mixed_wildcards_in_literal(self):
        """Both * and ? characters are present in a string literal."""
        qs = '"Fo? t*"'
        qs_escaped, wildcard = wildcardEscape(qs)

        self.assertEqual(qs_escaped, '"Fo\? t\*"',
                         "Both wildcards should be escaped")
        self.assertFalse(wildcard, "Wildcard should not be detected")
        self.assertIsInstance(
            Q_('match', 'title', qs),
            type(index.Q('match', title='"Fo\? t\*"')),
            "Wildcard Q object should not be generated"
        )

    def test_wildcards_both_inside_and_outside_literal(self):
        """Wildcard characters are present both inside and outside literal."""
        qs = '"Fo? t*" said the *'
        qs_escaped, wildcard = wildcardEscape(qs)

        self.assertEqual(qs_escaped, '"Fo\? t\*" said the *',
                         "Wildcards in literal should be escaped")
        self.assertTrue(wildcard, "Wildcard should be detected")
        self.assertIsInstance(
            Q_('match', 'title', qs),
            type(index.Q('wildcard', title='"Fo\? t\*" said the *')),
            "Wildcard Q object should be generated"
        )

    def test_wildcards_inside_outside_multiple_literals(self):
        """Wildcard chars are everywhere, and there are multiple literals."""
        qs = '"Fo?" s* "yes*" o?'
        qs_escaped, wildcard = wildcardEscape(qs)

        self.assertEqual(qs_escaped, '"Fo\?" s* "yes\*" o?',
                         "Wildcards in literal should be escaped")
        self.assertTrue(wildcard, "Wildcard should be detected")

        self.assertIsInstance(
            Q_('match', 'title', qs),
            type(index.Q('wildcard', title='"Fo\?" s* "yes\*" o?')),
            "Wildcard Q object should be generated"
        )

    def test_wildcard_at_opening_of_string(self):
        """A wildcard character is the first character in the querystring."""
        with self.assertRaises(index.QueryError):
            wildcardEscape("*nope")

        with self.assertRaises(index.QueryError):
            Q_('match', 'title', '*nope')


class TestPrepare(TestCase):
    """Tests for :mod:`.index.prepare`."""

    def test_group_terms(self):
        """:meth:`._group_terms` groups terms using logical precedence."""
        query = AdvancedQuery(terms=FieldedSearchList([
            FieldedSearchTerm(operator=None, field='title', term='muon'),
            FieldedSearchTerm(operator='OR', field='title', term='gluon'),
            FieldedSearchTerm(operator='NOT', field='title', term='foo'),
            FieldedSearchTerm(operator='AND', field='title', term='boson'),
        ]))
        expected = (
            FieldedSearchTerm(operator=None, field='title', term='muon'),
            'OR',
            (
              (
                FieldedSearchTerm(operator='OR', field='title', term='gluon'),
                'NOT',
                FieldedSearchTerm(operator='NOT', field='title', term='foo')
              ),
              'AND',
              FieldedSearchTerm(operator='AND', field='title', term='boson')
            )
        )
        try:
            terms = advanced._group_terms(query)
        except AssertionError:
            self.fail('Should result in a single group')
        self.assertEqual(expected, terms)

    def test_group_terms_all_and(self):
        """:meth:`._group_terms` groups terms using logical precedence."""
        query = AdvancedQuery(terms=FieldedSearchList([
            FieldedSearchTerm(operator=None, field='title', term='muon'),
            FieldedSearchTerm(operator='AND', field='title', term='gluon'),
            FieldedSearchTerm(operator='AND', field='title', term='foo'),
        ]))
        expected = (
            (
              FieldedSearchTerm(operator=None, field='title', term='muon'),
              'AND',
              FieldedSearchTerm(operator='AND', field='title', term='gluon')
            ),
            'AND',
            FieldedSearchTerm(operator='AND', field='title', term='foo')
        )
        try:
            terms = advanced._group_terms(query)
        except AssertionError:
            self.fail('Should result in a single group')
        self.assertEqual(expected, terms)
