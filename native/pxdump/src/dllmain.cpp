#include <windows.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <unordered_set>

#include "MinHook.h"

namespace {

char dump_path[MAX_PATH] = "C:\\tmp\\pxscript_dump.txt";

using PXInterp = char(*)(void*, int32_t*, void*, int);
PXInterp original = nullptr;

std::unordered_set<uintptr_t> seen_programs;
std::mutex seen_mutex;

const char* OPS[] = {
    "PUSH_CONST", "STORE_VAR", "STORE_VAR2", "DECL_VAR", "PUSH_VAL", "POP",
    "ACTOR_REF", "JUMP", "LOOP", "JZ", "EQ", "NE", "LT", "GT", "LE", "GE", "OR",
    "AND", "ADD", "SUB", "MUL", "DIV", "NEG", "CONCAT", "CALL", "CALL2",
    "RET_TRUE", "RET_FALSE", "TOSTRING", "END", "RESUME",
};

// Reads from live game memory must never fault the game thread.
bool safe_read(const void* src, void* dst, size_t n) {
    __try {
        memcpy(dst, src, n);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

template <class T>
bool rd(uintptr_t ea, T& out) {
    return ea && safe_read(reinterpret_cast<const void*>(ea), &out, sizeof(T));
}

void operand_str(uintptr_t op_ea, char* buf, size_t bufsz) {
    uint8_t type = 0;
    uintptr_t dptr = 0;
    uint32_t len = 0;
    rd(op_ea + 12, type);
    rd(op_ea + 0, dptr);
    rd(op_ea + 8, len);
    if (type == 4 || type == 5) {
        if (dptr && len && len < 4096) {
            char tmp[4096];
            size_t k = len < sizeof(tmp) - 1 ? len : sizeof(tmp) - 1;
            if (safe_read(reinterpret_cast<const void*>(dptr), tmp, k)) {
                tmp[k] = 0;
                if (char* nul = static_cast<char*>(memchr(tmp, 0, k))) *nul = 0;
                snprintf(buf, bufsz, "'%s'", tmp);
                return;
            }
        }
        snprintf(buf, bufsz, "<str>");
        return;
    }
    if (type == 1 || type == 2) {
        int32_t v = 0;
        if (rd(dptr, v)) { snprintf(buf, bufsz, "%d", v); return; }
    } else if (type == 3) {
        float f = 0;
        if (rd(dptr, f)) { snprintf(buf, bufsz, "%.6g", f); return; }
    } else if (type == 0x0E) {
        uint8_t b = 0;
        if (rd(dptr, b)) { snprintf(buf, bufsz, "%s", b ? "true" : "false"); return; }
    }
    snprintf(buf, bufsz, "<t%d>", type);
}

void dump_program(int32_t* program) {
    uint32_t count = 0;
    uintptr_t instrs = 0;
    if (!rd(reinterpret_cast<uintptr_t>(program), count)) return;
    if (!rd(reinterpret_cast<uintptr_t>(program) + 8, instrs)) return;
    if (!count || !instrs || count > 200000) return;
    {
        std::lock_guard<std::mutex> lock(seen_mutex);
        if (seen_programs.count(instrs)) return;
        seen_programs.insert(instrs);
    }
    FILE* f = fopen(dump_path, "a");
    if (!f) return;
    fprintf(f, "=== program @0x%llx  count=%u ===\n",
            static_cast<unsigned long long>(instrs), count);
    for (uint32_t i = 0; i < count; ++i) {
        uintptr_t ins = instrs + 32ull * i;
        uint8_t op = 0;
        uint32_t line = 0;
        if (!rd(ins, op)) break;
        rd(ins + 4, line);
        char opbuf[16];
        const char* mn = op <= 0x1E ? OPS[op] : (snprintf(opbuf, sizeof(opbuf), "OP%02X", op), opbuf);
        char arg[4100];
        operand_str(ins + 8, arg, sizeof(arg));
        fprintf(f, "  %4u  L%-5u %-10s %s\n", i, line, mn, arg);
    }
    fprintf(f, "\n");
    fclose(f);
}

char hook(void* a1, int32_t* program, void* a3, int a4) {
    dump_program(program);
    return original(a1, program, a3, a4);
}

// Signature scanner. Locates the PXScript interpreter by finding a stable
// string literal and walking backwards from its cross-reference to the
// function that owns it (via the module's exception directory).

struct ModuleLayout {
    uintptr_t base;
    size_t size;
    const uint8_t* text;
    size_t text_size;
    const RUNTIME_FUNCTION* funcs;
    size_t funcs_count;
};

ModuleLayout layout_module(HMODULE mod) {
    ModuleLayout m{};
    m.base = reinterpret_cast<uintptr_t>(mod);
    auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(mod);
    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS*>(m.base + dos->e_lfanew);
    m.size = nt->OptionalHeader.SizeOfImage;

    IMAGE_SECTION_HEADER* sect = IMAGE_FIRST_SECTION(nt);
    for (int i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        if (memcmp(sect[i].Name, ".text", 5) == 0) {
            m.text = reinterpret_cast<const uint8_t*>(m.base + sect[i].VirtualAddress);
            m.text_size = sect[i].Misc.VirtualSize;
            break;
        }
    }

    IMAGE_DATA_DIRECTORY* exc = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXCEPTION];
    if (exc->VirtualAddress) {
        m.funcs = reinterpret_cast<RUNTIME_FUNCTION*>(m.base + exc->VirtualAddress);
        m.funcs_count = exc->Size / sizeof(RUNTIME_FUNCTION);
    }
    return m;
}

const uint8_t* find_bytes(const uint8_t* haystack, size_t hsize,
                          const void* needle, size_t nsize) {
    if (nsize == 0 || hsize < nsize) return nullptr;
    for (size_t i = 0; i + nsize <= hsize; ++i) {
        if (memcmp(haystack + i, needle, nsize) == 0) return haystack + i;
    }
    return nullptr;
}

// Find `lea r64, [rip + disp32]` inside .text whose displacement resolves
// to `target`. REX.W byte is 0x48..0x4F; ModRM r/m field 101 with mod 00.
const uint8_t* find_lea_to(const ModuleLayout& m, const uint8_t* target) {
    if (!m.text || m.text_size < 7) return nullptr;
    for (size_t i = 0; i + 7 <= m.text_size; ++i) {
        const uint8_t* p = m.text + i;
        if ((p[0] & 0xF8) != 0x48) continue;
        if (p[1] != 0x8D) continue;
        if ((p[2] & 0xC7) != 0x05) continue;
        int32_t disp;
        memcpy(&disp, p + 3, sizeof(disp));
        if (p + 7 + disp == target) return p;
    }
    return nullptr;
}

const void* function_containing(const ModuleLayout& m, uintptr_t addr) {
    if (!m.funcs || m.funcs_count == 0) return nullptr;
    uintptr_t rva = addr - m.base;
    for (size_t i = 0; i < m.funcs_count; ++i) {
        if (m.funcs[i].BeginAddress <= rva && rva < m.funcs[i].EndAddress) {
            return reinterpret_cast<const void*>(m.base + m.funcs[i].BeginAddress);
        }
    }
    return nullptr;
}

// Stable literal emitted by the PXScript interpreter's loop-count guard.
constexpr char INTERP_SIG_STR[] =
    "PXScript: Max count detected for loop %s, exiting program.";

void* resolve_interpreter(HMODULE mod) {
    ModuleLayout m = layout_module(mod);
    if (!m.text || !m.funcs) return nullptr;
    const uint8_t* str = find_bytes(
        reinterpret_cast<const uint8_t*>(m.base), m.size,
        INTERP_SIG_STR, sizeof(INTERP_SIG_STR) - 1);
    if (!str) return nullptr;
    const uint8_t* lea = find_lea_to(m, str);
    if (!lea) return nullptr;
    return const_cast<void*>(function_containing(m, reinterpret_cast<uintptr_t>(lea)));
}

DWORD WINAPI init_thread(LPVOID) {
    if (const char* p = getenv("PXDUMP_PATH")) {
        strncpy(dump_path, p, sizeof(dump_path) - 1);
        dump_path[sizeof(dump_path) - 1] = 0;
    }
    HMODULE mod = GetModuleHandleA("SSOClient.exe");
    if (!mod) mod = GetModuleHandleA(nullptr);
    if (!mod) return 0;

    void* target = resolve_interpreter(mod);
    if (!target) {
        // Sig miss: env-var override for a hand-picked RVA.
        if (const char* r = getenv("PXDUMP_RVA")) {
            target = reinterpret_cast<void*>(
                reinterpret_cast<uintptr_t>(mod) + strtoull(r, nullptr, 0));
        } else {
            return 0;
        }
    }

    if (MH_Initialize() != MH_OK) return 0;
    if (MH_CreateHook(target, reinterpret_cast<void*>(&hook),
                      reinterpret_cast<void**>(&original)) != MH_OK) return 0;
    MH_EnableHook(target);
    return 0;
}

}

BOOL APIENTRY DllMain(HMODULE mod, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(mod);
        CreateThread(nullptr, 0, init_thread, nullptr, 0, nullptr);
    }
    return TRUE;
}
