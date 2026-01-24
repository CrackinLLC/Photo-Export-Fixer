# PEF Optimizations - Prioritized Task List

This document consolidates performance improvement opportunities, organized by ROI (impact vs effort ratio). Items at the top provide the best value for time invested.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| P1 | Do immediately - high impact, minimal effort |
| P2 | Do soon - high impact, reasonable effort |
| P3 | Do when convenient - moderate returns |
| P4 | Consider later - significant effort required |
| P5 | Future/specialized - advanced optimizations |

---

## P1: Quick Wins (< 30 minutes each)

### 1. Use orjson for JSON Parsing
**Effort:** 5 minutes | **Impact:** 3-10x faster JSON parsing

The standard library `json` module is slow. `orjson` is a drop-in replacement written in Rust.

```python
# Before
import json
with open(path, 'r') as f:
    content = json.load(f)

# After
import orjson
with open(path, 'rb') as f:  # Note: binary mode
    content = orjson.loads(f.read())
```

**Action:** Add `orjson>=3.9.0` to requirements.txt, update orchestrator.py `_read_json()`.

---

### 2. Pre-filter JSONs Before Full Parse
**Effort:** 10 minutes | **Impact:** Skip 20-50% of JSON parsing

Most Google Photos JSONs don't have GPS or people data. Quick byte search avoids expensive parsing.

```python
raw = f.read()
# Quick check before expensive parse
if b'"geoData"' not in raw and b'"people"' not in raw:
    # Skip files without relevant metadata
    continue
content = orjson.loads(raw)
```

**Action:** Add pre-filter in orchestrator.py before calling `_read_json()`.

---

### 3. Pre-compile Regex Patterns
**Effort:** 5 minutes | **Impact:** Minor but free

The bracket pattern regex is already compiled in matcher.py (good!). Verify no other runtime compilation exists.

```python
# Already done in matcher.py:
BRACKET_PATTERN = re.compile(r"\([1-9][0-9]{0,2}\)\.json$")
```

**Action:** Audit codebase for any `re.match()`, `re.findall()` calls without pre-compiled patterns.

---

### 4. Single-Pass Directory Scanning
**Effort:** 15 minutes | **Impact:** Eliminate redundant I/O

Currently scanner.py walks the directory tree twice - once to count directories (for progress), then again to actually scan. This doubles I/O time.

```python
# Current (scanner.py:54-56)
for _ in os.walk(self.path):
    dir_count += 1  # First pass - just counting

# Second pass does actual work
for dirpath, dirnames, filenames in os.walk(self.path):
    ...
```

**Action:** Remove first pass, use indeterminate progress or estimate based on early scanning.

---

### 5. Use os.scandir Instead of os.walk
**Effort:** 15 minutes | **Impact:** 20-30% faster directory scanning

`os.scandir()` provides DirEntry objects with cached stat info, avoiding redundant syscalls.

```python
def fast_walk(path):
    """Faster alternative to os.walk using scandir."""
    with os.scandir(path) as entries:
        dirs, files = [], []
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                dirs.append(entry.name)
            else:
                files.append(entry.name)
        yield path, dirs, files
        for d in dirs:
            yield from fast_walk(os.path.join(path, d))
```

**Action:** Replace os.walk() in scanner.py with scandir-based implementation.

---

## P2: High-Value Improvements (1-2 hours each)

### 6. ExifTool Batch Mode (BIGGEST SINGLE WIN)
**Effort:** 1-2 hours | **Impact:** 10-50x faster for metadata writes

Current implementation calls ExifTool once per file. ExifTool supports batching hundreds of files per call.

```python
# Current: One call per file (slow)
for file in files:
    et.set_tags(file, tags)

# Better: Batch files with identical tags
batch = []
for json_data in jsons:
    tags = build_tags(json_data)
    matched_files = find_files(json_data)
    batch.extend((f, tags) for f in matched_files)

    if len(batch) >= 100:
        et.execute_batch(batch)
        batch = []
```

Alternative: Use ExifTool's `-@ ARGFILE` to pass thousands of files via temp file.

**Action:** Modify processor.py to collect files and execute in batches.

---

