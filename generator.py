import csv
import random
import os
import sys

CITIES = ["Moscow", "Saint Petersburg", "Novosibirsk", "Yekaterinburg", "Kazan",
          "Nizhny Novgorod", "Chelyabinsk", "Samara", "Omsk", "Rostov-on-Don"]
STATUSES = ["In Transit", "Delivered", "Processing", "Returned", "Delayed"]


def gen_csv(fn="data.csv", tgt_gb=1.05):
    tgt_bytes = int(tgt_gb * 1024**3)
    print("Starting generation of %s (target: %.2f GB)..." % (fn, tgt_gb))
    sys.stdout.flush()

    step = max(1, tgt_bytes // 100)
    last_report = 0
    written = 0

    with open(fn, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["shipment_id", "destination_city", "weight_kg", "status"])
        buf = []

        while written < tgt_bytes:
            rand_id = "%08d" % random.randint(10000000, 99999999)
            weight_padded = "%09.2f" % random.uniform(0.5, 1500.0)
            row = [rand_id, random.choice(CITIES), weight_padded, random.choice(STATUSES)]
            line = ",".join(row) + "\r\n"
            buf.append(line)
            written += len(line)

            if written - last_report >= step:
                print("PROGRESS:%d" % min(99, int(written * 100 / tgt_bytes)))
                sys.stdout.flush()
                last_report = written

            if len(buf) >= 10000:
                f.writelines(buf)
                buf.clear()

        if buf:
            f.writelines(buf)

    final_size = os.path.getsize(fn)
    print("PROGRESS:100")
    print("Generation complete. Size: %.2f GB" % (final_size / 1024**3))
    sys.stdout.flush()


if __name__ == "__main__":
    size = float(sys.argv[1]) if len(sys.argv) > 1 else 1.05
    out = sys.argv[2] if len(sys.argv) > 2 else "data.csv"
    gen_csv(out, size)
