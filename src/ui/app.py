from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Fix encoding issues on Windows
if sys.platform == "win32":
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import streamlit as st
from dotenv import load_dotenv

from src.services.subtitle_service import build_service_from_env


def parse_season_episode(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract season and episode numbers from a string like S01E02 or 1x02."""
    if not text:
        return None, None
    # Match S01E02 format
    match = re.search(r'[Ss](\d{1,2})[Ee](\d{1,2})', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    # Match 1x02 format
    match = re.search(r'(\d{1,2})[xX](\d{1,2})', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def is_tv_show_results(results) -> bool:
    """Check if results appear to be TV show episodes."""
    if not results:
        return False
    tv_count = 0
    for item in results[:10]:  # Check first 10
        text = item.release or item.file_name or ""
        season, episode = parse_season_episode(text)
        if season is not None:
            tv_count += 1
    return tv_count >= len(results[:10]) * 0.5  # At least 50% have season/episode


def group_by_season_episode(results) -> Dict[int, Dict[int, List]]:
    """Group results by season and episode."""
    grouped = defaultdict(lambda: defaultdict(list))
    ungrouped = []

    for item in results:
        text = item.release or item.file_name or ""
        season, episode = parse_season_episode(text)
        if season is not None and episode is not None:
            grouped[season][episode].append(item)
        else:
            ungrouped.append(item)

    return grouped, ungrouped


@st.cache_resource
def get_service():
    load_dotenv()
    return build_service_from_env()


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="Persian Subtitle Search", layout="centered")
    st.title("Persian Subtitle Search")
    st.write("Search OpenSubtitles via MCP and download Persian subtitles.")

    movie_name = st.text_input("Movie/TV Show name")
    col_year, col_imdb, col_type = st.columns(3)
    with col_year:
        year = st.text_input("Year (optional)")
    with col_imdb:
        imdb_id = st.text_input("IMDB ID (optional)", help="e.g., tt5014882")
    with col_type:
        content_type = st.selectbox(
            "Type",
            options=["all", "movie", "tvshow", "episode"],
            index=0,
            help="Filter by content type"
        )
    prefer_lang = st.selectbox("Preferred language", options=["fa", "en"], index=0)
    fallback_to_english = st.checkbox("If no Persian, show English results", value=True)

    if "results" not in st.session_state:
        st.session_state.results = []

    service = get_service()

    col_search, col_download = st.columns(2)

    with col_search:
        if st.button("Search"):
            if not movie_name.strip():
                st.warning("Please enter a movie name.")
            else:
                try:
                    status = st.empty()
                    parsed_year = int(year) if year.strip().isdigit() else None
                    # Parse IMDB ID - remove 'tt' prefix if present and convert to int
                    parsed_imdb = None
                    if imdb_id.strip():
                        imdb_clean = imdb_id.strip().lower().replace("tt", "")
                        if imdb_clean.isdigit():
                            parsed_imdb = int(imdb_clean)
                    # Type filter - None if "all" selected
                    type_filter = content_type if content_type != "all" else None
                    results = []

                    # Search preferred language first
                    status.info(f"Searching for {prefer_lang.upper()} subtitles...")
                    try:
                        fa_results = service.search(
                            movie_name=movie_name,
                            year=parsed_year,
                            language=prefer_lang,
                            imdb_id=parsed_imdb,
                            type=type_filter,
                        )
                        results.extend(fa_results)
                    except Exception as e:
                        st.warning(f"Search for {prefer_lang.upper()} failed: {e}")

                    # When fallback is enabled, also search English
                    if prefer_lang == "fa" and fallback_to_english:
                        status.info("Searching for EN subtitles...")
                        try:
                            en_results = service.search(
                                movie_name=movie_name,
                                year=parsed_year,
                                language="en",
                                imdb_id=parsed_imdb,
                                type=type_filter,
                            )
                            results.extend(en_results)
                        except Exception as e:
                            st.warning(f"Search for EN failed: {e}")

                    status.empty()
                    st.session_state.results = results
                    if not results:
                        st.info("No subtitles found for this movie. Try a different search term or year.")
                except Exception as exc:
                    st.error(str(exc))

    with col_download:
        if st.button("Download best match"):
            if not movie_name.strip():
                st.warning("Please enter a movie name.")
            else:
                try:
                    result = service.download_best(
                        movie_name=movie_name,
                        year=int(year) if year.strip().isdigit() else None,
                        prefer_lang=prefer_lang,
                    )
                    st.success(f"Saved to {result.file_path}")
                    st.download_button(
                        label="Download SRT",
                        data=result.content_bytes,
                        file_name=os.path.basename(result.file_path),
                        mime="application/x-subrip",
                    )
                except Exception as exc:
                    st.error(str(exc))

    if st.session_state.results:
        st.subheader(f"Search results ({len(st.session_state.results)} found)")

        # Check if this is a TV show
        is_tv = is_tv_show_results(st.session_state.results)

        if is_tv:
            # TV Show mode - organized by season/episode
            grouped, ungrouped = group_by_season_episode(st.session_state.results)

            # Filter input
            filter_text = st.text_input(
                "Filter results",
                placeholder="Type to filter (e.g., S01E03, 720p, HDTV...)",
                key="result_filter"
            )

            # Store selected item
            if "selected_item" not in st.session_state:
                st.session_state.selected_item = None

            # Display organized results
            for season in sorted(grouped.keys()):
                with st.expander(f"Season {season}", expanded=(season == min(grouped.keys()))):
                    for episode in sorted(grouped[season].keys()):
                        items = grouped[season][episode]

                        # Apply filter
                        if filter_text:
                            items = [
                                item for item in items
                                if filter_text.lower() in (item.release or "").lower()
                                or filter_text.lower() in (item.file_name or "").lower()
                            ]
                            if not items:
                                continue

                        st.markdown(f"**Episode {episode}** ({len(items)} versions)")

                        for i, item in enumerate(items):
                            release = item.release or item.file_name or item.subtitle_id
                            downloads = f"downloads: {item.download_count}" if item.download_count else ""
                            lang_badge = f"[{item.language.upper()}]"

                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.caption(f"{lang_badge} {release} {downloads}")
                            with col2:
                                btn_key = f"select_s{season}_e{episode}_{i}"
                                if st.button("Select", key=btn_key):
                                    st.session_state.selected_item = item

            # Show ungrouped items if any
            if ungrouped:
                if filter_text:
                    ungrouped = [
                        item for item in ungrouped
                        if filter_text.lower() in (item.release or "").lower()
                        or filter_text.lower() in (item.file_name or "").lower()
                    ]
                if ungrouped:
                    with st.expander(f"Other ({len(ungrouped)} items)"):
                        for i, item in enumerate(ungrouped):
                            release = item.release or item.file_name or item.subtitle_id
                            downloads = f"downloads: {item.download_count}" if item.download_count else ""
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.caption(f"[{item.language.upper()}] {release} {downloads}")
                            with col2:
                                if st.button("Select", key=f"select_other_{i}"):
                                    st.session_state.selected_item = item

            # Show selected item actions
            selected = st.session_state.selected_item
        else:
            # Movie mode - simple dropdown
            filter_text = st.text_input(
                "Filter results",
                placeholder="Type to filter...",
                key="result_filter"
            )

            filtered_results = st.session_state.results
            if filter_text:
                filtered_results = [
                    item for item in st.session_state.results
                    if filter_text.lower() in (item.release or "").lower()
                    or filter_text.lower() in (item.file_name or "").lower()
                ]

            if filtered_results:
                labels = []
                for item in filtered_results:
                    label = f"{item.language} | {item.release or item.file_name or item.subtitle_id}"
                    if item.download_count is not None:
                        label += f" | downloads: {item.download_count}"
                    labels.append(label)

                selection = st.selectbox("Select a subtitle", options=labels)
                selected_idx = labels.index(selection)
                selected = filtered_results[selected_idx]
            else:
                st.info("No results match your filter.")
                selected = None

        # Download section for selected item
        if selected:
            st.divider()
            st.markdown(f"**Selected:** {selected.release or selected.file_name}")

            is_non_persian = selected.language != "fa"

            if is_non_persian:
                col_orig, col_translate = st.columns(2)

                with col_orig:
                    download_original = st.button(f"Download Original ({selected.language.upper()})")

                with col_translate:
                    download_translated = st.button("Translate to Persian")

                if download_original:
                    try:
                        result = service.download_selected(
                            movie_name=movie_name,
                            item=selected,
                            target_lang=selected.language,
                        )
                        st.success(f"Saved to {result.file_path}")
                        st.download_button(
                            label=f"Download SRT ({selected.language.upper()})",
                            data=result.content_bytes,
                            file_name=os.path.basename(result.file_path),
                            mime="application/x-subrip",
                        )
                    except Exception as exc:
                        st.error(str(exc))

                if download_translated:
                    try:
                        progress_bar = st.progress(0, text="Downloading subtitle...")
                        status_text = st.empty()

                        def update_progress(current: int, total: int, pct: float):
                            progress_bar.progress(int(pct), text=f"Translating to Persian... {int(pct)}%")
                            status_text.text(f"Translating chunk {current}/{total}")

                        result = service.download_selected(
                            movie_name=movie_name,
                            item=selected,
                            target_lang="fa",
                            progress_callback=update_progress,
                        )
                        progress_bar.progress(100, text="Translation complete!")
                        status_text.empty()

                        st.success(f"Saved to {result.file_path}")
                        st.download_button(
                            label="Download SRT (Persian)",
                            data=result.content_bytes,
                            file_name=os.path.basename(result.file_path),
                            mime="application/x-subrip",
                        )
                    except Exception as exc:
                        st.error(str(exc))
            else:
                if st.button("Download selected"):
                    try:
                        result = service.download_selected(
                            movie_name=movie_name,
                            item=selected,
                            target_lang="fa",
                        )
                        st.success(f"Saved to {result.file_path}")
                        st.download_button(
                            label="Download SRT",
                            data=result.content_bytes,
                            file_name=os.path.basename(result.file_path),
                            mime="application/x-subrip",
                        )
                    except Exception as exc:
                        st.error(str(exc))


main()