### 7. Skip Already-Tagged Files
**Effort:** 1 hour | **Impact:** Massive on re-runs (skip 100% of done files)

Before writing metadata, check if it already exists. Huge win for incremental processing.

```python
# Before writing, check existing tags
existing = et.get_tags(filepath, ["GPSLatitude", "PersonInImage"])
if existing.get("GPSLatitude") and existing.get("PersonInImage"):
    stats.skipped += 1
    continue
```

Could also maintain a "processed files" manifest file for even faster checks.

**Action:** Add tag existence check in processor.py before write operations.

---

### 8. LRU Cache for Path Operations
**Effort:** 30 minutes | **Impact:** Eliminates redundant computation

Cache results of pure functions that get called repeatedly with same inputs.

```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def get_album_name(filepath: str) -> str:
    return os.path.basename(os.path.dirname(filepath))
```

**Action:** Add @lru_cache to get_album_name() and similar functions in utils.py.

---

### 9. Thread Pool for File I/O
**Effort:** 1 hour | **Impact:** 2-4x faster for I/O-bound operations

Use ThreadPoolExecutor for concurrent file reads while CPU processes previous batch.

```python
from concurrent.futures import ThreadPoolExecutor

def read_and_parse(path):
    with open(path, 'rb') as f:
        return orjson.loads(f.read())

with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(executor.map(read_and_parse, json_paths))
```

**Action:** Add threaded JSON reading in orchestrator.py.

---

## P3: Moderate Returns (1-2 hours each)

### 10. Generator-Based Pipeline
**Effort:** 1 hour | **Impact:** Lower memory usage, faster startup

Process files as they're discovered rather than loading all paths into memory first.

```python
def scan_jsons(path):
    """Yield JSON paths as we find them."""
    for root, _, files in os.walk(path):
        for f in files:
            if f.endswith('.json'):
                yield os.path.join(root, f)

# Process as we find them
for jsonpath in scan_jsons(source_path):
    process(jsonpath)
```

**Action:** Refactor scanner.py to optionally yield results instead of collecting all.

---

### 11. Use __slots__ or NamedTuple for Data Classes
**Effort:** 20 minutes | **Impact:** 30-50% less memory, faster attribute access

Current dataclasses work fine, but for millions of files, memory adds up.

```python
# Option A: Add __slots__ to existing dataclass
@dataclass
class FileInfo:
    __slots__ = ['filename', 'filepath', 'albumname', 'procpath', 'jsonpath']
    filename: str
    filepath: str
    ...

# Option B: Use NamedTuple (immutable but lighter)
class FileInfo(NamedTuple):
    filename: str
    filepath: str
    albumname: str
```

**Action:** Add __slots__ to FileInfo and other high-volume dataclasses in models.py.

---

## P4: Significant Effort (Half day+)

### 12. Multiprocessing
**Effort:** 4-6 hours | **Impact:** 4-8x scaling with CPU cores

Split work across multiple processes for true parallelism.

```python
from multiprocessing import Pool

def process_chunk(json_chunk, file_index):
    results = []
    with ExifToolHelper() as et:
        for jsonpath in json_chunk:
            # Process and collect results
            ...
    return results

chunks = split_into_chunks(json_paths, num_processes=8)

with Pool(processes=8) as pool:
    all_results = pool.starmap(process_chunk,
                               [(chunk, file_index) for chunk in chunks])
```

**Considerations:**
- Each worker needs its own ExifTool process
- File index must be serialized or shared
- Aggregate results at the end
- More complex error handling

**Action:** Create parallel processing module when other optimizations are exhausted.

---

### 13. Producer-Consumer Architecture
**Effort:** 6 hours | **Impact:** Overlaps I/O with computation

Separate threads for different stages, connected by queues:

```
[Reader Thread] --> Queue --> [Processor Thread] --> Queue --> [Writer Thread]
     |                              |                              |
  Read JSONs                  Match files,               Call ExifTool
  from disk                   build tags                 in batches
```

**Action:** Consider after simpler threading approaches prove insufficient.

---

### 14. Async I/O with asyncio
**Effort:** 4 hours | **Impact:** Better I/O overlap

