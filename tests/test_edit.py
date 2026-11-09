import shutil
import subprocess

import pytest

from talkcut.edit import find_fillers, keep_ranges, plan_cuts, probe_duration, render


def w(text, start, end):
    return {"text": text, "start": start, "end": end}


WORDS = [w("So", 0.0, 0.5), w("um,", 0.6, 1.0), w("hello", 1.2, 1.5)]


def test_middle_deletion_takes_the_gap_but_leaves_pad():
    assert plan_cuts(WORDS, [1], 2.0) == [(0.55, 1.15)]


def test_leading_and_trailing_deletions_reach_the_file_edges():
    assert plan_cuts(WORDS, [0], 2.0) == [(0.0, 0.55)]
    assert plan_cuts(WORDS, [2], 2.0) == [(1.05, 2.0)]


def test_adjacent_deletions_merge_into_one_cut():
    assert plan_cuts(WORDS, [1, 2], 2.0) == [(0.55, 2.0)]


def test_pad_never_keeps_part_of_a_deleted_word():
    tight = [w("a", 0.0, 0.5), w("b", 0.51, 0.9), w("c", 0.91, 1.3)]
    assert plan_cuts(tight, [1], 1.5) == [(0.51, 0.9)]


def test_everything_deleted_leaves_nothing_to_keep():
    cuts = plan_cuts(WORDS, [0, 1, 2], 2.0)
    assert cuts == [(0.0, 2.0)]
    assert keep_ranges(cuts, 2.0) == []


def test_keep_ranges_is_the_complement():
    assert keep_ranges([(0.55, 1.15)], 2.0) == [(0.0, 0.55), (1.15, 2.0)]
    assert keep_ranges([], 2.0) == [(0.0, 2.0)]


def test_fillers_ignore_case_and_punctuation_but_not_real_words():
    words = [w("Um,", 0, 1), w("UH.", 1, 2), w("umbrella", 2, 3), w("hmm...", 3, 4)]
    assert find_fillers(words) == [0, 1, 3]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_rendered_length_matches_the_kept_ranges(tmp_path):
    src, dst = tmp_path / "tone.wav", tmp_path / "out.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=3", str(src)], check=True
    )
    render(str(src), str(dst), [(0.0, 1.0), (2.0, 3.0)])
    assert probe_duration(str(dst)) == pytest.approx(2.0, abs=0.01)
