#pragma once

#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>

namespace ssotk::text {

std::optional<std::string> decode_value(std::string_view payload);
std::unordered_map<std::string, std::string> parse(std::string_view data);

}
