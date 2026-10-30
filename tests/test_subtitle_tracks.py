"""The subtitle track list is a first-class selection, not an afterthought.

These tests pin the four rules the UI depends on:

  * manual and auto tracks for the same language are *separate* entries,
  * a track carries the name the service reports (falling back to its code),
  * the original language is the default, and manual wins over auto,
  * "no original language" means "no default" — never a random guess.
"""
from __future__ import annotations

from src import media_source


def _info(**kwargs) -> dict:
    info = {
        "language": "ja",
        "subtitles": {
            "ja": [{"name": "Japanese"}],
            "en": [{"name": "English"}],
        },
        "automatic_captions": {
            "ja": [{"name": "Japanese (auto-generated)"}],
            "de": [{"name": "German (auto-generated)"}],
        },
    }
    info.update(kwargs)
    return info


class TestBuildSubtitleTracks:
    def test_manual_tracks_come_first(self):
        tracks = media_source.build_subtitle_tracks(_info())
        kinds = [t["kind"] for t in tracks]
        assert kinds == sorted(kinds, key=lambda k: 0 if k == "manual" else 1), kinds
        assert kinds.count("manual") == 2
        assert kinds.count("auto") == 2

    def test_same_language_yields_two_entries(self):
        tracks = media_source.build_subtitle_tracks(_info())
        ja = [t for t in tracks if t["code"] == "ja"]
        assert len(ja) == 2, "manual and auto Japanese are different tracks"
        assert {t["kind"] for t in ja} == {"manual", "auto"}
        assert len({t["label"] for t in ja}) == 2

    def test_names_and_labels(self):
        tracks = media_source.build_subtitle_tracks(_info())
        english = next(t for t in tracks if t["kind"] == "manual" and t["code"] == "en")
        assert english["name"] == "English"
        assert english["label"] == "English · manual"

    def test_name_falls_back_to_the_code(self):
        tracks = media_source.build_subtitle_tracks(
            {"language": "en", "subtitles": {"en": []}, "automatic_captions": {}}
        )
        assert tracks[0]["name"] == "en"
        assert tracks[0]["label"] == "en · manual"

    def test_live_chat_is_not_a_subtitle_track(self):
        tracks = media_source.build_subtitle_tracks(
            {"language": "en", "subtitles": {"live_chat": [{"name": "Live chat"}]},
             "automatic_captions": {}}
        )
        assert tracks == []

    def test_no_tracks_at_all(self):
        assert media_source.build_subtitle_tracks({"language": "en"}) == []

    def test_original_language_is_marked(self):
        tracks = media_source.build_subtitle_tracks(_info())
        for track in tracks:
            assert track["isOriginal"] is (track["code"] == "ja")
            assert isinstance(track["isOriginal"], bool)


class TestDefaultSubtitleTrack:
    def test_original_language_manual_wins(self):
        assert media_source.default_subtitle_track(_info()) == "ja"

    def test_auto_is_the_fallback_when_only_auto_exists(self):
        info = {
            "language": "ja",
            "subtitles": {"en": [{"name": "English"}]},
            "automatic_captions": {"ja": [{"name": "Japanese"}]},
        }
        assert media_source.default_subtitle_track(info) == "ja"

    def test_region_variant_matches_the_base_language(self):
        info = {
            "language": "pt",
            "subtitles": {},
            "automatic_captions": {"pt-BR": [{"name": "Portuguese (Brazil)"}]},
        }
        assert media_source.default_subtitle_track(info) == "pt-BR"

    def test_unknown_original_language_means_no_default(self):
        info = {
            "language": "",
            "subtitles": {"en": [{"name": "English"}]},
            "automatic_captions": {},
        }
        assert media_source.default_subtitle_track(info) == ""

    def test_original_language_without_a_track_means_no_default(self):
        info = {
            "language": "fr",
            "subtitles": {"en": [{"name": "English"}]},
            "automatic_captions": {},
        }
        assert media_source.default_subtitle_track(info) == ""

    def test_accepts_a_payload_that_already_has_tracks(self):
        info = _info()
        info["subtitle_tracks"] = media_source.build_subtitle_tracks(info)
        assert media_source.default_subtitle_track(info) == "ja"


class TestInspectVideoPayload:
    def test_inspect_video_exposes_tracks_and_default(self, monkeypatch):
        monkeypatch.setattr(
            media_source,
            "_yt_dlp_json",
            lambda url: {
                **_info(),
                "title": "A video",
                "formats": [],
            },
        )
        result = media_source.inspect_video("https://youtu.be/dQw4w9WgXcQ")
        assert result["language"] == "ja"
        assert result["default_subtitle_track"] == "ja"
        assert len(result["subtitle_tracks"]) == 4
        assert "has_english_subtitle" not in result
