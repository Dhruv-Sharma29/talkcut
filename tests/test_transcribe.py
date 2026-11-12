from types import SimpleNamespace

import numpy as np

from talkcut.transcribe import fill_gaps, speech_gaps


def w(text, start, end):
    return {"text": text, "start": start, "end": end}


def test_speech_covered_by_words_is_not_a_gap():
    assert speech_gaps([w("hi", 1.0, 1.5), w("there", 1.6, 3.0)], [(1.0, 3.0)], 5.0) == []


def test_untranscribed_speech_is_a_gap_but_a_short_blip_is_not():
    words = [w("hi", 0.0, 1.0)]
    assert speech_gaps(words, [(4.0, 7.0)], 10.0) == [(4.0, 7.0)]
    assert speech_gaps(words, [(4.0, 4.8)], 10.0) == []  # under min_speech


def test_gaps_close_together_are_one_gap():
    # Repairing these separately split "I mean" into "I'm" / "mean" on the real podcast.
    assert speech_gaps([], [(2.0, 3.0), (3.5, 5.0)], 10.0) == [(2.0, 5.0)]
    assert speech_gaps([], [(2.0, 3.0), (6.0, 7.0)], 10.0) == [(2.0, 3.0), (6.0, 7.0)]


class FakeWhisper:
    """Returns words at fixed times relative to the clip it is given."""

    def __init__(self, words):
        self.words, self.clips = words, []

    def transcribe(self, clip, **options):
        self.clips.append(len(clip) / 16000)
        seg = SimpleNamespace(words=[SimpleNamespace(word=t, start=a, end=b) for t, a, b in self.words])
        return [seg], None


def test_fill_gaps_shifts_recovered_words_and_keeps_only_those_inside_the_gap():
    audio = np.zeros(16000 * 10, np.float32)
    words = [w("before", 0.5, 1.0), w("after", 8.0, 8.5)]
    # Gap is 4.0-6.0 s; the clip starts 0.3 s earlier, so 0.1 s in the clip is 3.8 s: outside.
    whisper = FakeWhisper([(" edge", 0.0, 0.2), (" lost", 0.8, 1.2), (" words", 1.3, 1.9)])
    merged, added = fill_gaps(whisper, audio, words, [(4.0, 6.0)])
    assert added == 2
    assert [x["text"] for x in merged] == ["before", "lost", "words", "after"]
    assert merged[1] == w("lost", 4.5, 4.9)
    assert abs(whisper.clips[0] - 2.6) < 1e-6  # 0.3 s of context each side


def test_nothing_to_fill_means_no_extra_transcription():
    whisper = FakeWhisper([])
    merged, added = fill_gaps(whisper, np.zeros(16000 * 3, np.float32), [w("hi", 0.5, 2.5)], [(0.5, 2.5)])
    assert added == 0 and whisper.clips == []
