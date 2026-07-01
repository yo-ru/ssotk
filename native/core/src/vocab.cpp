#include "ssotk/vocab.hpp"

#include <array>
#include <cstdio>

namespace ssotk::vocab {

namespace {

constexpr std::array<bool, 256> make_name_charset() {
    std::array<bool, 256> t{};
    for (int c = 'a'; c <= 'z'; ++c) t[c] = true;
    for (int c = 'A'; c <= 'Z'; ++c) t[c] = true;
    for (int c = '0'; c <= '9'; ++c) t[c] = true;
    for (unsigned char c : std::string_view("/\\._- ")) t[c] = true;
    return t;
}

constexpr auto NAME_CHARS = make_name_charset();

bool looks_text(std::string_view b) {
    if (b.empty()) return false;
    for (unsigned char c : b) {
        if (!NAME_CHARS[c]) return false;
    }
    return true;
}

}

std::string deobfuscate(std::string_view in, uint8_t key) {
    std::string out(in.size(), '\0');
    for (size_t i = 0; i < in.size(); ++i) {
        out[i] = static_cast<char>((static_cast<uint8_t>(in[i]) + key) & 0xFF);
    }
    return out;
}

std::pair<std::string, std::optional<uint8_t>> auto_deobfuscate(std::string_view data) {
    if (looks_text(data)) return {std::string(data), uint8_t{0}};
    if (data.empty())     return {std::string(data), std::nullopt};
    for (int key = 1; key < 256; ++key) {
        bool ok = true;
        for (unsigned char c : data) {
            if (!NAME_CHARS[static_cast<uint8_t>((c + key) & 0xFF)]) { ok = false; break; }
        }
        if (ok) return {deobfuscate(data, static_cast<uint8_t>(key)), static_cast<uint8_t>(key)};
    }
    return {std::string(data), std::nullopt};
}

const std::unordered_map<uint32_t, std::string>& hash_names() {
    static const std::unordered_map<uint32_t, std::string> table = {
        {KH::OFFSET,      "offset"},
        {KH::SIZE,        "size"},
        {KH::NAME_OFFSET, "name_offset"},
        {KH::EXTRACT,     "extract"},
        {KH::OWN,         "own"},
        {KH::PARENT,      "parent"},
        {KH::ID,          "id"},
        {KH::BREED_ID,    "breed_id"},
        {KH::PRICE,       "price"},
        {KH::JS_PRICE,    "price_js"},
        {KH::SC_PRICE,    "price_sc"},
        {KH::LEVEL,       "level"},
    };
    return table;
}

std::string name_for_hash(uint32_t h) {
    const auto& t = hash_names();
    auto it = t.find(h);
    if (it != t.end()) return it->second;
    char buf[16];
    std::snprintf(buf, sizeof(buf), "0x%08x", h);
    return std::string(buf);
}

}
