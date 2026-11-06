import os
import sys
import heapq
import time
import argparse

def get_key_from_line(line, c_idx):
    start = 0
    for _ in range(c_idx):
        pos = line.find(',', start)
        if pos == -1: return ""
        start = pos + 1
    end = line.find(',', start)
    if end == -1: return line[start:].rstrip('\r\n')
    return line[start:end]

def normalize_line(line):
    """Сохраняет ширину 9 (например, 00042.50), чтобы лексикографическая сортировка работала."""
    try:
        parts = line.split(',', 3)
        if len(parts) >= 3:
            parts[2] = "%09.2f" % float(parts[2])
            return ','.join(parts)
    except (ValueError, IndexError):
        pass
    return line

def verify_sorted(path, k_col):
    prev = None
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            key = get_key_from_line(line.rstrip('\r\n'), k_col)
            if prev is not None and key < prev:
                print("VERIFY:FAIL at line %d: %r < %r" % (i, key, prev))
                return False
            prev = key
    print("VERIFY:OK (col %d)" % k_col)
    return True

def _merge_group(files, out_path, k_col):
    heap = []
    fds = []
    for i, p in enumerate(files):
        f = open(p, "r", encoding="utf-8")
        fds.append(f)
        line = f.readline()
        if line:
            line = line.rstrip('\r\n')
            sid = get_key_from_line(line, 0) # tie-break по id
            heapq.heappush(heap, (get_key_from_line(line, k_col), sid, i, line))

    with open(out_path, "w", encoding="utf-8", newline='\n') as out_f:
        while heap:
            _, _, f_id, line = heapq.heappop(heap)
            out_f.write(line + "\n")
            next_line = fds[f_id].readline()
            if next_line:
                next_line = next_line.rstrip('\r\n')
                sid = get_key_from_line(next_line, 0)
                heapq.heappush(heap, (get_key_from_line(next_line, k_col), sid, f_id, next_line))
    for f in fds: f.close()

def sort_ext(in_path, k_col, ch_mb, out_path=None, verify=False, fan_in=16):
    ch_bytes = ch_mb * 1024 * 1024
    tmp_dir = "./temp_chunks_py"
    if os.path.exists(tmp_dir):
        for f in os.listdir(tmp_dir): os.remove(os.path.join(tmp_dir, f))
        os.rmdir(tmp_dir)
    os.makedirs(tmp_dir, exist_ok=True)

    if out_path is None:
        out_path = os.path.join(os.path.dirname(os.path.abspath(in_path)), "sorted_py.txt")

    print("Python External Sort | Key: col[%d] | Chunk: %d MB..." % (k_col, ch_mb))
    sys.stdout.flush()

    total_bytes = os.path.getsize(in_path)
    t_s = time.time()
    tmp_files = []

    with open(in_path, "r", encoding="utf-8") as f_in:
        next(f_in, None)  # skip header
        buf = []
        cur_b = 0
        c_idx = 0
        bytes_processed = 0
        step = max(1, total_bytes // 200)
        last_report = 0

        def flush_buf():
            nonlocal buf, cur_b, c_idx
            if not buf: return
            buf.sort() # сортируем кортежи (key, line)
            tp = os.path.join(tmp_dir, "chunk_%d.tmp" % c_idx)
            with open(tp, "w", encoding="utf-8", newline='\n') as f_out:
                f_out.write("\n".join(l for _, l in buf) + "\n")
            tmp_files.append(tp)
            buf = []
            cur_b = 0
            c_idx += 1

        for line in f_in:
            line = line.rstrip('\r\n')
            if not line: continue
            norm = normalize_line(line)
            key = get_key_from_line(norm, k_col)
            buf.append((key, norm))
            row_bytes = len(norm) + 1
            cur_b += row_bytes
            bytes_processed += row_bytes

            if bytes_processed - last_report >= step:
                pct = min(40, int(bytes_processed * 40 / total_bytes))
                print("PROGRESS:%d" % pct); sys.stdout.flush()
                last_report = bytes_processed

            if cur_b >= ch_bytes: flush_buf()
        flush_buf()

    print("PROGRESS:40")
    t_e1 = time.time()
    print("Split time: %.2fs | Chunks: %d" % (t_e1 - t_s, len(tmp_files))); sys.stdout.flush()

    t_m_s = time.time()
    round_idx = 0
    while len(tmp_files) > fan_in:
        new_files = []
        for i in range(0, len(tmp_files), fan_in):
            group = tmp_files[i:i + fan_in]
            out_tmp = os.path.join(tmp_dir, "merge_%d_%d.tmp" % (round_idx, i))
            _merge_group(group, out_tmp, k_col)
            new_files.append(out_tmp)
        for f in tmp_files: os.remove(f)
        tmp_files = new_files
        round_idx += 1

    _merge_group(tmp_files, out_path, k_col)

    for f in tmp_files:
        try: os.remove(f)
        except OSError: pass
    try: os.rmdir(tmp_dir)
    except OSError: pass

    print("PROGRESS:100"); sys.stdout.flush()
    t_e2 = time.time()
    print("Merge time: %.2fs" % (t_e2 - t_m_s))
    print("Total time: %.2fs" % (t_e2 - t_s))
    print("Output: %s" % out_path)

    if verify: verify_sorted(out_path, k_col)
    print("Done.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default="data.csv")
    ap.add_argument("key", nargs="?", type=int, default=2)
    ap.add_argument("chunk_mb", nargs="?", type=int, default=50)
    ap.add_argument("--output", default=None)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--fan-in", type=int, default=16)
    args = ap.parse_args()
    sort_ext(args.input, args.key, args.chunk_mb, args.output, args.verify, args.fan_in)
