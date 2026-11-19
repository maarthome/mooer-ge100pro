# Credits

This project stands on the work of other people who took Mooer pedals apart before us. Thank you.

## Code used in this repository

| Project | Author | What we use | License |
|---|---|---|---|
| [fingerskier/Mooer_GE150_Pro_Li-IO](https://github.com/fingerskier/Mooer_GE150_Pro_Li-IO) | Matt Currier (fingerskier) | `crc.py` (CRC lookup table) and `framing.py` (frames, report splitting); `web/protocol.js` ports the same logic | MIT |
| [atahan26/ge200-editor](https://github.com/atahan26/ge200-editor) | Atahan Şevki Bilginoğlu | `hid_win.py`: Windows HID access with stdlib ctypes | MIT |

Exact files, commits and license texts are in [NOTICE.md](NOTICE.md).

## Protocol knowledge used

No code was copied from these projects; their published findings shaped what we looked for and how.

| Project | Model | What it taught us |
|---|---|---|
| [andymann/mooer-prime-m2-app](https://github.com/andymann/mooer-prime-m2-app) | Prime M2 | the command family the GE100 Pro turned out to share (`01`, `11`, `13`, `25`, `29`, `2b`, `2f`, reply = request + 1), selecting a preset by writing the state back, the deaf period after a select, the warning about `81`, and a careful capture method |
| [lucanenni/mooer-prime-m2-web](https://github.com/lucanenni/mooer-prime-m2-web) | Prime M2 | protocol notes that confirm the above, and a WebHID editor that showed a web page is a good fit |
| [klaushofrichter/ge150pro-editor](https://github.com/klaushofrichter/ge150pro-editor) | GE150 Pro | the clearest write-up of the shared `AA 55` + CRC-16/GSM framing and the `[n]` report prefix, and the list of commands that erase memory on the GE150 |
| [atahan26/ge200-editor](https://github.com/atahan26/ge200-editor) | GE200 | framing details and the GE200's destructive commands (`E4`, `E5`) |
| [fingerskier/Mooer_GE150_Pro_Li-IO](https://github.com/fingerskier/Mooer_GE150_Pro_Li-IO) | GE150 Max | that the newer Mooer units use vendor ID `34db` with HID endpoints `0x85`/`0x05`, and the capture-driven, test-backed way of working |
| [ThijsWithaar/MooerManager](https://github.com/ThijsWithaar/MooerManager) | GE200 | the earliest public decoding of a Mooer USB protocol (Wireshark dissector) |

## Reviewed, nothing used

Checked during the research; they contain no USB protocol work that applies to the GE100 Pro.

| Project | What it is |
|---|---|
| [sidekickDan/mooerMoConvert](https://github.com/sidekickDan/mooerMoConvert) | GE200 → GE150 preset file converter (PHP, based on a gist by sonnm) |
| [fausto-ai/MOOER-ge300](https://github.com/fausto-ai/MOOER-ge300) | AI tone suggestion website for the GE300 Pro |
| [BrokenRain/MooerGE300](https://github.com/BrokenRain/MooerGE300) | 2018 Windows UI skeleton without device code |
| [BrokenRain/MooerStudio](https://github.com/BrokenRain/MooerStudio) | mirror of Mooer's official editors and firmware (2020) |
| [klaushofrichter/ge150pro-game](https://github.com/klaushofrichter/ge150pro-game) | game using the GE150 Pro as a controller |
| [lucanenni/mooer-prime-m2-mcp](https://github.com/lucanenni/mooer-prime-m2-mcp) | MCP server for the Prime M2 |
| [zennuttm27-star/GE150PRO](https://github.com/zennuttm27-star/GE150PRO), [minki414/GE150_auto_setting](https://github.com/minki414/GE150_auto_setting) | GE150 Pro control and preset tools |

Mooer, GE100 Pro and Mooer Studio are names of MOOER Audio. This project is unofficial and not affiliated with or endorsed by MOOER Audio.
