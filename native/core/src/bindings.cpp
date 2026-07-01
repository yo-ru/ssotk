#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <optional>

#include "ssotk/nebula.hpp"
#include "ssotk/text.hpp"
#include "ssotk/vocab.hpp"

namespace py = pybind11;

namespace {

py::str latin1_str(const std::string& s) {
    PyObject* o = PyUnicode_DecodeLatin1(s.data(), s.size(), "replace");
    return py::reinterpret_steal<py::str>(o);
}

py::list latin1_list(const std::vector<std::string>& v) {
    py::list out;
    for (auto& s : v) out.append(latin1_str(s));
    return out;
}

py::object decoded_to_py(const ssotk::nebula::DecodedValue& v, uint32_t raw_value) {
    return std::visit(
        [&](const auto& x) -> py::object {
            using T = std::decay_t<decltype(x)>;
            if constexpr (std::is_same_v<T, std::monostate>) {
                return py::int_(raw_value);
            } else if constexpr (std::is_same_v<T, int64_t>) {
                return py::int_(x);
            } else if constexpr (std::is_same_v<T, double>) {
                return py::float_(x);
            } else if constexpr (std::is_same_v<T, std::string>) {
                return latin1_str(x);
            } else if constexpr (std::is_same_v<T, std::array<float, 3>>) {
                return py::make_tuple(x[0], x[1], x[2]);
            } else if constexpr (std::is_same_v<T, std::array<float, 4>>) {
                return py::make_tuple(x[0], x[1], x[2], x[3]);
            } else if constexpr (std::is_same_v<T, std::array<uint32_t, 3>>) {
                return py::make_tuple(x[0], x[1], x[2]);
            } else if constexpr (std::is_same_v<T, std::array<uint8_t, 16>>) {
                return py::bytes(reinterpret_cast<const char*>(x.data()), x.size());
            }
            return py::none();
        },
        v);
}

}

