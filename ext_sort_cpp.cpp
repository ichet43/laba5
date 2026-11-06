#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <algorithm>
#include <queue>
#include <chrono>
#include <filesystem>
#include <cstdio>
#include <cstring>

using namespace std;
namespace fs = filesystem;

// Структура для хранения строки и её ключа (используется при сортировке чанка)
struct Row {
    string key;
    string line;
};

static string get_key(const string& line, int c_idx) {
    int start = 0, found = 0;
    int len = (int)line.size();
    for (int i = 0; i < len; ++i) {
        if (line[i] == ',') {
            if (found == c_idx) return line.substr(start, i - start);
            start = i + 1;
            found++;
        }
    }
    if (found == c_idx) {
        int end = len;
        while (end > start && (line[end-1] == '\r' || line[end-1] == '\n')) --end;
        return line.substr(start, end - start);
    }
    return "";
}

static string normalize_weight(const string& w_str) {
    try {
        double w = stod(w_str);
        char buffer[50];
        snprintf(buffer, sizeof(buffer), "%09.2f", w);
        return string(buffer);
    } catch (...) { return w_str; }
}

static string normalize_row(const string& line) {
    int comma2 = -1, comma3 = -1, count = 0;
    int len = (int)line.size();
    for (int i = 0; i < len && count < 3; ++i) {
        if (line[i] == ',') {
            if (count == 1) comma2 = i;
            else if (count == 2) comma3 = i;
            count++;
        }
    }
    if (comma2 != -1 && comma3 != -1) {
        string w_str = line.substr(comma2 + 1, comma3 - comma2 - 1);
        string norm_w = normalize_weight(w_str);
        return line.substr(0, comma2 + 1) + norm_w + line.substr(comma3);
    }
    return line;
}

