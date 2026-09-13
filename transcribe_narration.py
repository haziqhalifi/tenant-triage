"""Generate local word timestamps for the supplied recording."""
import json
from pathlib import Path
from faster_whisper import WhisperModel

model = WhisperModel('base.en', device='cpu', compute_type='int8', download_root='/tmp/unitcue-speech-models')
segments, info = model.transcribe('/Users/haziqhalifi/Downloads/San Francisco Coffee.m4a', language='en', word_timestamps=True)
result = []
for segment in segments:
    row = {'start': segment.start, 'end': segment.end, 'text': segment.text,
           'words': [{'start': w.start, 'end': w.end, 'word': w.word} for w in segment.words]}
    result.append(row)
    print(f'{segment.start:.2f}-{segment.end:.2f}: {segment.text}', flush=True)
Path('data/narration-timestamps.json').write_text(json.dumps(result, indent=2))
