#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>

namespace ssotk::vocab {

struct KH {
    static constexpr uint32_t OFFSET      = 0x0B6EF964;
    static constexpr uint32_t SIZE        = 0x0B1A6E08;
    static constexpr uint32_t NAME_OFFSET = 0x01C65A88;
    static constexpr uint32_t EXTRACT     = 0x0E89DE15;
    static constexpr uint32_t OWN         = 0x06D029F4;
    static constexpr uint32_t PARENT      = 0x0FA8A5A4;
    static constexpr uint32_t ID          = 0x040034D4;
    static constexpr uint32_t BREED_ID    = 0x0BB21504;
    static constexpr uint32_t PRICE       = 0x01DA6705;
    static constexpr uint32_t JS_PRICE    = 0x088D4FB5;
    static constexpr uint32_t SC_PRICE    = 0x008D4FA5;
    static constexpr uint32_t LEVEL       = 0x06A98294;
};

std::string deobfuscate(std::string_view in, uint8_t key);
std::pair<std::string, std::optional<uint8_t>> auto_deobfuscate(std::string_view data);
std::string name_for_hash(uint32_t h);
const std::unordered_map<uint32_t, std::string>& hash_names();

}
