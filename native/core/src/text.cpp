#include "ssotk/text.hpp"

#include <cstdint>
#include <cstring>

namespace ssotk::text {

namespace {

constexpr size_t HEADER_LEN = 0x10;

inline uint16_t read_u16(std::string_view d, size_t off) {
    uint16_t v;
    std::memcpy(&v, d.data() + off, sizeof(v));
    return v;
}

inline uint32_t read_u32(std::string_view d, size_t off) {
    uint32_t v;
    std::memcpy(&v, d.data() + off, sizeof(v));
    return v;
}

}

std::optional<std::string> decode_value(std::string_view payload) {
    if (payload.size() < 4) return std::nullopt;
    if (static_cast<uint8_t>(payload[0]) != 0x05 ||
        static_cast<uint8_t>(payload[1]) != 0x00 ||
        static_cast<uint8_t>(payload[2]) != 0x01) {
        return std::nullopt;
    }
    uint8_t first_low = static_cast<uint8_t>(payload[3]);
    std::string chars;
    std::optional<uint8_t> first_high;

    size_t i = 4;
    while (i + 1 < payload.size()) {
        uint8_t high = static_cast<uint8_t>(payload[i]);
        uint8_t low = static_cast<uint8_t>(payload[i + 1]);
        if (high == 0 && low == 0) break;
        if (!first_high.has_value()) first_high = high;
        uint8_t shift = (0x100 - high) & 0xFF;
        chars.push_back(static_cast<char>((low + shift) & 0xFF));
        i += 2;
    }
    if (!first_high.has_value()) first_high = 0xFF;
    uint8_t first_shift = (0x100 - *first_high) & 0xFF;
    char first_char = static_cast<char>((first_low + first_shift) & 0xFF);
    std::string out;
    out.push_back(first_char);
    out.append(chars);
    return out;
}

std::unordered_map<std::string, std::string> parse(std::string_view data) {
    std::unordered_map<std::string, std::string> out;
    size_t off = HEADER_LEN;
    size_t n = data.size();

    while (off + 16 < n) {
        uint16_t key_len = read_u16(data, off);
        uint8_t pad = static_cast<uint8_t>(data[off + 2]);
        uint8_t shift = static_cast<uint8_t>(data[off + 3]);
        if (key_len == 0 || key_len > 256 || pad != 0) { ++off; continue; }

        size_t key_start = off + 4;
        if (key_start + key_len + 12 > n) { ++off; continue; }

        uint32_t sa = read_u32(data, key_start + key_len);
        uint32_t sb = read_u32(data, key_start + key_len + 4);
        if (sa != 0 || sb != 1) { ++off; continue; }

        uint32_t vbc = read_u32(data, key_start + key_len + 8);
        size_t payload_off = key_start + key_len + 12;
        if (payload_off + vbc + 2 > n) { ++off; continue; }

        std::string key;
        key.reserve(key_len);
        for (size_t i = 0; i < key_len; ++i) {
            key.push_back(static_cast<char>((static_cast<uint8_t>(data[key_start + i]) + shift) & 0xFF));
        }
        size_t front = 0;
        while (front < key.size() && key[front] == '\t') ++front;
        key.erase(0, front);

        std::string payload_with_term(data.substr(payload_off, vbc));
        payload_with_term.push_back('\0');
        payload_with_term.push_back('\0');
        auto value = decode_value(payload_with_term);
        if (value.has_value()) {
            while (!value->empty() && value->back() == '\0') value->pop_back();
            out.emplace(std::move(key), std::move(*value));
        }
        off = payload_off + vbc + 2;
    }

    return out;
}

}
