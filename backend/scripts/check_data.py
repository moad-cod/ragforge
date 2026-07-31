try:
    from scripts._bootstrap import ensure_backend_path
except ModuleNotFoundError:
    try:
        from backend.scripts._bootstrap import ensure_backend_path
    except ModuleNotFoundError:
        from _bootstrap import ensure_backend_path

ensure_backend_path()

from app.services.indexer import qdrant
from qdrant_client.models import Filter, FieldCondition, MatchValue

DOCUMENT_ID = '4aacc15d-54b7-4943-bacc-ac75ef6184b7'
COLLECTION = 'sentence'


def main() -> None:
    offset = None
    total = 0
    bad_found = False

    while True:
        points, offset = qdrant.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(must=[FieldCondition(key='document_id', match=MatchValue(value=DOCUMENT_ID))]),
            limit=50,
            offset=offset,
            with_payload=True,
        )
        for point in points:
            total += 1
            text_val = point.payload.get('text')
            if not isinstance(text_val, str):
                bad_found = True
                print('BAD POINT:', point.id, '| type:', type(text_val), '| value:', repr(text_val)[:200])
        if offset is None:
            break

    print(f'Total points checked: {total}')
    if not bad_found:
        print('No bad points found for this document.')


if __name__ == "__main__":
    main()
