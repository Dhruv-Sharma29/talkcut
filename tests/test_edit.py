import shutil
import subprocess

import pytest

import numpy as np

from talkcut.edit import (
    find_fillers, keep_ranges, plan_cuts, probe_duration, render, snap_to_silence,
)


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


def levels(*spans):
    """10 ms loudness frames from (seconds, loud?) spans."""
    return np.concatenate([np.full(round(s / 0.01), 1.0 if loud else 0.0) for s, loud in spans])


# kept word 0-0.5 s, pause, deleted word 0.8-1.2 s, pause, kept word 1.5-2.0 s
SPEECH = levels((0.5, 1), (0.3, 0), (0.4, 1), (0.3, 0), (0.5, 1))


def test_edges_that_land_in_speech_move_to_the_nearest_pause():
    # Timestamps said the first word ended at 0.45 and the last began at 1.6: both too early/late.
    assert snap_to_silence([(0.45, 1.6)], SPEECH) == [(0.55, 1.45)]


def test_edges_already_in_a_pause_stay_put():
    assert snap_to_silence([(0.6, 1.3)], SPEECH) == [(0.6, 1.3)]


def test_snapping_never_moves_an_edge_further_than_max_shift():
    long_word = levels((1.0, 1), (0.5, 0), (0.5, 1))
    assert snap_to_silence([(0.2, 1.2)], long_word) == [(0.2, 1.2)]


def test_snapping_never_brings_back_a_deleted_word():
    # "think . the first one" with only 50 ms gaps around "first"; "the first" is deleted.
    # The planned end (1.2, in the gap before "one") is right; snapping back to the gap
    # between "the" and "first" would quietly un-delete "first".
    audio = levels((0.5, 1), (0.3, 0), (0.1, 1), (0.05, 0), (0.25, 1), (0.05, 0), (0.35, 1))
    words = [w("think", 0.0, 0.5), w("the", 0.8, 0.88), w("first", 0.88, 1.2), w("one", 1.2, 1.5)]
    cuts = plan_cuts(words, [1, 2], 1.6)
    assert cuts == [(0.55, 1.2)]
    assert snap_to_silence(cuts, audio, words) == [(0.55, 1.2)]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_rendered_length_matches_the_kept_ranges(tmp_path):
    src, dst = tmp_path / "tone.wav", tmp_path / "out.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=3", str(src)], check=True
    )
    render(str(src), str(dst), [(0.0, 1.0), (2.0, 3.0)])
    assert probe_duration(str(dst)) == pytest.approx(2.0, abs=0.01)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_render_handles_more_ranges_than_the_default_open_file_limit(tmp_path):
    # One input per range: 300 ranges is past macOS's default limit of 256 open files.
    # `uv run` raises that limit itself, so this only bites without uv (pip/pipx installs):
    # check with `ulimit -n 256; .venv/bin/python -m pytest`.
    src, dst = tmp_path / "tone.wav", tmp_path / "out.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=30", str(src)], check=True
    )
    keep = [(k * 0.1, k * 0.1 + 0.05) for k in range(300)]
    render(str(src), str(dst), keep)
    assert probe_duration(str(dst)) == pytest.approx(15.0, abs=0.05)
