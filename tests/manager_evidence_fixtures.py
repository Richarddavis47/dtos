"""Publish explicit test products through the real pinned producer boundary."""
from src.core.intelligence.manager_evidence import begin_preparation, end_preparation, publish_rows


def publish(data):
    token = begin_preparation(data)
    try:
        for field in ('front_office_evidence', 'gm_behavioral_intelligence'):
            if field in data:
                publish_rows(data, field, data[field])
    finally:
        end_preparation(token)