Async file reads can overlap with processing.

```python
import asyncio
import aiofiles

async def process_json(path, file_index):
    async with aiofiles.open(path, 'rb') as f:
        content = orjson.loads(await f.read())
    # ... process ...

async def main():
    tasks = [process_json(p, file_index) for p in json_paths]
    await asyncio.gather(*tasks)
```

**Action:** Consider if ThreadPoolExecutor approach proves insufficient.

---

## P5: Advanced/Specialized

### 15. SQLite Index for Huge Collections
**Effort:** 4 hours | **Impact:** Handles millions of files without memory issues

For collections too large to fit file index in RAM.

```python
conn.execute('''CREATE TABLE files
                (album TEXT, filename TEXT, filepath TEXT)''')
conn.execute('CREATE INDEX idx_lookup ON files(album, filename)')
```

**Action:** Only needed for extremely large collections (1M+ files).

---

### 16. Incremental Processing / Resume Support
**Effort:** 4 hours | **Impact:** Resume interrupted jobs

Write progress to state file, skip already-processed on restart.

**Action:** Consider for very long-running jobs.

---

### 17. PyPy Compatibility
**Effort:** Variable (testing) | **Impact:** 2-10x faster CPU-bound code

PyPy can dramatically speed up pure Python code but may have C extension issues.

**Action:** Test compatibility with pyexiftool and other dependencies.

---

### 18. Cython for Hot Paths
**Effort:** Significant | **Impact:** Near-C speed for critical loops

Compile hot path functions to C for maximum speed.

**Action:** Only if profiling shows specific Python bottlenecks.

---

## Measurement First

Before implementing optimizations, profile to find actual bottlenecks:

```python
import cProfile
import pstats

cProfile.run('main()', 'profile_output')

stats = pstats.Stats('profile_output')
stats.sort_stats('cumulative')
stats.print_stats(20)
```

Or use `py-spy` for sampling profiler:
```bash
py-spy record -o profile.svg -- python pef.py --path /your/takeout
```

---

## Summary Table

| # | Optimization | Effort | Impact | Priority |
|---|--------------|--------|--------|----------|
| 1 | orjson | 5 min | 3-10x JSON | P1 |
| 2 | Pre-filter JSONs | 10 min | Skip 20-50% | P1 |
| 3 | Pre-compile regex | 5 min | Minor | P1 |
| 4 | Single-pass scanning | 15 min | 2x scan speed | P1 |
| 5 | os.scandir | 15 min | 20-30% scan | P1 |
| 6 | ExifTool batching | 1-2 hrs | 10-50x exif | P2 |
| 7 | Skip tagged files | 1 hr | Huge on reruns | P2 |
| 8 | LRU cache | 30 min | Eliminate dup | P2 |
| 9 | Thread pool I/O | 1 hr | 2-4x I/O | P2 |
| 10 | Generator pipeline | 1 hr | Lower memory | P3 |
| 11 | __slots__ | 20 min | 30-50% memory | P3 |
| 12 | Multiprocessing | 4-6 hrs | 4-8x cores | P4 |
| 13 | Producer-Consumer | 6 hrs | Overlap I/O | P4 |
| 14 | Async I/O | 4 hrs | Better overlap | P4 |
| 15 | SQLite index | 4 hrs | Huge collections | P5 |
| 16 | Resume support | 4 hrs | Long jobs | P5 |
| 17 | PyPy | Variable | 2-10x CPU | P5 |
| 18 | Cython | Significant | Near-C speed | P5 |

---

## Recommended Implementation Order

**Phase 1 - Quick Wins (1 hour total):**
1. Add orjson dependency and update JSON parsing
2. Add pre-filter check before parsing
3. Remove double-pass in scanner
4. Switch to os.scandir

**Phase 2 - High Value (3-4 hours total):**
5. Implement ExifTool batching
6. Add skip-if-tagged check
7. Add LRU caching
8. Add thread pool for JSON reads

**Phase 3 - If Needed:**
9. Multiprocessing (if still too slow)
10. Other P4/P5 items based on profiling

**Expected Combined Improvement: 20-100x faster processing**
