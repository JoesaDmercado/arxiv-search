"""
The search agent is responsible for updating the index as papers are published.

The agent consumes notifications on the ``MetadataIsAvailable`` stream. For
each notification, the agent retrieves metadata for the most recent version of
the indicated paper from the :mod:`search.services.metadata` service. The agent
also retrieves metadata for earlier versions, if there are multiple versions
available. Each version is passed to the :mod:`search.services.index` service,
and becomes available for discovery via :mod:`search.routes.ui`.
"""
from typing import Optional
from datetime import datetime
import warnings

from flask import current_app as app

from arxiv.base import logging
from .consumer import MetadataRecordProcessor, DocumentFailed, IndexingFailed
from .base import CheckpointManager

logger = logging.getLogger(__name__)
logger.propagate = False


def process_stream(duration: Optional[int] = None) -> None:
    """
    Configure and run the record processor.

    Parameters
    ----------
    duration : int
        Time (in seconds) to run record processing. If None (default), will
        run "forever".

    """
    # We use the Flask application instance for configuration, and to manage
    # integrations with metadata service, search index.
    with warnings.catch_warnings():     # boto3 is notoriously annoying.
        warnings.simplefilter("ignore")
        start_at = app.config.get('KINESIS_START_AT')
        start_type = app.config.get('KINESIS_START_TYPE')
        if not start_type:
            start_type = 'AT_TIMESTAMP'
        if start_type == 'AT_TIMESTAMP' and not start_at:
            start_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        processor = MetadataRecordProcessor(
            app.config['KINESIS_STREAM'],
            app.config['KINESIS_SHARD_ID'],
            app.config['AWS_ACCESS_KEY_ID'],
            app.config['AWS_SECRET_ACCESS_KEY'],
            app.config['AWS_REGION'],
            CheckpointManager(
                app.config['KINESIS_CHECKPOINT_VOLUME'],
                app.config['KINESIS_STREAM'],
                app.config['KINESIS_SHARD_ID'],
            ),
            endpoint=app.config.get('KINESIS_ENDPOINT', None),
            verify=app.config.get('KINESIS_VERIFY', 'true') == 'true',
            duration=duration,
            start_type=start_type,
            start_at=start_at,
            sleep=float(app.config['KINESIS_SLEEP'])
        )
        processor.go()
