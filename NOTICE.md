# Third-party code

## fingerskier/Mooer_GE150_Pro_Li-IO

- Source: https://github.com/fingerskier/Mooer_GE150_Pro_Li-IO
- Commit: `b1756d5459fe392ca4c6a2972601ae2dfbfa6fde` (2026-09-30)
- Files used:
  - `src/mooer_ge150_mcp/utils/crc.py` → `src/ge100pro/crc.py` (unchanged apart from a header and a docstring note)
  - `src/mooer_ge150_mcp/protocol/framing.py` → `src/ge100pro/framing.py` (adapted: see the file header)
- License: MIT, as declared in the project's `pyproject.toml`. The license text:

```
MIT License

Copyright (c) Matt Currier (fingerskier)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Protocol knowledge

No code was copied from these projects, but their published findings informed this work; see PROTOCOL.md §6:
andymann/mooer-prime-m2-app, lucanenni/mooer-prime-m2-web, klaushofrichter/ge150pro-editor,
atahan26/ge200-editor, ThijsWithaar/MooerManager.
