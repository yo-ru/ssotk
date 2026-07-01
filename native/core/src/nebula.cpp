#include "ssotk/nebula.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cstring>
#include <unordered_map>

#include "ssotk/vocab.hpp"

namespace ssotk::nebula {

namespace {

constexpr size_t   PREAMBLE_LEN        = 0x1C;
constexpr size_t   TRIPLE_LEN          = 12;
constexpr size_t   SENTINEL_OFF        = 0x14;
constexpr uint32_t SENTINEL            = 0xFFFFFFFFu;
constexpr size_t   HEADER_PREAMBLE     = 8;
constexpr size_t   HEADER_SENTINEL_OFF = 0x0C;

inline uint32_t read_u32(std::string_view data, size_t off) {
    uint32_t v;
    std::memcpy(&v, data.data() + off, sizeof(v));
    return v;
}

inline float as_float(uint32_t bits) {
    return std::bit_cast<float>(bits);
}

std::string_view rstrip_nulls(std::string_view s) {
    size_t n = s.size();
    while (n > 0 && s[n - 1] == '\0') --n;
    return s.substr(0, n);
}

bool has_alpha(std::string_view s) {
    for (unsigned char c : s) {
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) return true;
    }
    return false;
}

bool is_printable(std::string_view s) {
    if (s.empty()) return false;
    for (unsigned char c : s) {
        if (c < 0x20 || (c >= 0x7F && c < 0xA0)) return false;
    }
    return true;
}

size_t string_table_start(std::string_view data, size_t base) {
    uint32_t count = read_u32(data, base + 8);
    return base + PREAMBLE_LEN + TRIPLE_LEN * (count - 1);
}

struct RecordParseResult {
    size_t rec_end;
    std::unordered_map<size_t, size_t> by_offset;
};

RecordParseResult parse_record_stream(
    std::string_view data, size_t start, size_t end, Object& obj) {
    RecordParseResult res{start, {}};
    size_t o = start;
    size_t idx = 0;

    while (o + 4 <= end) {
        uint32_t length = read_u32(data, o);
        if (length == 0 || o + 4 + length > end) break;

        Record rec;
        rec.idx = idx;
        rec.offset = o;
        rec.length = length;
        rec.raw.assign(
            reinterpret_cast<const uint8_t*>(data.data() + o + 4),
            reinterpret_cast<const uint8_t*>(data.data() + o + 4 + length));

        auto stripped = rstrip_nulls(
            std::string_view(reinterpret_cast<const char*>(rec.raw.data()), rec.raw.size()));
        auto [dec, key] = vocab::auto_deobfuscate(stripped);
        if (key.has_value()) {
            rec.key = key;
            if (dec.size() >= 3 && is_printable(dec) && has_alpha(dec)) {
                rec.text = dec;
            }
        }
        if (!rec.text.has_value() && stripped.size() >= 3) {
            std::string plain(stripped);
            if (is_printable(plain) && has_alpha(plain)) {
                rec.text = plain;
            }
        }

        obj.records.push_back(std::move(rec));
        res.by_offset[o - start] = obj.records.size() - 1;
        ++idx;
        o += 4 + length;
    }

    if (o < end) {
        bool all_zero = true;
        for (size_t i = o; i < end; ++i) {
            if (data[i] != '\0') { all_zero = false; break; }
        }
        if (all_zero) o = end;
    }
    res.rec_end = o;
    return res;
}

void decode_body(
    std::string_view data, size_t start, size_t end, Scene& scene, Object& obj,
    const std::unordered_map<size_t, size_t>& records_by_offset) {
    size_t o = start;
    while (o + TRIPLE_LEN <= end) {
        uint32_t name_hash = read_u32(data, o);
        uint32_t value = read_u32(data, o + 4);
        uint32_t token = read_u32(data, o + 8);
        Triple t{name_hash, value, token, {}};

        auto lookup_record = [&]() -> const Record* {
            auto it = records_by_offset.find(value);
            if (it == records_by_offset.end()) return nullptr;
            return &obj.records[it->second];
        };

        switch (token) {
            case 0x0100:
            case 0x0A02:
            case 0x0A0E:
                t.decoded = static_cast<int64_t>(value);
                break;
            case 0x0A03:
                t.decoded = static_cast<double>(as_float(value));
                break;
            case 0x0204: {
                const Record* r = lookup_record();
                if (r) {
                    if (r->text.has_value()) {
                        t.decoded = *r->text;
                    } else {
                        auto stripped = rstrip_nulls(std::string_view(
                            reinterpret_cast<const char*>(r->raw.data()), r->raw.size()));
                        if (!stripped.empty()) t.decoded = std::string(stripped);
                    }
                }
                break;
            }
            case 0x0207: {
                const Record* r = lookup_record();
                if (r && r->length >= 12) {
                    std::array<float, 3> v;
                    std::memcpy(&v, r->raw.data(), sizeof(v));
                    t.decoded = v;
                }
                break;
            }
            case 0x0209:
            case 0x020A: {
                const Record* r = lookup_record();
                if (r && r->length >= 16) {
                    std::array<float, 4> v;
                    std::memcpy(&v, r->raw.data(), sizeof(v));
                    t.decoded = v;
                }
                break;
            }
            case 0x0410: {
                const Record* r = lookup_record();
                if (r && r->length >= 16) {
                    std::array<uint8_t, 16> g;
                    std::memcpy(g.data(), r->raw.data(), 16);
                    t.decoded = g;
                }
                break;
            }
            case 0x0402: {
                const Record* r = lookup_record();
                if (r && r->length >= 12) {
                    std::array<uint32_t, 3> v;
                    std::memcpy(&v, r->raw.data(), sizeof(v));
                    t.decoded = v;
                }
                break;
            }
            default:
                scene.unknown_tokens.push_back(token);
                break;
        }

        obj.triples.push_back(std::move(t));
        o += TRIPLE_LEN;
    }
}

Scene parse_header(std::string_view data) {
    Scene scene;
    scene.total_size = data.size();
    size_t n = data.size();

    uint32_t count = read_u32(data, 0);
    size_t table_start = HEADER_PREAMBLE + TRIPLE_LEN * count;
    if (table_start > n) return scene;

    Object obj;
    obj.offset = 0;
    obj.size = static_cast<uint32_t>(n);
    auto rec = parse_record_stream(data, table_start, n, obj);
    decode_body(data, HEADER_PREAMBLE, table_start, scene, obj, rec.by_offset);

    scene.objects.push_back(std::move(obj));
    scene.strings = scene.objects[0].strings();
    scene.root_class = scene.objects[0].class_name();
    scene.object_count = 1;
    scene.coverage = data.empty() ? 1.0 : static_cast<double>(rec.rec_end) / n;
    return scene;
}

}

