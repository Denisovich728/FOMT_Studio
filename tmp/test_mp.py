import time
import os
from concurrent.futures import ProcessPoolExecutor

def _worker(chunk_info):
    start, end = chunk_info
    # simulate some work
    found = {}
    for i in range(start, end, 4):
        if i % 100000 == 0:
            found[i] = "test"
    return found

def test_pool():
    print("Testing pool overhead...")
    t0 = time.time()
    
    # simulate 16MB
    total_size = 16 * 1024 * 1024
    num_chunks = 8
    chunk_size = total_size // num_chunks
    chunks = [(i * chunk_size, (i + 1) * chunk_size) for i in range(num_chunks)]
    
    results = {}
    with ProcessPoolExecutor(max_workers=8) as executor:
        for res in executor.map(_worker, chunks):
            results.update(res)
            
    print(f"Done in {time.time() - t0:.2f}s, found {len(results)} items.")

if __name__ == '__main__':
    test_pool()
