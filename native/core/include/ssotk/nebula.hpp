#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

namespace ssotk::nebula {

using DecodedValue = std::variant<
    std::monostate,
    int64_t,
    double,
    std::string,
    std::array<float, 3>,
    std::array<float, 4>,
    std::array<uint32_t, 3>,
    std::array<uint8_t, 16>
>;

struct Triple {
    uint32_t name_hash;
    uint32_t value;
    uint32_t type_token;
    DecodedValue decoded;
};

struct Record {
    size_t idx;
    size_t offset;
    uint32_t length;
    std::vector<uint8_t> raw;
    std::optional<std::string> text;
    std::optional<uint8_t> key;
};

struct Object {
    size_t offset;
    uint32_t size;
    std::vector<Triple> triples;
    std::vector<Record> records;

    std::optional<std::string> class_name() const;
    std::vector<std::string> strings() const;

    const Triple* triple(uint32_t name_hash) const;
    std::vector<const Triple*> triples_of(uint32_t name_hash) const;

    std::optional<int64_t> get_int(uint32_t name_hash) const;
    std::optional<double> get_float(uint32_t name_hash) const;
    std::optional<bool> get_bool(uint32_t name_hash) const;
    std::optional<std::string> get_str(uint32_t name_hash) const;
    std::optional<std::string> get_string(size_t idx) const;
};

struct Scene {
    size_t total_size = 0;
    std::optional<std::string> root_class;
    double coverage = 0.0;
    size_t object_count = 0;
    std::vector<Object> objects;
    std::vector<uint32_t> unknown_tokens;
    std::vector<std::string> strings;

    const Object* object_by_own(uint32_t own_hash) const;
    std::vector<const Object*> objects_with_parent(uint32_t parent_own) const;
    const Object* object_by_first_string(std::string_view name) const;
};

Scene parse(std::string_view data);
bool is_header_flavor(std::string_view data);

}