bool is_header_flavor(std::string_view data) {
    return data.size() >= HEADER_SENTINEL_OFF + 4 &&
           read_u32(data, HEADER_SENTINEL_OFF) == SENTINEL;
}

Scene parse(std::string_view data) {
    if (is_header_flavor(data)) return parse_header(data);

    Scene scene;
    scene.total_size = data.size();
    size_t n = data.size();
    size_t consumed = 0;
    size_t o = 0;

    while (o + PREAMBLE_LEN <= n) {
        uint32_t size = read_u32(data, o);
        uint32_t sentinel = read_u32(data, o + SENTINEL_OFF);
        if (sentinel != SENTINEL || size < PREAMBLE_LEN || o + size > n) break;

        Object obj;
        obj.offset = o;
        obj.size = size;
        size_t obj_end = o + size;
        size_t table_start = string_table_start(data, o);

        auto rec = parse_record_stream(data, table_start, obj_end, obj);
        decode_body(data, o + PREAMBLE_LEN, table_start, scene, obj, rec.by_offset);

        auto strs = obj.strings();
        if (!scene.root_class.has_value()) {
            if (auto cls = obj.class_name(); cls.has_value()) {
                scene.root_class = cls;
            }
        }
        scene.strings.insert(scene.strings.end(), strs.begin(), strs.end());
        scene.objects.push_back(std::move(obj));

        consumed += rec.rec_end - o;
        ++scene.object_count;
        o = obj_end;
    }

    scene.coverage = data.empty() ? 1.0 : static_cast<double>(consumed) / n;
    return scene;
}

std::optional<std::string> Object::class_name() const {
    for (const auto& r : records) {
        if (r.text.has_value()) return r.text;
    }
    return std::nullopt;
}

std::vector<std::string> Object::strings() const {
    std::vector<std::string> out;
    for (const auto& r : records) {
        if (r.text.has_value()) out.push_back(*r.text);
    }
    return out;
}

const Triple* Object::triple(uint32_t name_hash) const {
    for (const auto& t : triples) {
        if (t.name_hash == name_hash) return &t;
    }
    return nullptr;
}

std::vector<const Triple*> Object::triples_of(uint32_t name_hash) const {
    std::vector<const Triple*> out;
    for (const auto& t : triples) {
        if (t.name_hash == name_hash) out.push_back(&t);
    }
    return out;
}

std::optional<int64_t> Object::get_int(uint32_t name_hash) const {
    const Triple* t = triple(name_hash);
    if (!t) return std::nullopt;
    if (const auto* p = std::get_if<int64_t>(&t->decoded)) return *p;
    return static_cast<int64_t>(t->value);
}

std::optional<double> Object::get_float(uint32_t name_hash) const {
    const Triple* t = triple(name_hash);
    if (!t) return std::nullopt;
    if (const auto* p = std::get_if<double>(&t->decoded)) return *p;
    return static_cast<double>(as_float(t->value));
}

std::optional<bool> Object::get_bool(uint32_t name_hash) const {
    const Triple* t = triple(name_hash);
    if (!t) return std::nullopt;
    return t->value != 0;
}

std::optional<std::string> Object::get_str(uint32_t name_hash) const {
    const Triple* t = triple(name_hash);
    if (!t) return std::nullopt;
    if (const auto* p = std::get_if<std::string>(&t->decoded)) return *p;
    return std::nullopt;
}

std::optional<std::string> Object::get_string(size_t idx) const {
    size_t i = 0;
    for (const auto& r : records) {
        if (!r.text.has_value()) continue;
        if (i == idx) return r.text;
        ++i;
    }
    return std::nullopt;
}

const Object* Scene::object_by_own(uint32_t own_hash) const {
    for (const auto& obj : objects) {
        const Triple* t = obj.triple(vocab::KH::OWN);
        if (t && t->value == own_hash) return &obj;
    }
    return nullptr;
}

std::vector<const Object*> Scene::objects_with_parent(uint32_t parent_own) const {
    std::vector<const Object*> out;
    for (const auto& obj : objects) {
        const Triple* t = obj.triple(vocab::KH::PARENT);
        if (t && t->value == parent_own) out.push_back(&obj);
    }
    return out;
}

const Object* Scene::object_by_first_string(std::string_view name) const {
    for (const auto& obj : objects) {
        auto cls = obj.class_name();
        if (cls.has_value() && *cls == name) return &obj;
    }
    return nullptr;
}

}