PYBIND11_MODULE(_core, m) {
    py::module vocab = m.def_submodule("vocab");
    vocab.def(
        "deobfuscate",
        [](py::bytes data, uint8_t key) {
            std::string_view sv = data;
            return py::bytes(ssotk::vocab::deobfuscate(sv, key));
        },
        py::arg("data"), py::arg("key"));
    vocab.def(
        "auto_deobfuscate",
        [](py::bytes data) {
            std::string_view sv = data;
            auto [dec, key] = ssotk::vocab::auto_deobfuscate(sv);
            py::object k = key.has_value() ? py::cast(static_cast<int>(*key)) : py::none();
            return py::make_tuple(py::bytes(dec), k);
        },
        py::arg("data"));
    vocab.def("name_for_hash", &ssotk::vocab::name_for_hash, py::arg("h"));

    py::module nebula = m.def_submodule("nebula");

    py::class_<ssotk::nebula::Triple>(nebula, "Triple")
        .def_readonly("name_hash", &ssotk::nebula::Triple::name_hash)
        .def_readonly("value", &ssotk::nebula::Triple::value)
        .def_readonly("type_token", &ssotk::nebula::Triple::type_token)
        .def_property_readonly(
            "decoded",
            [](const ssotk::nebula::Triple& t) { return decoded_to_py(t.decoded, t.value); })
        .def_property_readonly(
            "name", [](const ssotk::nebula::Triple& t) {
                return ssotk::vocab::name_for_hash(t.name_hash);
            });

    py::class_<ssotk::nebula::Record>(nebula, "Record")
        .def_readonly("idx", &ssotk::nebula::Record::idx)
        .def_readonly("offset", &ssotk::nebula::Record::offset)
        .def_readonly("length", &ssotk::nebula::Record::length)
        .def_property_readonly(
            "raw",
            [](const ssotk::nebula::Record& r) {
                return py::bytes(reinterpret_cast<const char*>(r.raw.data()), r.raw.size());
            })
        .def_property_readonly(
            "text",
            [](const ssotk::nebula::Record& r) -> py::object {
                if (!r.text.has_value()) return py::none();
                return latin1_str(*r.text);
            })
        .def_property_readonly(
            "key", [](const ssotk::nebula::Record& r) {
                return r.key.has_value() ? py::cast(static_cast<int>(*r.key)) : py::none();
            });

    py::class_<ssotk::nebula::Object>(nebula, "Object")
        .def_readonly("offset", &ssotk::nebula::Object::offset)
        .def_readonly("size", &ssotk::nebula::Object::size)
        .def_readonly("triples", &ssotk::nebula::Object::triples)
        .def_readonly("records", &ssotk::nebula::Object::records)
        .def_property_readonly(
            "class_name",
            [](const ssotk::nebula::Object& o) -> py::object {
                auto v = o.class_name();
                if (!v.has_value()) return py::none();
                return latin1_str(*v);
            })
        .def_property_readonly(
            "strings",
            [](const ssotk::nebula::Object& o) { return latin1_list(o.strings()); })
        .def(
            "triple",
            [](const ssotk::nebula::Object& o, uint32_t h) {
                const ssotk::nebula::Triple* t = o.triple(h);
                return t ? py::cast(*t) : py::none();
            },
            py::arg("name_hash"))
        .def(
            "triples_of",
            [](const ssotk::nebula::Object& o, uint32_t h) {
                std::vector<ssotk::nebula::Triple> out;
                for (auto* t : o.triples_of(h)) out.push_back(*t);
                return out;
            },
            py::arg("name_hash"))
        .def(
            "get_int",
            [](const ssotk::nebula::Object& o, uint32_t h) {
                auto v = o.get_int(h);
                return v.has_value() ? py::cast(*v) : py::none();
            },
            py::arg("name_hash"))
        .def(
            "get_float",
            [](const ssotk::nebula::Object& o, uint32_t h) {
                auto v = o.get_float(h);
                return v.has_value() ? py::cast(*v) : py::none();
            },
            py::arg("name_hash"))
        .def(
            "get_bool",
            [](const ssotk::nebula::Object& o, uint32_t h) {
                auto v = o.get_bool(h);
                return v.has_value() ? py::cast(*v) : py::none();
            },
            py::arg("name_hash"))
        .def(
            "get_str",
            [](const ssotk::nebula::Object& o, uint32_t h) -> py::object {
                auto v = o.get_str(h);
                if (!v.has_value()) return py::none();
                return latin1_str(*v);
            },
            py::arg("name_hash"))
        .def(
            "get_string",
            [](const ssotk::nebula::Object& o, size_t i) -> py::object {
                auto v = o.get_string(i);
                if (!v.has_value()) return py::none();
                return latin1_str(*v);
            },
            py::arg("idx"));

    py::class_<ssotk::nebula::Scene>(nebula, "Scene")
        .def_readonly("total_size", &ssotk::nebula::Scene::total_size)
        .def_property_readonly(
            "root_class",
            [](const ssotk::nebula::Scene& s) -> py::object {
                if (!s.root_class.has_value()) return py::none();
                return latin1_str(*s.root_class);
            })
        .def_readonly("coverage", &ssotk::nebula::Scene::coverage)
        .def_readonly("object_count", &ssotk::nebula::Scene::object_count)
        .def_readonly("objects", &ssotk::nebula::Scene::objects)
        .def_readonly("unknown_tokens", &ssotk::nebula::Scene::unknown_tokens)
        .def_property_readonly(
            "strings", [](const ssotk::nebula::Scene& s) { return latin1_list(s.strings); })
        .def_property_readonly(
            "entries",
            [](const ssotk::nebula::Scene& s) {
                py::list out;
                for (const auto& obj : s.objects) {
                    for (const auto& t : obj.triples) {
                        py::dict e;
                        e["key"] = ssotk::vocab::name_for_hash(t.name_hash);
                        e["type"] = t.type_token;
                        e["value"] = decoded_to_py(t.decoded, t.value);
                        out.append(std::move(e));
                    }
                }
                return out;
            })
        .def(
            "object_by_own",
            [](const ssotk::nebula::Scene& s, uint32_t h) {
                const auto* o = s.object_by_own(h);
                return o ? py::cast(*o) : py::none();
            },
            py::arg("own_hash"))
        .def(
            "objects_with_parent",
            [](const ssotk::nebula::Scene& s, uint32_t h) {
                std::vector<ssotk::nebula::Object> out;
                for (const auto* o : s.objects_with_parent(h)) out.push_back(*o);
                return out;
            },
            py::arg("parent_own"))
        .def(
            "object_by_first_string",
            [](const ssotk::nebula::Scene& s, const std::string& n) {
                const auto* o = s.object_by_first_string(n);
                return o ? py::cast(*o) : py::none();
            },
            py::arg("name"));

    nebula.def(
        "parse",
        [](py::bytes data) {
            std::string_view sv = data;
            return ssotk::nebula::parse(sv);
        },
        py::arg("data"));
    nebula.def(
        "is_header_flavor",
        [](py::bytes data) {
            std::string_view sv = data;
            return ssotk::nebula::is_header_flavor(sv);
        },
        py::arg("data"));

    py::module text = m.def_submodule("text");
    text.def(
        "parse",
        [](py::bytes data) {
            std::string_view sv = data;
            auto table = ssotk::text::parse(sv);
            py::dict out;
            for (auto& [k, v] : table) {
                out[latin1_str(k)] = latin1_str(v);
            }
            return out;
        },
        py::arg("data"));
    text.def(
        "decode_value",
        [](py::bytes payload) {
            std::string_view sv = payload;
            auto v = ssotk::text::decode_value(sv);
            return v.has_value() ? py::cast(*v) : py::none();
        },
        py::arg("payload"));
}
