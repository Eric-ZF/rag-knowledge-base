"""
repair_chromadb.py — 修复 ChromaDB chunk metadata
1. 删除 phantom paper_id 的 chunks（ChromaDB 有但 papers_db 无）
2. 修复所有 chunk 的 title metadata（从 papers_db 读取）
"""
import chromadb, json, sys, os

# Add parent dir to path for config
sys.path.insert(0, os.path.dirname(__file__) + '/..')

CHROMADB_DIR = '/tmp/chromadb'
PAPERS_DB_PATH = '/root/.openclaw/rag-data/papers_db.json'
COLLECTION_NAME = 'user_1d2a4dc3_550f_4f89_b97b_2b057705381c'

def main():
    client = chromadb.PersistentClient(path=CHROMADB_DIR)
    col = client.get_collection(COLLECTION_NAME)

    with open(PAPERS_DB_PATH) as f:
        papers_db = json.load(f)
    valid_pids = set(papers_db.keys())

    # Get all chunk data (no embeddings)
    all_data = col.get(include=['documents', 'metadatas'])
    print(f'Total chunks before repair: {col.count()}')

    # Identify phantom chunks
    phantom_ids = []
    valid_entries = []
    for mid, doc, meta in zip(all_data['ids'], all_data['documents'], all_data['metadatas']):
        pid = meta['paper_id']
        if pid not in valid_pids:
            phantom_ids.append(mid)
        else:
            valid_entries.append((mid, doc, meta))

    print(f'Phantom chunks: {len(phantom_ids)}')
    print(f'Valid chunks: {len(valid_entries)}')

    # Step 1: Delete phantom chunks
    if phantom_ids:
        col.delete(ids=phantom_ids)
        print(f'✅ Deleted {len(phantom_ids)} phantom chunks')

    # Step 2: Update title metadata for chunks that need it
    to_update = []
    for mid, doc, meta in valid_entries:
        pid = meta['paper_id']
        correct_title = papers_db[pid]['title']
        if meta.get('title') != correct_title:
            to_update.append((mid, doc, meta, correct_title))

    print(f'Chunks needing title update: {len(to_update)}')

    if to_update:
        ids_update = [mid for mid, _, _, _ in to_update]
        metas_update = []
        for mid, doc, old_meta, new_title in to_update:
            new_meta = dict(old_meta)
            new_meta['title'] = new_title
            metas_update.append(new_meta)

        # Use update() - only updates specified fields, preserves embeddings
        col.update(ids=ids_update, metadatas=metas_update)
        print(f'✅ Updated title for {len(ids_update)} chunks')

    # Verify
    all_data2 = col.get(include=['metadatas'])
    title_null = sum(1 for m in all_data2['metadatas'] if not m.get('title'))
    print(f'\n📊 After repair:')
    print(f'  Total chunks: {col.count()}')
    print(f'  Chunks with title=None: {title_null}')

    # Show per-paper stats
    from collections import Counter
    pid_counts = Counter(m['paper_id'] for m in all_data2['metadatas'])
    for pid, cnt in sorted(pid_counts.items()):
        title = papers_db.get(pid, {}).get('title', '???')
        print(f'  {pid[:8]} ({cnt} chunks): {title[:50]}')

if __name__ == '__main__':
    main()
