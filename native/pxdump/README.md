# pxdump.dll

In-process PXScript capture. Hooks the VM interpreter in `SSOClient.exe` with MinHook, disassembles each program on execution, and appends to a dump that `ssotk pxscript` renders.

## Build

Visual Studio 2022 + ClangCL, x64. MinHook is fetched by CMake.

```
cmake --preset default
cmake --build build --config Release
```

Output: `build/Release/pxdump.dll`.

## Use

1. Launch SSO and log in.
2. Get the client PID: `tasklist | findstr SSOClient`.
3. Inject:
   ```
   python ..\..\tools\inject.py <pid> <absolute path>\pxdump.dll
   ```
4. Play to trigger the scripts you want; programs stream to
   `C:\tmp\pxscript_dump.txt` (deduped per program).
5. Render:
   ```
   ssotk pxscript C:\tmp\pxscript_dump.txt --out scripts.txt
   ```

The interpreter is located at inject time by signature: the DLL scans
`SSOClient.exe` for the string literal `"PXScript: Max count detected for
loop %s, exiting program."`, walks its LEA cross-reference, and resolves
the enclosing function via the module's exception directory (`.pdata`).

## Config (env vars, read at inject time)

- `PXDUMP_PATH` - output file (default `C:\tmp\pxscript_dump.txt`).
- `PXDUMP_RVA` - hex offset to hook directly, used only if the signature
  lookup fails. Rebuild against the current binary instead when you can.

NOTE: Injecting carries anti-cheat / ban risk.
