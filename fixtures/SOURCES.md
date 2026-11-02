# Fixture sources

All clips are mono 16-bit WAV, under 1 MB. Made on 2026-11-02.

| File | What it is | Source | Licence |
| - | - | - | - |
| `synthetic-1.wav` | Synthetic voice, about 9 s | Piper TTS, voice `en_US-ljspeech-medium`, run locally | Voice trained on LJ Speech, public domain (voice model card) |
| `pii-speech.wav` | Synthetic voice, about 12 s. Contains a made-up name, a 555 phone number and a made-up date of birth | Same Piper voice | Same |
| `real-1.wav` | Human speech, 12 s, from 40 s into the track (earlier parts hold the LibriVox intro) | LibriVox, "Aesop's Fables, Volume 2", track "The Fox and The Stork" (`archive.org/details/aesop_fables_volume_two_librivox`) | Public domain (LibriVox recordings are dedicated to the public domain) |
| `real-2.wav` | Human speech, 12 s, from 14 s into the track | LibriVox, "Aesop's Fables, Volume 1", track "The North Wind and The Sun" (`archive.org/details/aesop_fables_volume_one_librivox`) | Public domain |
| `music-1.wav` | Human-made music (a historical opera recording), 12 s, from 2 s into the file | Wikimedia Commons, "CC0-CH - Various artists - Madama Butterfly - Io scendo al piano - Giacomo Puccini - Columbia-d14539-bx546.flac" | Public domain as marked on Commons. Re-check the file page before redistributing |

Notes:
- `real-1.wav` and `real-2.wav` are the same LibriVox reader style, so they are one kind of real voice, not two.
- `synthetic-2.wav` (macOS `say`, voice Samantha) is generated locally and is not committed because the licence of Apple voice output is unclear.
- Studio-style clips like these do not match phone audio. Do not tune thresholds on them.
