Captured from the live API on 2026-11-02 with the fixtures in ../../../fixtures (trimmed copies, no key or headers):
svd_synthetic.json   synthetic-1.wav
svd_real.json        real-2.wav
music_ai_vocal.json  synthetic-1.wav sent to the AI music endpoint
music_not_ai.json    music-1.wav
stt_pii.json         pii-speech.wav with all signals on
triage_default.json  an earlier cut of real-1.wav with config=default
redaction_*          pii-speech.wav; the MP3 part is cut to 1500 bytes, boundary and part headers are as received