static void merge_group(const vector<fs::path>& files, const fs::path& out_path, int k_col) {
    struct Item {
        string key;
        string sid;
        int id;
        string line;
    };

    auto cmp = [](const Item& a, const Item& b) {
        if (a.key != b.key) return a.key > b.key;
        if (a.sid != b.sid) return a.sid > b.sid;
        return a.line > b.line;
    };

    priority_queue<Item, vector<Item>, decltype(cmp)> pq(cmp);
    vector<ifstream> fds(files.size());

    for (size_t i = 0; i < files.size(); ++i) {
        fds[i].open(files[i], ios::binary);
        string line;
        if (getline(fds[i], line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            pq.push({get_key(line, k_col), get_key(line, 0), (int)i, line});
        }
    }

    ofstream out_s(out_path, ios::binary);
    while (!pq.empty()) {
        auto top = pq.top(); pq.pop();
        out_s << top.line << "\n";

        int id = top.id;
        string line;
        if (getline(fds[id], line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            pq.push({get_key(line, k_col), get_key(line, 0), id, line});
        }
    }
    out_s.close();
    for (auto& f : fds) f.close();
}

static bool verify_sorted(const string& path, int k_col) {
    ifstream f(path, ios::binary);
    string line, prev;
    bool first = true;
    long long idx = 0;
    while (getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        string key = get_key(line, k_col);
        if (!first && key < prev) {
            cerr << "VERIFY:FAIL at line " << idx << endl;
            return false;
        }
        prev = key;
        first = false;
        idx++;
    }
    cout << "VERIFY:OK (col " << k_col << ")" << endl;
    return true;
}

int main(int argc, char* argv[]) {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);

    if (argc < 3) {
        cerr << "Usage: ext_sort_cpp <input.csv> <key_idx(0-3)> [chunk_mb] [--output path] [--verify]" << endl;
        return 1;
    }

    string in_p = argv[1];
    int k_col = stoi(argv[2]);
    size_t ch_mb = (argc > 3) ? stoul(argv[3]) : 50;
    size_t ch_bytes = ch_mb * 1024ULL * 1024ULL;

    string out_path;
    bool do_verify = false;
    int fan_in = 16;
    for (int i = 4; i < argc; ++i) {
        if (strcmp(argv[i], "--verify") == 0) do_verify = true;
        else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc) out_path = argv[++i];
        else if (strcmp(argv[i], "--fan-in") == 0 && i + 1 < argc) fan_in = stoi(argv[++i]);
    }
    if (out_path.empty()) {
        out_path = (fs::path(in_p).parent_path() / "sorted_cpp.txt").string();
    }

    if (!fs::exists(in_p)) {
        cerr << "File not found: " << in_p << endl;
        return 1;
    }

    cout << "C++ External Sort | Key: col[" << k_col << "] | Chunk: " << ch_mb << " MB..." << endl;

    fs::path tmp_dir = "./temp_chunks_cpp";
    if (fs::exists(tmp_dir)) fs::remove_all(tmp_dir);
    fs::create_directories(tmp_dir);

    uintmax_t input_size = fs::file_size(in_p);
    auto t_s = chrono::high_resolution_clock::now();
    vector<fs::path> tmp_files;
    ifstream inf(in_p, ios::binary);
    string line;
    getline(inf, line); // skip header

    vector<Row> buf;
    buf.reserve(500000);
    size_t cur_bytes = 0, total_read = 0;
    int c_idx = 0, last_pct = -1;
    size_t step = input_size / 200 + 1;

    auto flush_buf = [&]() {
        if (buf.empty()) return;
        sort(buf.begin(), buf.end(), [k_col](const Row& a, const Row& b) {
            if (a.key != b.key) return a.key < b.key;
            string sid_a = get_key(a.line, 0);
            string sid_b = get_key(b.line, 0);
            if (sid_a != sid_b) return sid_a < sid_b;
            return a.line < b.line;
        });
        fs::path tmp = tmp_dir / ("chunk_" + to_string(c_idx++) + ".tmp");
        ofstream out(tmp, ios::binary);
        for (const auto& r : buf) out << r.line << "\n";
        out.close();
        tmp_files.push_back(tmp);
        cur_bytes = 0;
        buf.clear();

        int pct = min(40, (int)((total_read * 40) / input_size));
        if (pct != last_pct) { cout << "PROGRESS:" << pct << endl; last_pct = pct; }
    };

    while (getline(inf, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;

        string norm = normalize_row(line);
        Row r;
        r.line = norm;
        r.key = get_key(norm, k_col);
        buf.push_back(std::move(r));

        size_t line_len = norm.size() + 1;
        cur_bytes += line_len;
        total_read += line_len;

        if (total_read - (size_t)(last_pct) * step >= step) {
            int pct = min(40, (int)((total_read * 40) / input_size));
            if (pct != last_pct) { cout << "PROGRESS:" << pct << endl; last_pct = pct; }
        }
        if (cur_bytes >= ch_bytes) flush_buf();
    }
    flush_buf();
    inf.close();
    cout << "PROGRESS:40" << endl;

    auto t_e1 = chrono::high_resolution_clock::now();
    cout << "Split time: " << chrono::duration<double>(t_e1 - t_s).count() << "s | Chunks: " << c_idx << endl;

    auto t_m_s = chrono::high_resolution_clock::now();
    int round_idx = 0;
    while ((int)tmp_files.size() > fan_in) {
        vector<fs::path> new_files;
        for (size_t i = 0; i < tmp_files.size(); i += fan_in) {
            vector<fs::path> group(tmp_files.begin() + i, tmp_files.begin() + min(tmp_files.size(), i + fan_in));
            fs::path out_tmp = tmp_dir / ("merge_" + to_string(round_idx) + "_" + to_string(i) + ".tmp");
            merge_group(group, out_tmp, k_col);
            new_files.push_back(out_tmp);
        }
        for (auto& f : tmp_files) { try { fs::remove(f); } catch (...) {} }
        tmp_files = std::move(new_files);
        round_idx++;
    }

    merge_group(tmp_files, fs::path(out_path), k_col);

    for (auto& f : tmp_files) { try { fs::remove(f); } catch (...) {} }
    try { fs::remove_all(tmp_dir); } catch (...) {}

    auto t_e2 = chrono::high_resolution_clock::now();
    cout << "PROGRESS:100" << endl;
    cout << "Merge time: " << chrono::duration<double>(t_e2 - t_m_s).count() << "s" << endl;
    cout << "Total time: " << chrono::duration<double>(t_e2 - t_s).count() << "s" << endl;
    cout << "Output: " << out_path << endl;

    if (do_verify) verify_sorted(out_path, k_col);
    cout << "Done." << endl;
    return 0;
}
